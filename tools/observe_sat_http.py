"""Teste autorizado de login e abertura da consulta por HTTP; não faz busca fiscal."""
import json
import sys
from getpass import getpass
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.automation.sat_session import abrir_sessao, CredenciaisSAT
from app.config.config_defaults import default_values


def main():
    credentials = CredenciaisSAT(getpass("Usuário SAT (oculto): "), getpass("Senha SAT (oculta): "))
    try:
        with abrir_sessao(SimpleNamespace(**default_values()), credentials, None, print) as client:
            auth = client.autenticar()
            print(json.dumps(asdict(auth), ensure_ascii=False))
            if auth.success:
                client.abrir_consulta_nfce()
                print(json.dumps({"consulta_aberta_por_http": True,
                                  "validacao_humana_exigida": client.exige_validacao_humana(),
                                  "busca_fiscal_enviada": False}))
    except Exception:
        print("Teste HTTP interrompido; detalhes secretos omitidos")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
