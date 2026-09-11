"""Um A1 por execução; falhas de vínculo são registradas por empresa."""
import logging
from pathlib import Path

from app.automation.sat_auth import AuthResult, ExecucaoCancelada, check_cancel
from app.automation.sat_automacao import ResultadoCNPJ
from app.automation.sat_nfce_api import abrir_api, ErroAPI
from app.automation.sat_nfce_download import baixar_periodo
from app.output_layout import nomes_saida, pastas_empresa

log = logging.getLogger("sat")


def executar_api(params, cancel_event=None, *, config, certificado, on_progress=None, on_auth=None):
    results = []
    total = len(params.clientes)

    def progress(index, client, message):
        name = client["nome"] if client else "Contador"
        log.info("[%s] %s", name, message)
        if on_progress:
            on_progress(index, total, client["documento"] if client else "", name, message, results)

    check_cancel(cancel_event)
    output_names = nomes_saida(params.clientes)
    progress(0, None, "Preparando certificado A1 para a API NFC-e")
    try:
        with abrir_api(certificado) as api:
            if on_auth:
                on_auth(AuthResult(message="Certificado preparado. A autorização é verificada por empresa; arquivos locais dispensam nova consulta."))
            for index, client in enumerate(params.clientes, 1):
                check_cancel(cancel_event)
                authenticated = False

                def response(code):
                    nonlocal authenticated
                    if code in {"117", "118"}:
                        authenticated = True
                        if on_auth:
                            on_auth(AuthResult(success=True, message="Acesso com certificado confirmado pela API. Confira o resultado de cada empresa."))

                progress(index, client, "Consultando NFC-e emitidas com o certificado do contador")
                try:
                    _, _, xml_folder = pastas_empresa(config.PASTA_SAIDA, output_names[client["documento"]])
                    cache_root = Path(config.CACHE_NFCE) / client["documento"]
                    data = baixar_periodo(api, cnpj=client["documento"], inicio=params.data_inicio,
                        fim=params.data_fim, pasta_saida=xml_folder, pasta_cache=cache_root,
                        cancel_event=cancel_event,
                        on_step=lambda message: progress(index, client, message), on_response=response)
                    status = "erro" if data.codigo in {"8002", "280", "281", "283", "284", "285", "286", "489", "215"} else data.status
                    item = ResultadoCNPJ(client["documento"], client["nome"], status,
                        success=status == "ok", authenticated=authenticated,
                        error_type="" if status == "ok" else "SEF_" + (data.codigo or "PENDING"),
                        message=data.message, documentos=data.documentos, notas=data.notas,
                        eventos=data.eventos, pasta=data.pasta, ultimo_nsu=data.ultimo_nsu,
                        proxima_consulta=data.proxima_consulta, origem="cache" if data.from_cache else "api",
                        codigo=data.codigo)
                except ExecucaoCancelada:
                    raise
                except ErroAPI as exc:
                    item = ResultadoCNPJ(client["documento"], client["nome"], "erro",
                        authenticated=authenticated, error_type="API_ERROR", message=str(exc))
                except Exception:
                    item = ResultadoCNPJ(client["documento"], client["nome"], "erro",
                        authenticated=authenticated, error_type="DOWNLOAD_ERROR",
                        message="Falha ao consultar ou salvar XMLs; estado de continuação preservado")
                results.append(item)
                progress(index, client, item.message)
    except ExecucaoCancelada:
        raise
    except ErroAPI as exc:
        if results:
            raise
        if on_auth:
            on_auth(AuthResult(error_type="CERTIFICATE_ERROR", message=str(exc)))
        for index, client in enumerate(params.clientes, 1):
            check_cancel(cancel_event)
            results.append(ResultadoCNPJ(client["documento"], client["nome"], "erro",
                error_type="CERTIFICATE_ERROR", message=str(exc), etapa="certificado"))
            progress(index, client, str(exc))
    return results
