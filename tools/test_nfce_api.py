"""Primeiro lote autorizado da API oficial. Não registra arquivo/senha do A1."""
import json
from getpass import getpass
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.automation.sat_nfce_api import CertificadoAPI, abrir_api, ErroAPI, MENSAGENS


def main():
    certificate = CertificadoAPI(getpass("Caminho do A1 (oculto): "), getpass("Senha do A1 (oculta): "))
    root = Path(__file__).resolve().parents[1]
    target = root / "Downloads" / "35693867000154" / "api_sef"
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "primeiro_lote.json"
    if report_path.exists():
        print("Teste já registrado. Consultar o estado salvo antes de repetir a requisição.")
        return
    report = {"cnpj":"35693867000154", "ator":"emitente", "nsu_solicitado":0,
              "data_teste":datetime.now(timezone.utc).isoformat(), "documentos_baixados":0}
    try:
        _, cert = certificate.carregar()
        print("Certificado aberto; validade local confirmada", flush=True)
        report["certificado_valido_localmente"] = True
        with abrir_api(certificate) as api:
            print("Consultando API oficial NFC-e com o certificado", flush=True)
            batch = api.consultar_lote(report["cnpj"])
            report.update(codigo=batch.codigo, message=MENSAGENS.get(batch.codigo,"Resposta da SEF requer análise"),
                          ultimo_nsu=batch.ultimo_nsu, quantidade=batch.quantidade)
            if batch.lote_xml:
                path = target / f"lote_0_{batch.ultimo_nsu}.xml"
                path.write_bytes(batch.lote_xml)
                report["lote_salvo"] = path.name
                report["documentos_baixados"] = batch.quantidade
    except ErroAPI as exc:
        report["message"] = str(exc)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__ == "__main__":
    main()
