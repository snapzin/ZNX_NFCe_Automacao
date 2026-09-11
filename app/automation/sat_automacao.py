"""Orquestra empresas com o contrato de execução local usado pela API NFSe."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from app.automation.sat_session import CredenciaisSAT, abrir_sessao
from app.automation.sat_http import ValidacaoHumanaNecessaria, ErroSATHTTP
from app.automation.sat_downloader import consultar_e_baixar, FluxoNaoMapeado
from datetime import date, datetime, timedelta

from app.automation.sat_auth import ExecucaoCancelada, check_cancel, resultado

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
    etapa: str = "consulta"
    authenticated: bool = False
    documentos: int = 0
    notas: int = 0
    eventos: int = 0
    pasta: str = ""
    ultimo_nsu: int = 0
    proxima_consulta: str = ""
    origem: str = ""
    codigo: str = ""


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


def executar_local(params, cancel_event=None, *, config=None, on_progress=None,
                   credenciais=None, on_auth=None, session_factory=None,
                   download=None) -> list[ResultadoCNPJ]:
    """Autentica uma vez como contador; consulta cada CNPJ na mesma sessão."""
    if config is None:
        import config
    credenciais = credenciais or CredenciaisSAT()
    session_factory = session_factory or abrir_sessao
    download = download or consultar_e_baixar
    results = []
    total = len(params.clientes)
    auth = None

    def progress(index, client, message):
        name = client["nome"] if client else "Contador"
        log.info("[%s] %s", name, message)
        if on_progress:
            on_progress(index, total, client["documento"] if client else "", name, message, results)

    def blocked(auth_result):
        pending = auth_result.error_type in {"USER_SELECTION_REQUIRED", "ADDITIONAL_STEP", "UNCONFIRMED"}
        for index, client in enumerate(params.clientes, 1):
            check_cancel(cancel_event)
            results.append(ResultadoCNPJ(
                client["documento"], client["nome"], "pendente" if pending else "erro",
                requires_user_selection=auth_result.requires_user_selection,
                error_type=auth_result.error_type, message=auth_result.message, etapa="login_contador"))
            progress(index, client, "Consulta não iniciada: " + auth_result.message)

    check_cancel(cancel_event)
    progress(0, None, "Iniciando sessão única do contador")
    try:
        with session_factory(config, credenciais, cancel_event,
                             lambda message: progress(0, None, message)) as session:
            check_cancel(cancel_event)
            auth = session.autenticar()
            if on_auth:
                on_auth(auth)
            progress(0, None, auth.message)
            check_cancel(cancel_event)
            if not auth.success:
                blocked(auth)
                return results
            for index, client in enumerate(params.clientes, 1):
                check_cancel(cancel_event)
                progress(index, client, "Preparando consulta NFC-e por CNPJ na sessão do contador")
                try:
                    data = download(session, cliente=client,
                                    data_inicio=params.data_inicio, data_fim=params.data_fim,
                                    pasta_saida=config.PASTA_SAIDA)
                    check_cancel(cancel_event)
                    item = ResultadoCNPJ(client["documento"], client["nome"], "ok", success=True,
                                         authenticated=True, documentos=data.documentos,
                                         message="Consulta e download concluídos")
                except ValidacaoHumanaNecessaria:
                    item = ResultadoCNPJ(client["documento"], client["nome"], "pendente",
                                         authenticated=True, error_type="HUMAN_VALIDATION_REQUIRED",
                                         message="Login HTTP confirmado; SAT exige validação humana na consulta NFC-e")
                except ErroSATHTTP:
                    item = ResultadoCNPJ(client["documento"], client["nome"], "erro", authenticated=True,
                                         error_type="HTTP_ERROR", message="Falha de comunicação HTTP com a consulta SAT")
                except FluxoNaoMapeado:
                    item = ResultadoCNPJ(client["documento"], client["nome"], "pendente",
                                         authenticated=True, error_type="FLOW_NOT_MAPPED",
                                         message="Login do contador confirmado; consulta/download por CNPJ aguardam mapeamento")
                except ExecucaoCancelada:
                    raise
                except Exception:
                    item = ResultadoCNPJ(client["documento"], client["nome"], "erro", authenticated=True,
                                         error_type="DOWNLOAD_ERROR", message="Falha na consulta/download desta empresa")
                results.append(item)
                progress(index, client, item.message)
    except ExecucaoCancelada:
        raise
    except Exception:
        check_cancel(cancel_event)
        if auth is None:
            auth = resultado("PORTAL_ERROR")
            if on_auth:
                on_auth(auth)
            blocked(auth)
        else:
            # Falha de sessão/encerramento não transforma resultados já obtidos em sucesso.
            raise RuntimeError("Falha na sessão do contador") from None
    return results
