"""Login SAT via navegador. Nenhuma URL interna ou seleção de perfil presumida."""
from __future__ import annotations

import time
import unicodedata
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from app.config.config_defaults import SAT_LOGIN_URL, default_values


class ExecucaoCancelada(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthResult:
    success: bool = False
    requires_user_selection: bool = False
    error_type: str = ""
    message: str = ""


def resultado(tipo: str) -> AuthResult:
    messages = {
        "SUCCESS": "Login realizado",
        "USER_SELECTION_REQUIRED": "SAT solicita seleção de usuário/perfil; etapa pendente de mapeamento",
        "INVALID_CREDENTIALS": "Usuário ou senha inválidos",
        "PORTAL_ERROR": "Erro do portal SAT ou falha de comunicação",
        "ADDITIONAL_STEP": "Tela/etapa adicional; autenticação ainda não confirmada",
        "UNCONFIRMED": "Resposta do login não confirmada; observar a página com a conta de teste",
        "LAYOUT_CHANGED": "Campos de acesso não encontrados; revisar os seletores do SAT",
        "MISSING_CREDENTIALS": "Usuário e senha SAT são obrigatórios",
        "BROWSER_ERROR": "Não foi possível iniciar ou controlar o navegador",
    }
    return AuthResult(tipo == "SUCCESS", tipo == "USER_SELECTION_REQUIRED",
                      "" if tipo == "SUCCESS" else tipo, messages[tipo])


def check_cancel(event) -> None:
    if event is not None and event.is_set():
        raise ExecucaoCancelada("Execução cancelada pelo usuário")


def _normalizar(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn")


def erro_texto(text: str) -> str | None:
    """Reconhece apenas mensagens explícitas; nunca devolve texto bruto do portal."""
    text = _normalizar(text)
    if any(t in text for t in ("usuario ou senha invalid", "credenciais invalid",
                               "senha incorreta", "senha invalida")):
        return "INVALID_CREDENTIALS"
    if any(t in text for t in ("erro interno do servidor", "server error in",
                               "servico indisponivel", "service unavailable")):
        return "PORTAL_ERROR"
    return None


def _visivel(page, selector: str) -> bool:
    if not selector:
        return False
    items = page.locator(selector)
    return any(items.nth(i).is_visible() for i in range(items.count()))


def detectar_pagina(page, selectors: dict) -> AuthResult | None:
    # inner_text considera a renderização; o HTML inicial contém seleção oculta.
    if _visivel(page, selectors["SAT_SELECTOR_SELECAO_USUARIO"]):
        return resultado("USER_SELECTION_REQUIRED")
    if _visivel(page, selectors["SAT_SELECTOR_CREDENCIAIS_INVALIDAS"]):
        return resultado("INVALID_CREDENTIALS")
    if _visivel(page, selectors["SAT_SELECTOR_ERRO_PORTAL"]):
        return resultado("PORTAL_ERROR")
    body = page.locator("body").inner_text(timeout=1000)
    error = erro_texto(body)
    if error:
        return resultado(error)
    # URL diferente e desaparecimento do formulário NÃO confirmam autenticação.
    # O indicador positivo precisa ser observado/configurado com uma conta real.
    if (_visivel(page, selectors["SAT_SELECTOR_LOGIN_OK"])
            and not _visivel(page, selectors["SAT_SELECTOR_SENHA"])):
        return resultado("SUCCESS")
    return None


def login_sat(page, usuario: str, senha: str, *, config=None, cancel_event=None,
              on_step: Callable[[str], None] | None = None) -> AuthResult:
    """Faz um único envio de credenciais e acompanha postbacks, janelas e diálogos.

    O chamador é dono do navegador/contexto. Não grava HTML, screenshots, traces,
    URLs de retorno, mensagens de exceções ou conteúdo de campos secretos.
    """
    check_cancel(cancel_event)
    if not usuario.strip() or not senha:
        return resultado("MISSING_CREDENTIALS")
    defaults = default_values()
    selectors = {k: str(getattr(config, k, v)) for k, v in defaults.items()
                 if k.startswith("SAT_SELECTOR_")}
    action_ms = max(1000, min(15000, int(getattr(config, "PLAYWRIGHT_TIMEOUT_MS", 15000))))
    response_s = max(1, int(getattr(config, "PLAYWRIGHT_LOGIN_TIMEOUT_S", 45)))
    step = on_step or (lambda _: None)
    pages = [page]
    dialogs = []
    http_errors = set()
    listeners = []

    def on_dialog(dialog):
        dialogs.append(erro_texto(dialog.message) or "ADDITIONAL_STEP")
        dialog.dismiss()

    def on_response(response):
        if response.status >= 400 and response.request.is_navigation_request():
            http_errors.add(response.frame.page)

    def watch(new_page):
        if new_page not in pages:
            pages.append(new_page)
        new_page.on("dialog", on_dialog)
        new_page.on("response", on_response)
        listeners.append(new_page)

    watch(page)
    page.context.on("page", watch)
    try:
        step("Abrindo SAT")
        try:
            response = page.goto(SAT_LOGIN_URL, wait_until="domcontentloaded", timeout=action_ms)
            if response and response.status >= 400:
                return resultado("PORTAL_ERROR")
        except Exception:
            check_cancel(cancel_event)
            return resultado("PORTAL_ERROR")
        check_cancel(cancel_event)
        # Não preencher credenciais numa página redirecionada para outra origem.
        if urlsplit(page.url).hostname != urlsplit(SAT_LOGIN_URL).hostname:
            return resultado("ADDITIONAL_STEP")
        try:
            for key in ("SAT_SELECTOR_USUARIO", "SAT_SELECTOR_SENHA", "SAT_SELECTOR_ENTRAR"):
                field = page.locator(selectors[key])
                field.wait_for(state="visible", timeout=action_ms)
                check_cancel(cancel_event)
            step("Preenchendo credenciais")
            page.locator(selectors["SAT_SELECTOR_USUARIO"]).fill(usuario, timeout=action_ms)
            check_cancel(cancel_event)
            page.locator(selectors["SAT_SELECTOR_SENHA"]).fill(senha, timeout=action_ms)
        except Exception:
            check_cancel(cancel_event)
            return resultado("LAYOUT_CHANGED")
        check_cancel(cancel_event)
        step("Realizando login")
        try:
            # Aciona o __doPostBack real do link Entrar, preservando hidden/state.
            page.locator(selectors["SAT_SELECTOR_ENTRAR"]).click(timeout=action_ms)
        except Exception:
            # O clique pode disparar navegação antes de completar a espera.
            # Observar o resultado; não repetir o envio nem revelar a exceção.
            check_cancel(cancel_event)
        step("Aguardando resposta do SAT")
        deadline = time.monotonic() + response_s
        while time.monotonic() < deadline:
            check_cancel(cancel_event)
            if dialogs:
                return resultado(dialogs[-1])
            active = [p for p in pages if not p.is_closed()]
            if not active:
                return resultado("BROWSER_ERROR")
            found = []
            for candidate in reversed(active):
                if candidate in http_errors:
                    found.append(resultado("PORTAL_ERROR"))
                    continue
                try:
                    detected = detectar_pagina(candidate, selectors)
                    if detected:
                        found.append(detected)
                except Exception:
                    pass  # DOM/contexto pode desaparecer durante um postback.
            if found:
                # Etapas extras/erros têm precedência sobre indicadores de sucesso.
                return next((r for r in found if not r.success), found[0])
            active[-1].wait_for_timeout(200)
        check_cancel(cancel_event)
        active = [p for p in pages if not p.is_closed()]
        for candidate in active:
            try:
                if (candidate != page or candidate.url != SAT_LOGIN_URL
                        or not _visivel(candidate, selectors["SAT_SELECTOR_SENHA"])):
                    return resultado("ADDITIONAL_STEP")
            except Exception:
                pass
        return resultado("UNCONFIRMED")
    except ExecucaoCancelada:
        raise
    except Exception:
        check_cancel(cancel_event)
        return resultado("BROWSER_ERROR")
    finally:
        page.context.remove_listener("page", watch)
        for observed in listeners:
            observed.remove_listener("dialog", on_dialog)
            observed.remove_listener("response", on_response)
