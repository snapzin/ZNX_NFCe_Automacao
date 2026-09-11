"""Teste real de um cliente com a mesma orquestração do aplicativo, sem navegador."""
import argparse
from dataclasses import asdict
from getpass import getpass
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.automation.sat_automacao import executar_local, preparar_parametros
from app.automation.sat_session import CredenciaisSAT
from app.config.config_defaults import default_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cnpj", required=True)
    parser.add_argument("--inicio", required=True)
    parser.add_argument("--fim", required=True)
    args = parser.parse_args()
    document = ''.join(c for c in args.cnpj if c.isdigit())
    if len(document) != 14:
        parser.error("Informe CNPJ com 14 dígitos")
    parameters = preparar_parametros(args.inicio, args.fim,
        clientes=[{"nome":"Cliente de teste", "documento":document, "ativo":True}])
    credentials = CredenciaisSAT(getpass("Usuário SAT (oculto): "), getpass("Senha SAT (oculta): "))
    authentication = []
    results = executar_local(parameters, config=SimpleNamespace(**default_values()), credenciais=credentials,
        on_auth=lambda auth: authentication.append(asdict(auth)),
        on_progress=lambda i,total,doc,name,stage,results: print(stage, flush=True))
    report = {"cnpj":document, "periodo":[parameters.data_inicio,parameters.data_fim],
              "transporte":"HTTP sem navegador", "authentication":authentication,
              "resultados":[asdict(r) for r in results], "documentos_baixados":sum(r.documentos for r in results)}
    if any(r.error_type == "HUMAN_VALIDATION_REQUIRED" for r in results):
        report["busca_fiscal_enviada"] = False
    path = Path(__file__).resolve().parents[1] / "docs" / "TESTE_CLIENTE_HTTP.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
