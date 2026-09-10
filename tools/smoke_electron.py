"""Inicia Electron real sem exibir janelas e verifica IPC -> FastAPI.

Não ativa nem simula licença. Valida a tela de ativação e o health autenticado.
Usa um diretório de dados temporário e encerra somente o processo que iniciou.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright


def main():
    root = Path(__file__).resolve().parents[1]
    packaged = "--packaged" in sys.argv
    executable = root / ("electron/dist/win-unpacked/ZNX SAT Automacao.exe" if packaged
                         else "electron/node_modules/electron/dist/electron.exe")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="sat_electron_smoke_") as temp:
        env = dict(os.environ)
        env.pop("ELECTRON_RUN_AS_NODE", None)
        env.update(SAT_DATA_DIR=str(Path(temp) / "data"),
                   SAT_PROJECT_ROOT=str(root),
                   SAT_PYTHON_PATH=str(root / ".venv/Scripts/python.exe"),
                   VITE_DEV_SERVER_URL=(root / "electron/renderer-dist/index.html").as_uri())
        args = [str(executable)] + ([] if packaged else [str(root / "electron")])
        proc = subprocess.Popen([*args, "--smoke-test",
                                 f"--remote-debugging-port={port}", f"--user-data-dir={temp}"],
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            with sync_playwright() as pw:
                browser = None
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError("Electron encerrou antes do teste")
                    try:
                        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=1000)
                        break
                    except Exception:
                        time.sleep(.5)
                if browser is None:
                    raise RuntimeError("Electron não disponibilizou o navegador")
                page = None
                while time.monotonic() < deadline:
                    pages = [p for ctx in browser.contexts for p in ctx.pages]
                    page = next((p for p in pages if "renderer-dist" in p.url), None)
                    if page:
                        break
                    try:
                        # A splash fecha enquanto a janela principal é criada.
                        if pages:
                            pages[-1].wait_for_timeout(250)
                        else:
                            browser.new_browser_cdp_session().send("Target.getTargets")
                            time.sleep(.1)
                    except Exception:
                        time.sleep(.1)
                if page is None:
                    raise RuntimeError("Interface principal não abriu")
                page.get_by_role("button", name="Ativar licenca", exact=True).wait_for(timeout=10000)
                health = page.evaluate("window.electronAPI.apiCall('GET', '/health/auth')")
                assert health == {"ok": True, "authenticated": True}
                print(json.dumps({"electron_started": True, "packaged": packaged, "license_gate_visible": True,
                                  "ipc_fastapi_authenticated": health["authenticated"]}))
        finally:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            proc.wait(timeout=10)


if __name__ == "__main__":
    main()
