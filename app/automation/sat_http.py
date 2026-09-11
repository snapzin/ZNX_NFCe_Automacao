"""Sessão HTTP do SAT. Cookies e campos ASP.NET permanecem somente em memória."""
from dataclasses import dataclass, field
import re
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from app.automation.sat_auth import check_cancel, erro_texto, resultado
from app.config.config_defaults import SAT_LOGIN_URL


class ErroSATHTTP(RuntimeError):
    def __init__(self, message="Falha de comunicação HTTP com o SAT"):
        super().__init__(message)


class ValidacaoHumanaNecessaria(RuntimeError):
    pass


def origem_permitida(url):
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.hostname == "sat.sef.sc.gov.br"
            and parsed.port in (None, 443) and not parsed.username and not parsed.password)


def visivel_html(element):
    if element is None:
        return False
    for parent in [element, *element.parents]:
        style = re.sub(r"\s+", "", parent.get("style", "").lower())
        if parent.has_attr("hidden") or "display:none" in style or "visibility:hidden" in style:
            return False
    return True


@dataclass(repr=False)
class PaginaSAT:
    url: str
    html: str = field(repr=False)

    @property
    def soup(self):
        return BeautifulSoup(self.html, "html.parser")


def campos_formulario(form):
    """Controles bem sucedidos do formulário; preserva todos os hidden recebidos."""
    fields = []
    for element in form.select("input[name], select[name], textarea[name]"):
        if element.has_attr("disabled"):
            continue
        kind = element.get("type", "text").lower()
        if kind in {"submit", "button", "image", "reset", "file"}:
            continue
        if kind in {"checkbox", "radio"} and not element.has_attr("checked"):
            continue
        name = element["name"]
        if element.name == "select":
            options = element.select("option[selected]")
            if not options and not element.has_attr("multiple"):
                options = element.select("option")[:1]
            fields.extend((name, o.get("value", o.get_text())) for o in options)
        else:
            fields.append((name, element.get_text() if element.name == "textarea" else element.get("value", "")))
    return fields


