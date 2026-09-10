from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.automation import sat_auth as auth
from app.config.config_defaults import default_values, SAT_LOGIN_URL


def selectors():
    return {k: v for k, v in default_values().items() if k.startswith("SAT_SELECTOR_")}


def page_double():
    """Dublê do protocolo Playwright, não um HTML fictício do portal."""
    page = MagicMock()
    page.url = SAT_LOGIN_URL
    page.is_closed.return_value = False
    page.goto.return_value.status = 200
    fields = {}
    for key, selector in selectors().items():
        if selector:
            loc = MagicMock()
            loc.count.return_value = 1
            loc.is_visible.return_value = key != "SAT_SELECTOR_SELECAO_USUARIO"
            loc.nth.return_value = loc
            fields[selector] = loc
    body = MagicMock()
    body.inner_text.return_value = "Acesso com senha"
    fields["body"] = body
    page.locator.side_effect = lambda selector: fields[selector]
    return page, fields


def test_initial_hidden_selection_is_not_an_active_step():
    page, _ = page_double()
    assert auth.detectar_pagina(page, selectors()) is None


def test_visible_selection_has_no_false_success():
    page, fields = page_double()
    fields[selectors()["SAT_SELECTOR_SELECAO_USUARIO"]].is_visible.return_value = True
    result = auth.detectar_pagina(page, selectors())
    assert result.requires_user_selection and not result.success


def test_positive_indicator_must_be_configured_and_login_form_absent():
    page, fields = page_double()
    # O nome é só uma chave do dublê; não é seletor implementado para o SAT.
    fields["observed_indicator"] = MagicMock()
    fields["observed_indicator"].count.return_value = 1
    fields["observed_indicator"].nth.return_value.is_visible.return_value = True
    cfg = {**selectors(), "SAT_SELECTOR_LOGIN_OK": "observed_indicator"}
    assert auth.detectar_pagina(page, cfg) is None
    fields[cfg["SAT_SELECTOR_SENHA"]].is_visible.return_value = False
    assert auth.detectar_pagina(page, cfg).success


@pytest.mark.parametrize("text,kind", [
    ("Usuário ou senha inválidos", "INVALID_CREDENTIALS"),
    ("Server Error in application", "PORTAL_ERROR"),
    ("Esqueci minha senha", None),
])
def test_only_explicit_error_messages(text, kind):
    assert auth.erro_texto(text) == kind


def test_fill_exception_never_leaks_secret(caplog):
    page, fields = page_double()
    fields[selectors()["SAT_SELECTOR_SENHA"]].fill.side_effect = RuntimeError("test-secret-xyz")
    result = auth.login_sat(page, "test-user", "test-secret-xyz")
    assert result.error_type == "LAYOUT_CHANGED"
    assert "test-secret-xyz" not in str(result) + caplog.text
    fields[selectors()["SAT_SELECTOR_ENTRAR"]].click.assert_not_called()


def test_cancel_before_click():
    import threading
    event = threading.Event()
    page, fields = page_double()
    fields[selectors()["SAT_SELECTOR_SENHA"]].fill.side_effect = lambda *a, **k: event.set()
    with pytest.raises(auth.ExecucaoCancelada):
        auth.login_sat(page, "user", "secret", cancel_event=event)
    fields[selectors()["SAT_SELECTOR_ENTRAR"]].click.assert_not_called()


def test_redirect_to_other_origin_does_not_receive_credentials():
    page, fields = page_double()
    page.url = "https://example.invalid/"
    assert auth.login_sat(page, "user", "secret").error_type == "ADDITIONAL_STEP"
    fields[selectors()["SAT_SELECTOR_USUARIO"]].fill.assert_not_called()


def test_click_is_not_success(monkeypatch):
    page, fields = page_double()
    monkeypatch.setattr(auth.time, "monotonic", MagicMock(side_effect=[0, 100]))
    result = auth.login_sat(page, "user", "secret")
    assert result.error_type == "UNCONFIRMED"
    fields[selectors()["SAT_SELECTOR_ENTRAR"]].click.assert_called_once()


def test_postback_is_polled_until_result(monkeypatch):
    page, _ = page_double()
    detect = MagicMock(side_effect=[None, auth.resultado("INVALID_CREDENTIALS")])
    monkeypatch.setattr(auth, "detectar_pagina", detect)
    assert auth.login_sat(page, "user", "secret").error_type == "INVALID_CREDENTIALS"
    assert detect.call_count == 2


def test_popup_selection_is_detected(monkeypatch):
    page, fields = page_double()
    popup, _ = page_double()
    callbacks = {}
    page.context.on.side_effect = lambda event, callback: callbacks.update({event: callback})
    fields[selectors()["SAT_SELECTOR_ENTRAR"]].click.side_effect = lambda **k: callbacks["page"](popup)
    monkeypatch.setattr(auth, "detectar_pagina", lambda p, _: auth.resultado("USER_SELECTION_REQUIRED") if p is popup else None)
    assert auth.login_sat(page, "user", "secret").requires_user_selection


def test_http_error_never_fills():
    page, fields = page_double()
    page.goto.return_value.status = 503
    assert auth.login_sat(page, "user", "secret").error_type == "PORTAL_ERROR"
    fields[selectors()["SAT_SELECTOR_USUARIO"]].fill.assert_not_called()
