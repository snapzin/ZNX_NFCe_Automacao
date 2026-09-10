"""Orquestra empresas com o contrato de execução local usado pela API NFSe."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.automation.sat_auth import ExecucaoCancelada, check_cancel, login_sat, resultado

log = logging.getLogger("sat")


@dataclass
class Parametros:
    data_inicio: str
    data_fim: str
    clientes: list[dict] = field(repr=False)


@dataclass
class ResultadoCNPJ:
    cnpj: str
    nome: str
    status: str
    success: bool = False
    requires_user_selection: bool = False
    error_type: str = ""
    message: str = ""
    etapa: str = "login"
    documentos: int = 0


def preparar_parametros(data_inicio=None, data_fim=None, cnpjs=None, tipos=None,
                        clientes=None, *, hoje=None) -> Parametros:
    if bool(data_inicio) != bool(data_fim):
        raise ValueError("Informe data inicial e final juntas")
    if not data_inicio:
        fim = (hoje or date.today()).replace(day=1) - timedelta(days=1)
        inicio = fim.replace(day=1)
    else:
        def parse(value):
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value, fmt).date()
                except (ValueError, TypeError):
                    pass
            raise ValueError("Data inválida; use DD/MM/AAAA ou AAAA-MM-DD")
        inicio, fim = parse(data_inicio), parse(data_fim)
        if inicio > fim:
            raise ValueError("Data inicial deve ser menor ou igual à final")
    selected = [dict(c) for c in (clientes or []) if c.get("ativo", True)]
    if cnpjs:
        if not isinstance(cnpjs, list):
            raise ValueError("Filtro de documentos deve ser uma lista")
        docs = {re.sub(r"\D", "", str(c)) for c in cnpjs}
        selected = [c for c in selected if c["documento"] in docs]
    if not selected:
        raise ValueError("Nenhum cliente ativo selecionado")
    return Parametros(inicio.isoformat(), fim.isoformat(), selected)


def autenticar_cliente(cliente, config, cancel_event, on_step):
    from playwright.sync_api import sync_playwright
    browser = None
    try:
        with sync_playwright() as pw:
            options = {"headless": bool(config.PLAYWRIGHT_HEADLESS)}
            if config.CHROME_EXECUTABLE_PATH:
                options["executable_path"] = config.CHROME_EXECUTABLE_PATH
            elif config.CHROME_CHANNEL:
                options["channel"] = config.CHROME_CHANNEL
            browser = pw.chromium.launch(**options)
            try:
                # Contexto efêmero por empresa; cookies e sessões não se misturam.
                context = browser.new_context(accept_downloads=False)
                return login_sat(context.new_page(), cliente.get("usuario_sat", ""),
                                 cliente.get("senha_sat", ""), config=config,
                                 cancel_event=cancel_event, on_step=on_step)
            finally:
                browser.close()
    except ExecucaoCancelada:
        raise
    except Exception:
        return resultado("BROWSER_ERROR")


def executar_local(params, cancel_event=None, *, config=None, on_progress=None,
                   authenticate=None) -> list[ResultadoCNPJ]:
    if config is None:
        import config
    authenticate = authenticate or autenticar_cliente
    results = []
    total = len(params.clientes)
    for index, client in enumerate(params.clientes, 1):
        check_cancel(cancel_event)
        name = client["nome"]
        def step(message):
            log.info("[%s] %s", name, message)
            if on_progress:
                on_progress(index, total, client["documento"], name, message, results)
        step("Iniciando processamento")
        try:
            if not client.get("usuario_sat", "").strip() or not client.get("senha_sat"):
                auth = resultado("MISSING_CREDENTIALS")
            else:
                auth = authenticate(client, config, cancel_event, step)
        except ExecucaoCancelada:
            raise
        except Exception:
            auth = resultado("BROWSER_ERROR")
        check_cancel(cancel_event)
        pending = auth.error_type in {"USER_SELECTION_REQUIRED", "ADDITIONAL_STEP", "UNCONFIRMED"}
        status = "ok" if auth.success else "pendente" if pending else "erro"
        item = ResultadoCNPJ(client["documento"], name, status, auth.success,
                             auth.requires_user_selection, auth.error_type, auth.message)
        results.append(item)
        step(auth.message)
        # Escopo atual encerra no login; nenhum download fictício é informado.
    return results
