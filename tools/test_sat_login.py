"""Teste manual opcional com conta autorizada; nenhuma credencial é gravada."""
from dataclasses import asdict
from getpass import getpass
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config.config_defaults import ensure_config_file, apply_defaults
from app.automation.sat_auth import login_sat
from playwright.sync_api import sync_playwright


def main():
    sys.path.insert(0, str(ensure_config_file().parent))
    import config
    apply_defaults(config)
    usuario = getpass("Usuário SAT de teste (entrada oculta): ")
    senha = getpass("Senha SAT de teste (entrada oculta): ")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=config.CHROME_CHANNEL or None, headless=False)
        try:
            page = browser.new_page()
            result = login_sat(page, usuario, senha, config=config, on_step=print)
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
            # As páginas permanecem abertas para observar a etapa desconhecida.
            # Não exporta cookies, HTML, screenshots, valores ou traces da sessão.
            input("Observe a página seguinte. Pressione Enter para fechar o navegador.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
