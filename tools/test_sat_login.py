"""Teste manual do login único; mantém a sessão aberta para observação."""
from dataclasses import asdict
from getpass import getpass
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config.config_defaults import ensure_config_file, apply_defaults
from app.automation.sat_session import abrir_sessao, CredenciaisSAT


def main():
    sys.path.insert(0, str(ensure_config_file().parent))
    import config
    apply_defaults(config)
    usuario = getpass("Usuário SAT (entrada oculta): ")
    senha = getpass("Senha SAT (entrada oculta): ")
    credenciais = CredenciaisSAT(usuario, senha)
    try:
        with abrir_sessao(config, credenciais, None, print) as session:
            result = session.autenticar()
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
            print("Teste HTTP concluído; sessão encerrada sem navegador.")
    except Exception:
        print("Não foi possível concluir o teste. Confira o acesso ao SAT e a configuração.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
