"""Inicia Electron real sem exibir janelas e verifica IPC -> FastAPI.

Valida abertura direta da aplicação e o health autenticado, sem licença.
Usa um diretório de dados temporário e encerra somente o processo que iniciou.
"""
import json
from getpass import getpass
import os
from pathlib import Path
import socket
import subprocess
import shutil
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright


def main():
    root = Path(__file__).resolve().parents[1]
    packaged = "--packaged" in sys.argv
    certificate_test = "--certificate-test" in sys.argv
    certificate = None
    if certificate_test:
        certificate = {"arquivo": getpass("Caminho do A1 (oculto): "), "senha": getpass("Senha do A1 (oculta): ")}
    executable = root / ("electron/dist/win-unpacked/ZNX SAT Automacao.exe" if packaged
                         else "electron/node_modules/electron/dist/electron.exe")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="sat_electron_smoke_") as temp:
        if certificate_test:
            legacy = root / "cache_nfce/35693867000154"
            target = Path(temp) / "data/cache_nfce/35693867000154"
            if legacy.is_dir():
                shutil.copytree(legacy, target)
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
                page.get_by_role("button", name="Executar agora", exact=True).wait_for(timeout=10000)
                assert page.get_by_role("button", name="Executar agora", exact=True).is_enabled()
                assert page.locator(".license-gate").count() == 0
                assert page.get_by_label("Forma de acesso", exact=True).input_value() == "certificado_api"
                assert page.get_by_role("button", name="Selecionar certificado A1", exact=True).is_visible()
                assert page.get_by_label("Senha do certificado (somente nesta execução)", exact=True).is_visible()
                assert page.evaluate("typeof window.electronAPI.selectCertificate === 'function' && typeof window.electronAPI.openResult === 'function'")
                page.get_by_label("Forma de acesso",exact=True).select_option("usuario_senha")
                assert page.get_by_label("Usuário SAT", exact=True).is_visible()
                page.get_by_label("Forma de acesso",exact=True).select_option("certificado_api")
                settings = page.evaluate("window.electronAPI.apiCall('GET', '/config')")
                assert not any(k.startswith("SAT_CERTIFICADO") for k in settings["values"])
                assert int(settings["values"]["SAT_HTTP_TIMEOUT_S"]) > 0
                assert "PLAYWRIGHT_HEADLESS" not in settings["values"]
                health = page.evaluate("window.electronAPI.apiCall('GET', '/health/auth')")
                assert health == {"ok": True, "authenticated": True}
                clients = page.evaluate("window.electronAPI.apiCall('GET', '/clientes')")
                assert clients["clientes"] == []
                if certificate_test:
                    # Reaproveita a distribuição autorizada; não reinicia NSU nem força rede.
                    from app.reports.nfce import parse, txt
                    output = root / "Downloads"
                    source = output / "JHOW BATATA BATATAS RECHEADAS E MASSAS/08 - Agosto 2026/XMLs"
                    note = parse(next(source.glob("NFCe_*.xml")).read_bytes())
                    name = txt(note, "n:NFe/n:infNFe/n:emit/n:xNome")
                    page.evaluate("body => window.electronAPI.apiCall('POST','/config',body)", {"PASTA_SAIDA": str(output)})
                    page.evaluate("body => window.electronAPI.apiCall('POST','/clientes',body)",
                                  {"clientes": [{"documento": "35693867000154", "nome": name, "ativo": True}]})
                    started = page.evaluate("body => window.electronAPI.apiCall('POST','/executar',body)",
                        {"tipoLogin": "certificado_api", "certificado": certificate,
                         "dataInicio": "2026-08-01", "dataFim": "2026-08-31"})
                    jobid = started["jobId"]
                    deadline = time.monotonic() + 300
                    last_stage = None
                    while time.monotonic() < deadline:
                        result = page.evaluate("id => window.electronAPI.apiCall('GET',`/executar/${id}/status`)", jobid)
                        stage = result.get("progress", {}).get("stage")
                        if stage != last_stage:
                            print(stage, flush=True)
                            last_stage = stage
                        if result["status"] != "running":
                            break
                        time.sleep(.5)
                    assert result["status"] == "ok", "O job com A1 não concluiu"
                    final = result["resultado"]
                    assert final["notas"] == 1187 and final["eventos"] == 9
                    assert final["relatorios"]["clientes"]["35693867000154"] and not final["relatorios"]["erros"]
                    assert certificate["arquivo"] not in json.dumps(result)
                    assert certificate["senha"] not in json.dumps(result)
                    for kind in ("cliente", "relatorio", "xml"):
                        info = page.evaluate("args => window.electronAPI.apiCall('GET',`/executar/${args[0]}/arquivo?tipo=${args[1]}&cnpj=35693867000154`)", [jobid, kind])
                        assert Path(info["path"]).exists()
                    evidence = {"packaged": packaged, "status": result["status"],
                        "notas": final["notas"], "eventos": final["eventos"],
                        "origem": final["resultados"][0]["origem"], "relatorios": final["relatorios"],
                        "segredos_omitidos": True}
                    (root / "docs/TESTE_APP_CERTIFICADO.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
                page.get_by_role("button", name="Clientes", exact=True).click()
                page.get_by_role("button", name="+ Adicionar cliente", exact=True).wait_for(timeout=10000)
                page.get_by_role("button", name="Sobre", exact=True).click()
                page.get_by_text("Versão 0.5.1", exact=True).wait_for(timeout=10000)
                print(json.dumps({"electron_started": True, "packaged": packaged, "opens_without_license": True,
                                  "customers_accessible": True, "certificate_default": True, "http_login_fallback": True,
                                  "ipc_fastapi_authenticated": health["authenticated"]}))
        finally:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            proc.wait(timeout=10)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
