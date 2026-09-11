# ZNX NFC-e / SAT — usuário e senha

Versão 0.3.0. Aplicação separada da NFSe original, sem licença ou ativação.

O acesso ao SAT utiliza **um único login com usuário e senha do contador por execução**.
A planilha contém somente **NOME** e **CNPJ** das empresas que serão consultadas.
Não há usuário, senha ou certificado individual no cadastro de clientes.

## Usar o aplicativo

1. Abra `INICIAR.bat` (desenvolvimento) ou instale
   `electron/dist/ZNX-SAT-Setup-0.3.0.exe`.
2. Na aba **Clientes**, importe sua planilha NOME/CNPJ e clique em **Salvar**.
   Use [modelo_clientes.xlsx](docs/modelo_clientes.xlsx) como modelo. Marque os
   clientes desejados como ativos na interface; a coluna ATIVO não é necessária
   na planilha. Os dois cabeçalhos podem estar em qualquer ordem.
3. Na aba **Executar**, informe o usuário e a senha do SAT. A senha fica oculta,
   vale apenas para a execução atual e é apagada do campo ao iniciar. Nenhuma
   credencial é salva no cadastro, configuração, planilha ou instalador.
4. Escolha o período e clique em **Executar agora**.

A execução abre uma sessão de navegador, preenche **Usuário** e **Senha** e clica em **Entrar**
na página oficial e observa a resposta. Após confirmar o acesso do contador,
o processamento dos CNPJs usa a mesma sessão, sem refazer login por empresa.
O acesso do contador e os resultados das empresas são apresentados separadamente.

**Estado atual:** login com usuário e senha observado na conta autorizada em
11/09/2026, com chegada à lista de aplicações. O indicador dessa tela está
centralizado na configuração. Seleção de perfil e consulta/download por CNPJ
continuam pendentes de mapeamento; o aplicativo não informa downloads concluídos
apenas porque o login terminou.

URL inicial: https://sat.sef.sc.gov.br/tax.NET/Login.aspx

## Confirmar o fluxo real

`SAT_SELECTOR_LOGIN_OK` combina o rodapé da aplicação e o controle
"Buscar aplicações...", observados na sessão autenticada. A confirmação também
exige origem oficial e formulário de login ausente. Configurações antigas com
esse indicador vazio recebem o padrão observado. Mudança de URL sozinha não
confirma autenticação.

Para manter o navegador aberto durante a observação manual:

```powershell
.\.venv\Scripts\python.exe tools\test_sat_login.py
```

O utilitário pede usuário e senha com entrada oculta e aguarda Enter antes de
fechar a sessão. Não salva HTML, screenshots, cookies ou credenciais. O utilitário
`tools/observe_sat_response.py` faz o mesmo teste e encerra automaticamente,
mostrando apenas resultado estruturado e contagens dos indicadores.

## Dados locais

O XLSX salvo tem exatamente `NOME` e `CNPJ`. A seleção ativo/inativo continua em
`clientes_selecao.json`, no formato existente. Colunas antigas de usuário/senha
são ignoradas na importação, e o antigo `clientes_credenciais.json` não é lido.
Arquivos legados existentes não são apagados automaticamente.

Em desenvolvimento, os dados ficam na raiz do projeto. No aplicativo instalado,
ficam no diretório `data` do produto SAT. `SAT_DATA_DIR` permite escolher outra pasta.
O cadastro não é sincronizado com servidores externos. O token entre Electron e
FastAPI permanece protegendo a comunicação local.

Usuário e senha são enviados em memória somente para o job. O navegador usa
contexto temporário, sem certificado digital. Logs e erros têm mensagens fixas;
a senha não é devolvida pelos endpoints nem incluída em resultados.

## Desenvolvimento e testes

Pré-requisitos: Windows, Python 3.10+ (validado com 3.14), Node.js/npm e Google Chrome.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd electron
npm.cmd ci --no-audit --no-fund
node node_modules/electron/install.js
npm.cmd run dev
```

Na raiz:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools\inspect_sat_login.py
.\.venv\Scripts\python.exe tools\smoke_renderer.py
.\.venv\Scripts\python.exe tools\smoke_electron.py
.\.venv\Scripts\python.exe tools\smoke_electron.py --packaged
```

Os testes de autenticação usam dublês de Playwright, sem HTML fiscal inventado.
O inspetor acessa a página pública sem enviar credenciais. O teste da interface
usa IPC simulado; o teste Electron verifica a API real sem ativação. Os testes
de interface exigem `npm.cmd run build:renderer`; `--packaged` exige o build completo.

## Build

Execute `CONSTRUIR_INSTALADOR.bat`. Ele roda testes, compila o backend com
PyInstaller e gera o instalador Electron/NSIS, sem publicar releases.

- Backend: `dist/server/server.exe` (acompanha `_internal`).
- Instalador: `electron/dist/ZNX-SAT-Setup-0.3.0.exe`.

Certificados, senhas, configuração e cadastros não são incluídos no pacote. O
instalador não tem assinatura digital configurada. O mecanismo de atualização
permanece opcional, por `SAT_UPDATE_FEED_URL`, sem usar releases NFSe.

Detalhes da alteração: [docs/LOGIN_USUARIO_SENHA.md](docs/LOGIN_USUARIO_SENHA.md).