class ClienteSATHTTP:
    def __init__(self, config, credenciais, cancel_event=None, on_step=None, transport=None):
        self.config = config
        self.credenciais = credenciais
        self.cancel_event = cancel_event
        self.on_step = on_step or (lambda _: None)
        self.transport = transport or requests.Session()
        self.transport.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,*/*"})
        self.page = None
        self.consulta_aberta = False

    def request(self, method, url, **kwargs):
        for _ in range(8):
            check_cancel(self.cancel_event)
            if not origem_permitida(url):
                raise ErroSATHTTP("Redirecionamento fora da origem SAT observada")
            try:
                response = self.transport.request(method, url, allow_redirects=False,
                                                  timeout=(15, int(getattr(self.config, "SAT_HTTP_TIMEOUT_S", 60))), **kwargs)
            except requests.RequestException:
                check_cancel(self.cancel_event)
                raise ErroSATHTTP() from None
            check_cancel(self.cancel_event)
            if response.status_code in {301, 302, 303, 307, 308}:
                target = urljoin(url, response.headers.get("Location", ""))
                if not response.headers.get("Location") or not origem_permitida(target):
                    raise ErroSATHTTP("Redirecionamento fora da origem SAT observada")
                if response.status_code in {301, 302, 303}:
                    method, kwargs = "GET", {}
                url = target
                continue
            if response.status_code >= 400:
                raise ErroSATHTTP("Portal SAT retornou erro HTTP")
            return response
        raise ErroSATHTTP("Número excessivo de redirecionamentos do SAT")

    def abrir(self, url):
        response = self.request("GET", url)
        self.page = PaginaSAT(response.url, response.text)
        return self.page

    def postback(self, control, overrides=None):
        soup = self.page.soup
        element = soup.select_one(control)
        if element is None:
            raise ErroSATHTTP("Controle esperado não encontrado no HTML do SAT")
        form = element.find_parent("form")
        if form is None:
            raise ErroSATHTTP("Formulário SAT não encontrado")
        script = element.get("href", "") + " " + element.get("onclick", "")
        if "window.open" in element.get("onclick", ""):
            raise ErroSATHTTP("Ação abre outra aplicação; use a navegação observada")
        match = re.search(r"__doPostBack\('([^']*)','([^']*)'\)", script)
        if not match:
            match = re.search(r'WebForm_PostBackOptions\("([^\"]*)",\s*"([^\"]*)"', script)
        values = dict(overrides or {})
        if match:
            values.update(__EVENTTARGET=match[1], __EVENTARGUMENT=match[2])
        elif element.name in {"input", "button"} and element.get("name"):
            values[element["name"]] = element.get("value", "")
        else:
            raise ErroSATHTTP("Ação JavaScript do SAT ainda não mapeada")
        fields = [(k, v) for k, v in campos_formulario(form) if k not in values]
        fields.extend(values.items())
        target = urljoin(self.page.url, form.get("action", ""))
        response = self.request("POST", target, data=fields, headers={"Referer": self.page.url})
        self.page = PaginaSAT(response.url, response.text)
        return self.page

    def autenticar(self):
        try:
            self.credenciais.validar()
            self.on_step("Abrindo SAT por HTTP")
            page = self.abrir(SAT_LOGIN_URL)
            soup = page.soup
            user = soup.select_one(self.config.SAT_SELECTOR_USUARIO)
            password = soup.select_one(self.config.SAT_SELECTOR_SENHA)
            if user is None or password is None or not user.get("name") or not password.get("name"):
                return resultado("LAYOUT_CHANGED")
            self.on_step("Realizando login por HTTP")
            self.postback(self.config.SAT_SELECTOR_ENTRAR, {
                user["name"]: self.credenciais.usuario.strip(), password["name"]: self.credenciais.senha,
            })
            return self.detectar_autenticacao()
        except ValueError:
            return resultado("MISSING_CREDENTIALS")
        except ErroSATHTTP:
            return resultado("PORTAL_ERROR")
        finally:
            self.credenciais = None

    def detectar_autenticacao(self):
        if not origem_permitida(self.page.url):
            return resultado("ADDITIONAL_STEP")
        soup = self.page.soup
        if any(visivel_html(el) for el in soup.select(self.config.SAT_SELECTOR_SELECAO_USUARIO)):
            return resultado("USER_SELECTION_REQUIRED")
        text_soup = self.page.soup
        for element in list(text_soup.find_all(True)):
            if element.parent is not None and (element.name in {"script", "style", "noscript", "input", "textarea"}
                                               or not visivel_html(element)):
                element.decompose()
        error = erro_texto(text_soup.get_text(" ", strip=True))
        if error:
            return resultado(error)
        if (soup.select_one("#Body_ApplicationMasterFooter_hlkPolicy")
                and soup.select_one("#Body_ApplicationMasterHeader_ApplicationMasterSearchAppsInput_txtSearchApp")
                and not any(visivel_html(e) for e in soup.select(self.config.SAT_SELECTOR_FORMULARIO_LOGIN))):
            return resultado("SUCCESS")
        return resultado("ADDITIONAL_STEP")

    def abrir_consulta_nfce(self):
        if self.consulta_aberta:
            return self.page
        link = next((e for e in self.page.soup.select("a[onclick]")
                     if e.get_text(" ", strip=True) == "NFe / NFCe - Consulta"), None)
        match = re.search(r"window.open\('([^']+)'\)", link.get("onclick", "")) if link else None
        if not match:
            raise ErroSATHTTP("Aplicação NFe / NFCe - Consulta não localizada no menu autorizado")
        self.abrir(urljoin(self.page.url, match[1]))
        if self.page.soup.select_one("#Body_Main_Main_sepConsultaNfpe_selTipoDocumento") is None:
            raise ErroSATHTTP("SAT não apresentou o formulário de consulta observado")
        self.consulta_aberta = True
        return self.page

    def exige_validacao_humana(self):
        soup = self.page.soup
        field = soup.select_one("#Body_Main_Main_sepConsultaNfpe_capValidacao")
        return visivel_html(field) and any("challenges.cloudflare.com/turnstile/" in s.get("src", "")
                                           for s in soup.select("script[src]"))

    def close(self):
        self.page = None
        self.credenciais = None
        self.transport.close()
