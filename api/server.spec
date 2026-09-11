# -*- mode: python ; coding: utf-8 -*-
"""
Spec PyInstaller para o backend FastAPI (api/server.py).
Gera dist/server/server.exe — executavel standalone, sem Python no sistema.
config.py fica FORA do bundle (copiado pelo build script ao lado do server.exe).
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPEC_DIR = Path(SPECPATH)          # .../nfse/api/
ROOT_DIR = SPEC_DIR.parent         # .../nfse/

datas = []

# ── Imports ocultos ────────────────────────────────────────────────────────────
hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("anyio")
hiddenimports += [
    "openpyxl", "openpyxl.styles", "openpyxl.utils",
    "h11", "h11._readers", "h11._writers",
    "email.mime.multipart", "email.mime.text",
    "app.automation.sat_automacao", "app.automation.sat_auth",
    "app.automation.sat_http", "requests", "bs4", "soupsieve", "app.automation.sat_downloader", "app.automation.sat_session", "app.config.config_defaults",
]

# ── Análise ────────────────────────────────────────────────────────────────────
a = Analysis(
    [str(SPEC_DIR / "server.py")],
    pathex=[str(ROOT_DIR)],        # projeto root → importa nfse_automacao, cert_reader, etc.
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "playwright",
        "config",                  # fica externo, ao lado do server.exe
        # GUI/extras nao usados pelo backend (enxuga o bundle):
        "customtkinter", "tkcalendar", "PIL",
        "tkinter",                 # seletor de pasta agora e feito no Electron
        "babel",                   # dep da GUI; backend nao usa (~31 MB)
        "notebook", "IPython", "matplotlib", "selenium",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # mostra console para log (main.js captura stdout)
    version=str(SPEC_DIR / "version_info.txt"),  # metadados (reduz falso-positivo de AV)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="server",
    contents_directory=".",   # todos os arquivos na mesma pasta do server.exe
)
