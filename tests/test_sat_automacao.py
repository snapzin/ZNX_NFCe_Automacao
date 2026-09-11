from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
import threading
from unittest.mock import MagicMock
import pytest
from app.automation.sat_auth import resultado, ExecucaoCancelada
from app.automation.sat_automacao import preparar_parametros, executar_local
from app.automation.sat_downloader import ResultadoDownload, FluxoNaoMapeado
from app.automation.sat_session import CredenciaisSAT, abrir_sessao
from app.config.config_defaults import default_values


def clients():
    return [{"documento": "12345678000195", "nome": "Empresa A", "ativo": True},
            {"documento": "22345678000195", "nome": "Empresa B", "ativo": True}]


def test_previous_month_january_and_leap_year():
    p = preparar_parametros(clientes=clients(), hoje=date(2026, 1, 10))
    assert (p.data_inicio, p.data_fim) == ("2025-12-01", "2025-12-31")
    assert preparar_parametros(clientes=clients(), hoje=date(2024, 3, 10)).data_fim == "2024-02-29"


@pytest.mark.parametrize("start,end", [("31/02/2026", "01/03/2026"),
    ("02/03/2026", "01/03/2026"), ("01/03/2026", None)])
def test_invalid_period(start, end):
    with pytest.raises(ValueError):
        preparar_parametros(start, end, clientes=clients())


def test_only_selected_active_clients():
    data = clients()
    data[1]["ativo"] = False
    assert len(preparar_parametros(clientes=data).clientes) == 1
    with pytest.raises(ValueError):
        preparar_parametros(clientes=data, cnpjs=[data[1]["documento"]])


@pytest.fixture
def session():
    obj = MagicMock()
    obj.autenticar.return_value = resultado("SUCCESS")
    obj.abrir_consulta_nfce.side_effect = FluxoNaoMapeado()
    return obj


def factory(session):
    @contextmanager
    def open_session(*args):
        yield session
    return open_session


def test_one_login_same_session_for_all_clients_despite_error(session, caplog):
    page = session
    called = []
    def download(current, **args):
        assert current is page
        called.append(args["cliente"]["documento"])
        if len(called) == 1:
            raise RuntimeError("secret-password")
        return ResultadoDownload(3)
    results = executar_local(preparar_parametros(clientes=clients()), config=SimpleNamespace(PASTA_SAIDA="Downloads"),
                             session_factory=factory(session), download=download)
    assert [r.status for r in results] == ["erro", "ok"]
    assert results[1].documentos == 3
    assert called == [c["documento"] for c in clients()]
    session.autenticar.assert_called_once()
    assert "secret-password" not in caplog.text + repr(results)


def test_profile_selection_blocks_all_consultations(session):
    session.autenticar.return_value = resultado("USER_SELECTION_REQUIRED")
    download = MagicMock()
    results = executar_local(preparar_parametros(clientes=clients()), config=SimpleNamespace(),
                             session_factory=factory(session), download=download)
    assert all(r.status == "pendente" and not r.authenticated for r in results)
    download.assert_not_called()
    session.autenticar.assert_called_once()


def test_login_success_is_not_download_success(session):
    results = executar_local(preparar_parametros(clientes=clients()), config=SimpleNamespace(PASTA_SAIDA="Downloads"),
                             session_factory=factory(session))
    assert all(r.status == "pendente" and r.authenticated and r.documentos == 0 for r in results)
    assert all(r.error_type == "FLOW_NOT_MAPPED" for r in results)


def test_cancel_does_not_consult_next_client(session):
    event = threading.Event()
    calls = []
    def download(*args, **kwargs):
        calls.append(1)
        event.set()
        return ResultadoDownload(1)
    with pytest.raises(ExecucaoCancelada):
        executar_local(preparar_parametros(clientes=clients()), event,
                       config=SimpleNamespace(PASTA_SAIDA="Downloads"), session_factory=factory(session), download=download)
    assert len(calls) == 1


def test_credentials_not_in_repr():
    credentials = CredenciaisSAT("private-user", "secret-password")
    credentials.validar()
    assert "secret-password" not in repr(credentials)
    assert "private-user" not in repr(credentials)


@pytest.mark.parametrize("usuario,senha", [("", "secret"), ("user", ""), (None, "secret"), ("user", [])])
def test_requires_username_and_password(usuario, senha):
    with pytest.raises(ValueError):
        CredenciaisSAT(usuario, senha).validar()


def test_single_http_session_without_browser(monkeypatch):
    transport = MagicMock()
    monkeypatch.setattr("app.automation.sat_http.requests.Session", lambda: transport)
    with abrir_sessao(SimpleNamespace(**default_values()), CredenciaisSAT("test-user", "secret"), None, None) as session:
        assert session.transport is transport
    transport.close.assert_called_once()
    assert session.credenciais is None


def test_captcha_is_pending_and_does_not_report_downloads(session):
    session.abrir_consulta_nfce.side_effect = None
    session.exige_validacao_humana.return_value = True
    results = executar_local(preparar_parametros(clientes=clients()), config=SimpleNamespace(PASTA_SAIDA="Downloads"),
                             session_factory=factory(session))
    assert all(r.error_type == "HUMAN_VALIDATION_REQUIRED" and r.status == "pendente" for r in results)
    assert all(r.authenticated and not r.success and r.documentos == 0 for r in results)
