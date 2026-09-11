# ZNX NFC-e / SAT — API e HTTP sem navegador

Versão 0.4.0. Aplicativo separado da NFSe original, sem licença ou ativação.
A comunicação com o portal SAT usa `requests.Session`, cookies e formulários
ASP.NET em memória. A execução não inicia Chrome nem Playwright.

## Teste com certificado A1 — concluído

O certificado fornecido foi aceito pela API oficial da SEF para o CNPJ
**35.693.867/0001-54**. Foram obtidas **1.187 NFC-e e 9 eventos de agosto/2026**,
sem navegador. Os XMLs exportados tiveram digest e assinatura RSA conferidos.
Isso não substitui validação fiscal ou da cadeia de certificação.

O cliente SOAP, a continuação por NSU e a exportação estão implementados em Python.
**Este fluxo é executado pelo terminal; a tela e o instalador 0.4.0 ainda usam
usuário/senha do portal.** Consulte [API com A1](docs/API_NFCE.md) e
[resultado do teste](docs/TESTE_CERTIFICADO_API.json).

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/baixar_nfce_api.py --cnpj 35693867000154 --inicio 2026-08-01 --fim 2026-08-31
```

O terminal pede caminho e senha do A1 com entrada oculta. Não são gravados na
configuração. O cache local permite reexportar o período durante a espera de
12 horas da API, sem repetir consultas. Não apague o estado NSU para forçar consultas.

## Teste anterior pelo portal — usuário e senha

O login com usuário e senha foi confirmado por HTTP. A aplicação **NFe / NFCe -
Consulta** foi aberta pelo link observado no menu, preservando os redirecionamentos.
Ela apresenta **Cloudflare Turnstile obrigatório**. Quando isso acontece, o job
registra `HUMAN_VALIDATION_REQUIRED`, sem enviar a busca nem informar arquivos baixados.

Teste solicitado: CNPJ **35.693.867/0001-54**, período **01/08/2026 a 31/08/2026**.
Naquele teste: login confirmado, **zero downloads**, busca fiscal não enviada devido à validação.
Consulte [o resultado estruturado](docs/TESTE_CLIENTE_HTTP.json).

A SEF disponibiliza uma [API oficial para download de XML NFC-e](https://www.sef.sc.gov.br/saiba-mais/web-service-para-download-de-nfce),
que exige certificado digital do contador vinculado ao contribuinte. Usuário e
senha do portal não substituem essa autenticação. O teste posterior com A1 acima
confirmou o download. O transporte HTTP do portal não é essa API oficial.

## Usar

1. Abra `INICIAR.bat` ou instale `electron/dist/ZNX-SAT-Setup-0.4.0.exe`.
2. Em **Clientes**, importe a planilha com **NOME** e **CNPJ**, salve e marque os clientes.
   [Planilha modelo](docs/modelo_clientes.xlsx).
3. Em **Executar**, informe usuário/senha do SAT e o período. A senha é apagada do
   campo ao iniciar e não é salva em configuração, planilha, logs ou instalador.
4. Confira separadamente o acesso do contador e o resultado de cada empresa.

Uma sessão HTTP atende todos os clientes da execução. O captcha não é contornado,
não há abertura automática de navegador e não são inventados documentos ou endpoints.
Os botões Exportar/Exportar itens observados na consulta se referem a dados da nota;
ainda não foi confirmado que entreguem os XML completos.

## Dados locais

XLSX contém exatamente NOME e CNPJ. A seleção fica em `clientes_selecao.json`.
Credenciais antigas em colunas extras são ignoradas. Cookies e campos de estado
ASP.NET ficam em memória e não são incluídos em diagnósticos. O token de sessão
Electron/FastAPI continua protegendo a API local.

## Desenvolvimento e validação

Requer Python e Node.js/npm para desenvolvimento. Chrome/Playwright são usados
somente pelos testes da interface; o backend empacotado não os inclui.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
cd electron
npm.cmd run build:renderer
cd ..
.\.venv\Scripts\python.exe tools/smoke_renderer.py
.\.venv\Scripts\python.exe tools/smoke_electron.py
```

Teste manual HTTP (pede credenciais com entrada oculta):

```powershell
.\.venv\Scripts\python.exe tools/test_sat_cliente_http.py --cnpj 35693867000154 --inicio 2026-08-01 --fim 2026-08-31
```

Build: `CONSTRUIR_INSTALADOR.bat`. Teste do pacote:
`.\.venv\Scripts\python.exe tools/smoke_electron.py --packaged`.

Detalhes: [HTTP e API oficial](docs/HTTP_SAT.md). Registros de versões anteriores
em outros documentos são históricos e não descrevem o transporte atual.
