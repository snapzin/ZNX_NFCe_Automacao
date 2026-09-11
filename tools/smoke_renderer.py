"""Verifica a UI compilada com IPC simulado, sem SAT e sem servidor de licença."""
import json
import mimetypes
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    root = Path(__file__).resolve().parents[1] / "electron/renderer-dist"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 760})
            def resource(route):
                from urllib.parse import urlsplit
                name = urlsplit(route.request.url).path.lstrip("/") or "index.html"
                path = (root / name).resolve()
                if not path.is_relative_to(root.resolve()) or not path.is_file():
                    route.fulfill(status=404)
                    return
                mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
                if path.suffix == ".js":
                    mime = "application/javascript"
                route.fulfill(body=path.read_bytes(), content_type=mime)
            page.route("http://sat-ui.test/**", resource)
            page.add_init_script("""
              window.savedClients = [];
              window.electronAPI = {
                selectCertificate: async () => 'C:/synthetic/hidden-name.pfx',
                openResult: async (...args) => { window.openedResult = args; return {ok:true}; },
                apiCall: async (method, endpoint, body) => {
                  if (endpoint === '/clientes') {
                    if (method === 'POST') window.savedClients = body.clientes;
                    return {clientes:window.savedClients, salvos:window.savedClients.length};
                  }
                  if (endpoint === '/executar') { window.sentJob = body; return {jobId:'ui-test'}; }
                  if (endpoint.endsWith('/status') && window.sentJob?.tipoLogin === 'certificado_api') return {
                    status:'ok', logs:[], progress:{total:1, processed:1, clients:[{cnpj:'12345678000195', nome:'Empresa UI', status:'ok', notas:2, eventos:1}]},
                    resultado:{notas:2,eventos:1,total:1,resultados:[{cnpj:'12345678000195',nome:'Empresa UI',notas:2,eventos:1,pasta:'C:/output'}],
                      relatorios:{clientes:{'12345678000195':'C:/output/Empresa/Relatorio/Cliente.xlsx'},
                        pastas:{'12345678000195':{relatorio:'C:/output/Empresa/Relatorio',xml:'C:/output/Empresa/XMLs'}},erros:[]}}
                  };
                  if (endpoint.endsWith('/status')) return {
                    status:'pendente', logs:[], progress:{total:1, processed:1,
                      clients:[{cnpj:'12345678000195', nome:'Empresa UI', status:'pendente',
                        message:'SAT solicita seleção de usuário/perfil'}]}
                  };
                  return {};
                }
              };
            """)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto("http://sat-ui.test/")
            page.get_by_role("button", name="Clientes", exact=True).click()
            page.get_by_role("button", name="+ Adicionar cliente", exact=True).click()
            row = page.locator("tbody tr").first
            row.locator('input[type="text"]').nth(0).fill("12345678000195")
            row.get_by_placeholder("Nome / Razão social").fill("Empresa UI")
            assert row.locator('input[type="password"]').count() == 0
            assert row.locator('input[type="text"]').count() == 2
            page.get_by_role("button", name="Salvar", exact=True).click()
            page.wait_for_function("window.savedClients.length === 1")
            assert page.evaluate("Object.keys(window.savedClients[0]).sort().join(',')") == "ativo,documento,nome"
            page.get_by_role("button", name="Executar", exact=True).click()
            assert page.get_by_label("Forma de acesso",exact=True).input_value()=="certificado_api"
            page.get_by_role("button",name="Selecionar certificado A1",exact=True).click()
            password=page.get_by_label("Senha do certificado (somente nesta execução)",exact=True)
            assert password.get_attribute("type")=="password"
            password.fill("synthetic-certificate-password")
            page.get_by_role("button",name="Executar agora",exact=True).click()
            page.wait_for_function("window.sentJob?.certificado?.senha === 'synthetic-certificate-password'")
            assert not page.evaluate("'credenciais' in window.sentJob")
            assert password.input_value()==""
            page.get_by_role("button",name="Relatório da empresa",exact=True).click()
            page.wait_for_function("window.openedResult?.[1] === 'cliente' && window.openedResult?.[2] === '12345678000195'")
            assert "hidden-name" not in page.locator("body").inner_text()
            assert "synthetic-certificate-password" not in page.locator("body").inner_text()
            page.screenshot(path=str(root.parent.parent / 'docs/interface_api_relatorios.png'),full_page=True)
            page.get_by_label("Forma de acesso",exact=True).select_option("usuario_senha")
            page.get_by_label("Usuário SAT", exact=True).fill("ui-test-user")
            page.get_by_label("Senha SAT (somente nesta execução)", exact=True).fill("ui-test-password")
            page.get_by_role("button", name="Executar agora", exact=True).click()
            page.wait_for_function("window.sentJob?.credenciais?.senha === 'ui-test-password'")
            assert page.evaluate("window.sentJob.tipoLogin") == "usuario_senha"
            assert page.get_by_label("Senha SAT (somente nesta execução)", exact=True).input_value() == ""
            assert not page.evaluate("'certificado' in window.sentJob")
            page.get_by_text("1 pendente(s) de verificação", exact=True).wait_for()
            assert page.get_by_text("0 cliente(s) concluído(s)", exact=True).is_visible()
            assert "ui-test-password" not in page.locator("body").inner_text()
            assert not errors, errors
            print(json.dumps({"customer_form": True, "only_name_cnpj": True,
                              "certificate_default_and_ephemeral": True, "two_output_folders": True,
                              "pending_not_success": True, "js_errors": 0}))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
