from datetime import date
from types import SimpleNamespace
import threading

import pytest

from app.automation.sat_auth import resultado, ExecucaoCancelada
from app.automation.sat_automacao import preparar_parametros, executar_local


def clients():
    return [{"documento": "12345678901", "nome": "Empresa A", "ativo": True,
             "usuario_sat": "test-user", "senha_sat": "secret"},
            {"documento": "12345678902", "nome": "Empresa B", "ativo": True,
             "usuario_sat": "test-user-b", "senha_sat": "secret-b"}]


def test_previous_month_january_and_leap_year():
    p = preparar_parametros(clientes=clients(), hoje=date(2026, 1, 10))
    assert (p.data_inicio, p.data_fim) == ("2025-12-01", "2025-12-31")
    p = preparar_parametros(clientes=clients(), hoje=date(2024, 3, 10))
    assert p.data_fim == "2024-02-29"


@pytest.mark.parametrize("start,end", [("31/02/2026", "01/03/2026"),
    ("02/03/2026", "01/03/2026"), ("01/03/2026", None)])
def test_invalid_period(start, end):
    with pytest.raises(ValueError):
        preparar_parametros(start, end, clientes=clients())


def test_only_selected_active_clients():
    data = clients()
    data[1]["ativo"] = False
    p = preparar_parametros(clientes=data)
    assert len(p.clientes) == 1
    assert "secret" not in repr(p)
    with pytest.raises(ValueError):
        preparar_parametros(clientes=data, cnpjs=[data[1]["documento"]])


def test_company_error_does_not_stop_next_company(caplog):
    def authenticate(c, *args):
        if c["nome"] == "Empresa A":
            raise RuntimeError("secret browser failure")
        return resultado("SUCCESS")
    results = executar_local(preparar_parametros(clientes=clients()),
                             config=SimpleNamespace(), authenticate=authenticate)
    assert [r.status for r in results] == ["erro", "ok"]
    assert "secret" not in caplog.text + repr(results)


def test_profile_selection_counts_as_pending():
    results = executar_local(preparar_parametros(clientes=clients()), config=SimpleNamespace(),
                             authenticate=lambda *a: resultado("USER_SELECTION_REQUIRED"))
    assert all(r.status == "pendente" and not r.success for r in results)


def test_cancel_does_not_start_next_client():
    event = threading.Event()
    calls = []
    def authenticate(c, *args):
        calls.append(c["documento"])
        event.set()
        return resultado("SUCCESS")
    with pytest.raises(ExecucaoCancelada):
        executar_local(preparar_parametros(clientes=clients()), event,
                       config=SimpleNamespace(), authenticate=authenticate)
    assert len(calls) == 1
