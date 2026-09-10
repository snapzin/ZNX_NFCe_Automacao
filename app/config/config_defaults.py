"""Configuração SAT; mantém o contrato usado pelo backend NFSe."""
from __future__ import annotations

import os
import sys
from pathlib import Path

SAT_LOGIN_URL = "https://sat.sef.sc.gov.br/tax.NET/Login.aspx"


def project_root() -> Path:
    if os.environ.get("SAT_DATA_DIR"):
        return Path(os.environ["SAT_DATA_DIR"]).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ZNX_SAT_Automacao"
    return Path(__file__).resolve().parents[2]


def default_values() -> dict:
    return {
        "XLSX_PATH": "clientes.xlsx",
        "PASTA_SAIDA": "Downloads",
        "SAT_LOGIN_URL": SAT_LOGIN_URL,
        "CHROME_CHANNEL": "chrome",
        "CHROME_EXECUTABLE_PATH": "",
        "PLAYWRIGHT_HEADLESS": False,
        "PLAYWRIGHT_TIMEOUT_MS": 15000,
        "PLAYWRIGHT_LOGIN_TIMEOUT_S": 45,
        # IDs observados no HTML público oficial em 10/09/2026.
        "SAT_SELECTOR_USUARIO": "#Body_pnlMain_rptLoginPanels_tbxUsername_0",
        "SAT_SELECTOR_SENHA": "#Body_pnlMain_rptLoginPanels_tbxUserPassword_0",
        "SAT_SELECTOR_ENTRAR": "#Body_pnlMain_rptLoginPanels_btnLogin_0",
        "SAT_SELECTOR_SELECAO_USUARIO": "h4.tit-pan-acc",
        # TODO: confirmar indicadores na sessão real. Vazio impede falso sucesso.
        "SAT_SELECTOR_LOGIN_OK": "",
        "SAT_SELECTOR_CREDENCIAIS_INVALIDAS": "",
        "SAT_SELECTOR_ERRO_PORTAL": "",
        "LICENSE_ADMIN_URL": os.environ.get("NFSE_LICENSE_ADMIN_URL", "https://license-server-sigma-topaz.vercel.app/api/admin"),
        "LICENSE_ADMIN_TOKEN": "",
    }


PATH_KEYS = {"XLSX_PATH", "PASTA_SAIDA", "CHROME_EXECUTABLE_PATH"}
DIRECTORY_KEYS = {"PASTA_SAIDA"}


def config_path(root: Path | None = None) -> Path:
    return (root or project_root()) / "config.py"


def default_config_text() -> str:
    return "# Configuração local SAT. Não versionar credenciais.\n" + "\n".join(
        f"{key} = {value!r}" for key, value in default_values().items()
    ) + "\n"


def ensure_config_file(root: Path | None = None) -> Path:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(default_config_text(), encoding="utf-8")
    return path


def apply_defaults(config_module: object, create_dirs: bool = True, **_) -> None:
    base = Path(getattr(config_module, "__file__", config_path())).resolve().parent
    for key, value in default_values().items():
        if getattr(config_module, key, None) is None:
            setattr(config_module, key, value)
    # Página inicial oficial, não substituível por URL de outro portal.
    config_module.SAT_LOGIN_URL = SAT_LOGIN_URL
    for key in PATH_KEYS:
        value = getattr(config_module, key, "")
        if value and not Path(value).is_absolute():
            setattr(config_module, key, str(base / value))
    if create_dirs:
        Path(config_module.PASTA_SAIDA).mkdir(parents=True, exist_ok=True)
