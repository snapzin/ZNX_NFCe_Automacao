import logging
import threading
import time

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from api import server
from app.automation import sat_automacao
from app.automation.sat_auth import resultado, check_cancel


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server.config, "XLSX_PATH", str(tmp_path / "clientes.xlsx"))
    monkeypatch.setattr(server, "_API_TOKEN", "test-session-token")
    # Licenciamento simulado somente no teste; produção mantém validação real.
    monkeypatch.setattr(server, "validate_license_key", lambda key: (key == "test-license", "test license"))
    server.JOBS.clear()
    with TestClient(server.app) as c:
        c.headers.update({"x-api-token": "test-session-token", "x-license-key": "test-license"})
        yield c
    for job in server.JOBS.values():
        job.cancel_event.set()
        if job.thread:
            job.thread.join(3)


def customer(**changes):
    return {"documento": "12345678901", "nome": "Empresa Teste", "ativo": True,
            "usuario_sat": "test-user", "senha_sat": "=test-secret", **changes}


def wait_job(client, jobid):
    for _ in range(100):
        data = client.get(f"/executar/{jobid}/status").json()
        if data["status"] != "running":
            return data
        time.sleep(0.02)
    pytest.fail("Job did not finish")


def test_api_token_and_license_remain_required(client):
    assert client.get("/health").status_code == 200
    assert client.get("/health/auth", headers={"x-api-token": "wrong"}).status_code == 401
    assert client.get("/clientes", headers={"x-license-key": ""}).status_code == 402


def test_customer_round_trip_and_excel_literal(client):
    assert client.post("/clientes", json={"clientes": [customer()]}).status_code == 200
    saved = client.get("/clientes").json()["clientes"][0]
    assert saved["senha_sat"] == "=test-secret"
    wb = load_workbook(server.config.XLSX_PATH, data_only=False)
    assert wb.active["F2"].data_type == "s"
    wb.close()
    saved["ativo"] = False
    client.post("/clientes", json={"clientes": [saved]})
    assert client.post("/executar", json={}).status_code == 400


@pytest.mark.parametrize("user_header,password_header", [
    ("usuario", "senha"), ("USUARIO_SAT", "SENHA_SAT"), ("USUARIO_NFSE", "SENHA_NFSE")])
def test_import_aliases(client, tmp_path, user_header, password_header):
    p = tmp_path / "import.xlsx"
    wb = Workbook()
    wb.active.append(["cnpj", "nome", user_header, password_header, "ativo"])
    wb.active.append(["12345678901", "Importada", "login", "secret", "Não"])
    wb.save(p)
    wb.close()
    data = client.post("/clientes/importar", json={"path": str(p)}).json()["clientes"][0]
    assert data["usuario_sat"] == "login" and data["senha_sat"] == "secret"
    assert data["ativo"] is False


def test_job_summary_progress_and_no_secrets(client, monkeypatch, caplog):
    with caplog.at_level(logging.INFO):
        client.post("/clientes", json={"clientes": [customer(), customer(documento="12345678902", nome="Empresa B")]})
        outcomes = iter([resultado("INVALID_CREDENTIALS"), resultado("USER_SELECTION_REQUIRED")])
        monkeypatch.setattr(sat_automacao, "autenticar_cliente", lambda *a: next(outcomes))
        response = client.post("/executar", json={})
        assert response.status_code == 200
        data = wait_job(client, response.json()["jobId"])
        assert data["status"] == "erro"
        assert data["resultado"]["erro"] == 1 and data["resultado"]["pendente"] == 1
        assert data["resultado"]["ok"] == 0 and data["progress"]["processed"] == 2
        assert "test-secret" not in str(data) + caplog.text
        assert "test-user" not in str(data) + caplog.text


def test_cancel_and_reject_concurrent_job(client, monkeypatch):
    entered = threading.Event()
    def authenticate(c, cfg, event, step):
        entered.set()
        while not event.wait(.02):
            pass
        check_cancel(event)
    monkeypatch.setattr(sat_automacao, "autenticar_cliente", authenticate)
    client.post("/clientes", json={"clientes": [customer()]})
    jobid = client.post("/executar", json={}).json()["jobId"]
    assert entered.wait(2)
    assert client.post("/executar", json={}).status_code == 409
    assert client.post(f"/executar/{jobid}/cancelar").json()["ok"]
    assert wait_job(client, jobid)["status"] == "cancelado"


def test_dates_validated_before_start(client):
    client.post("/clientes", json={"clientes": [customer()]})
    assert client.post("/executar", json={"dataInicio": "invalid", "dataFim": "invalid"}).status_code == 400
    assert not server.JOBS


def test_no_certificate_or_download_mode(client):
    client.post("/clientes", json={"clientes": [customer()]})
    assert client.post("/executar", json={"tipoLogin": "certificado"}).status_code == 400
    assert client.post("/executar", json={"modo": "download"}).status_code == 400


def test_validation_does_not_echo_request_secrets(client, caplog):
    response = client.post("/clientes", json=[{"senha_sat": "do-not-echo"}])
    assert response.status_code == 422
    assert "do-not-echo" not in response.text + caplog.text


def test_credential_write_failure_is_not_reported_as_saved(client, monkeypatch, caplog):
    def fail(*a):
        raise OSError("write-error test-secret")
    monkeypatch.setattr(server, "_salvar_credenciais_locais", fail)
    response = client.post("/clientes", json={"clientes": [customer()]})
    assert response.status_code == 500
    assert "test-secret" not in response.text + caplog.text


def test_remote_sync_never_sends_credentials(client, monkeypatch):
    sent = []
    monkeypatch.setattr(server, "_clientes_remotos_ativos", lambda: True)
    def remote(op, key, clientes=None):
        sent.extend(clientes or [])
        return {"ok": True, "salvos": 1}
    monkeypatch.setattr(server, "_clientes_remote_call", remote)
    assert client.post("/clientes", json={"clientes": [customer()]}).status_code == 200
    assert sent == [{"documento": "12345678901", "nome": "Empresa Teste", "ativo": True}]


def test_selector_config_round_trip_and_official_url_fixed(client):
    selector = 'a[data-label="observado"]'
    response = client.post("/config", json={"SAT_SELECTOR_LOGIN_OK": selector,
                                           "SAT_LOGIN_URL": "https://example.invalid/"})
    assert response.status_code == 200
    assert server.config.SAT_SELECTOR_LOGIN_OK == selector
    assert server.config.SAT_LOGIN_URL == "https://sat.sef.sc.gov.br/tax.NET/Login.aspx"
    assert client.post("/config", json={"SAT_SELECTOR_LOGIN_OK": ""}).status_code == 200
