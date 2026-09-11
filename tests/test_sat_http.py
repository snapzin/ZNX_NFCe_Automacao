"""Fixtures mínimas do protocolo observado; nenhum dado fiscal ou segredo real."""
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests
from bs4 import BeautifulSoup

from app.automation.sat_http import ClienteSATHTTP, PaginaSAT, ErroSATHTTP, campos_formulario
from app.automation.sat_auth import ExecucaoCancelada
from app.automation.sat_session import CredenciaisSAT
from app.config.config_defaults import default_values, SAT_LOGIN_URL


LOGIN = '''<form action="./Login.aspx"><input type="hidden" name="__VIEWSTATE" value="state-one">
<div id="LoginContainers"><input id="Body_pnlMain_rptLoginPanels_tbxUsername_0" name="observed$user">
<input id="Body_pnlMain_rptLoginPanels_tbxUserPassword_0" type="password" name="observed$password">
<a id="Body_pnlMain_rptLoginPanels_btnLogin_0" href="javascript:__doPostBack('observed$login','')">Entrar</a></div>
<div style="display:none"><h4 class="tit-pan-acc">Selecione o usuário</h4></div></form>'''
APPS = '''<form><a id="Body_ApplicationMasterFooter_hlkPolicy">Política</a>
<div id="Body_ApplicationMasterHeader_ApplicationMasterSearchAppsInput_txtSearchApp"></div>
<a onclick="window.open('Go.ashx?app=DFE00116&amp;source=7');return false;">NFe / NFCe - Consulta</a></form>'''
CONSULTA = '''<form><select id="Body_Main_Main_sepConsultaNfpe_selTipoDocumento"><option value="20">NFC-e</option></select>
<div id="Body_Main_Main_sepConsultaNfpe_capValidacao" class="mandatory"></div>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script></form>'''


def response(html="", url=SAT_LOGIN_URL, status=200, location=None):
    r = requests.Response()
    r.status_code = status
    r.url = url
    r.encoding = "utf-8"
    r._content = html.encode()
    if location:
        r.headers["Location"] = location
    return r


def client(responses, event=None):
    transport = MagicMock()
    transport.request.side_effect = responses
    return ClienteSATHTTP(SimpleNamespace(**default_values()), CredenciaisSAT("test-user", "secret-password"),
                          event, transport=transport)


def test_login_posts_real_form_state_once_without_browser(caplog):
    c = client([response(LOGIN), response(APPS, url="https://sat.sef.sc.gov.br/tax.NET/Apps.aspx")])
    assert c.autenticar().success
    calls = c.transport.request.call_args_list
    assert [x.args[0] for x in calls] == ["GET", "POST"]
    data = dict(calls[1].kwargs["data"])
    assert data == {"__VIEWSTATE":"state-one", "observed$user":"test-user", "observed$password":"secret-password",
                    "__EVENTTARGET":"observed$login", "__EVENTARGUMENT":""}
    assert c.credenciais is None
    assert "secret-password" not in caplog.text + repr(c.page)


def test_hidden_profile_selection_is_not_required():
    c = client([])
    c.page = PaginaSAT(SAT_LOGIN_URL, APPS + '<div style="display: none"><h4 class="tit-pan-acc">Perfil</h4></div>')
    assert c.detectar_autenticacao().success
    c.page = PaginaSAT(SAT_LOGIN_URL, APPS + '<h4 class="tit-pan-acc">Perfil</h4>')
    assert c.detectar_autenticacao().requires_user_selection


@pytest.mark.parametrize("message,kind", [("Usuário ou senha inválidos", "INVALID_CREDENTIALS"),
    ("Serviço indisponível", "PORTAL_ERROR"), ("Outra etapa", "ADDITIONAL_STEP")])
def test_failed_login_has_structured_result_without_retry(message, kind):
    c = client([response(LOGIN), response(f"<p>{message}</p>")])
    assert c.autenticar().error_type == kind
    assert c.transport.request.call_count == 2


@pytest.mark.parametrize("url", ["http://sat.sef.sc.gov.br/", "https://example.invalid/", "https://sat.sef.sc.gov.br:444/"])
def test_redirect_cannot_forward_credentials_to_another_origin(url):
    c = client([response(status=307, location=url)])
    with pytest.raises(ErroSATHTTP):
        c.request("POST", SAT_LOGIN_URL, data={"senha":"secret"})
    assert c.transport.request.call_count == 1


def test_post_redirect_get_clears_form_data():
    c = client([response(status=302, location="Apps.aspx"), response(APPS)])
    c.request("POST", SAT_LOGIN_URL, data={"senha":"secret"})
    assert c.transport.request.call_args.args[0] == "GET"
    assert "data" not in c.transport.request.call_args.kwargs


def test_opens_observed_application_and_stops_at_captcha_once():
    c = client([response(CONSULTA)])
    c.page = PaginaSAT("https://sat.sef.sc.gov.br/tax.NET/Apps.aspx", APPS)
    c.abrir_consulta_nfce()
    c.abrir_consulta_nfce()
    assert c.transport.request.call_count == 1
    assert c.transport.request.call_args.args[1] == "https://sat.sef.sc.gov.br/tax.NET/Go.ashx?app=DFE00116&source=7"
    assert c.exige_validacao_humana()


def test_cancelled_request_never_uses_network():
    event = threading.Event()
    event.set()
    c = client([], event)
    with pytest.raises(ExecucaoCancelada):
        c.autenticar()
    c.transport.request.assert_not_called()


def test_transport_errors_do_not_reveal_request_details(caplog):
    c = client([requests.ConnectionError("secret-password")])
    result = c.autenticar()
    assert result.error_type == "PORTAL_ERROR"
    assert "secret-password" not in repr(result) + caplog.text


def test_successful_controls_preserve_duplicates_and_checked_options():
    form = BeautifulSoup('''<form><input type="hidden" name="state" value="a"><input type="hidden" name="state" value="b">
    <input type="radio" name="radio" value="0"><input type="radio" name="radio" value="1" checked>
    <input disabled name="ignore"><input type="submit" name="button"><select name="doc"><option value="3">NF-e</option>
    <option value="20" selected>NFC-e</option></select></form>''', "html.parser").form
    assert campos_formulario(form) == [("state","a"),("state","b"),("radio","1"),("doc","20")]


def test_postback_uses_latest_hidden_state():
    c = client([response(LOGIN.replace("state-one", "state-two")), response(LOGIN)])
    c.page = PaginaSAT(SAT_LOGIN_URL, LOGIN)
    c.postback("#Body_pnlMain_rptLoginPanels_btnLogin_0")
    c.postback("#Body_pnlMain_rptLoginPanels_btnLogin_0")
    assert dict(c.transport.request.call_args.kwargs["data"])["__VIEWSTATE"] == "state-two"


def test_hidden_validation_error_does_not_override_authenticated_page():
    c = client([])
    c.page = PaginaSAT(SAT_LOGIN_URL, APPS + '<span style="display:none">Senha inválida</span>')
    assert c.detectar_autenticacao().success
    c.page = PaginaSAT("https://example.invalid/", APPS)
    assert not c.detectar_autenticacao().success
