"""Inspeciona apenas a página pública, sem credenciais nem submissão de login."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from app.config.config_defaults import SAT_LOGIN_URL, default_values
from app.automation.sat_auth import detectar_pagina


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page()
            page.goto(SAT_LOGIN_URL, wait_until="load", timeout=45000)
            selectors = {k: v for k, v in default_values().items() if k.startswith("SAT_SELECTOR_")}
            checks = {}
            for key, selector in selectors.items():
                if not selector:
                    continue
                loc = page.locator(selector)
                checks[key] = {"selector": selector, "count": loc.count(),
                               "visible": loc.count() == 1 and loc.is_visible()}
            checks["initial_state"] = "unconfirmed" if detectar_pagina(page, selectors) is None else "unexpected"
            print(json.dumps(checks, ensure_ascii=False, indent=2))
            for key in ("SAT_SELECTOR_USUARIO", "SAT_SELECTOR_SENHA", "SAT_SELECTOR_ENTRAR"):
                assert checks[key]["count"] == 1 and checks[key]["visible"], key
            assert not checks["SAT_SELECTOR_SELECAO_USUARIO"]["visible"]
            assert checks["initial_state"] == "unconfirmed"
        finally:
            browser.close()


if __name__ == "__main__":
    main()
