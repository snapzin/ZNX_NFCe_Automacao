"""Baixa e retoma NFC-e pela API oficial; arquivo/senha A1 somente em memória."""
import argparse
from dataclasses import asdict
from getpass import getpass
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.automation.sat_nfce_api import CertificadoAPI, abrir_api, ErroAPI
from app.automation.sat_nfce_download import baixar_periodo
from app.output_layout import pastas_empresa


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cnpj",required=True)
    parser.add_argument("--inicio",required=True)
    parser.add_argument("--fim",required=True)
    parser.add_argument("--nome",default="")
    args = parser.parse_args()
    cert = CertificadoAPI(getpass("Caminho do A1 (oculto): "),getpass("Senha do A1 (oculta): "))
    try:
        with abrir_api(cert) as api:
            root = Path(__file__).resolve().parents[1]
            _, _, _, xml_folder = pastas_empresa(root / "Downloads", args.nome or args.cnpj,
                                                  args.inicio, args.fim)
            result = baixar_periodo(api,cnpj=args.cnpj,inicio=args.inicio,fim=args.fim,
                pasta_saida=xml_folder, pasta_cache=root/"cache_nfce"/args.cnpj,
                on_step=lambda m:print(m,flush=True))
            print(json.dumps(asdict(result),ensure_ascii=False,indent=2),flush=True)
    except ErroAPI as exc:
        print(str(exc),flush=True)
        raise SystemExit(1) from None
    except Exception:
        print("Download interrompido; estado preservado para análise",flush=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
