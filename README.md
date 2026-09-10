# ZNX NFC-e / SAT — preparação do login

Aplicação separada, baseada no ZIP NFSe fornecido. O ZIP original não foi alterado.
Preserva Electron/React/Vite, FastAPI, Playwright, cadastro, jobs e licenciamento.

**Escopo desta versão:** testar usuário e senha no SAT por empresa, acompanhar a
resposta e registrar sucesso, erro ou pendência. Consulta e download de NFC-e ainda
dependem do mapeamento da operação CONX.

Página inicial fixa: https://sat.sef.sc.gov.br/tax.NET/Login.aspx

## Executar

No Windows, com Python 3.10+ (validado com 3.14), Node.js/npm e Google Chrome:

1. Abra `INICIAR.bat` na raiz do projeto.
2. Ative a licença pelo fluxo existente.
3. Em **Clientes**, cadastre CPF/CNPJ, nome, usuário SAT e senha. Marque a empresa
   como ativa e clique em **Salvar**. A senha aparece mascarada.
4. Em **Executar**, clique em **Executar agora**. O navegador será aberto por
   empresa, em contexto temporário, e encerrado ao concluir a tentativa.
5. Observe o resultado e a etapa de cada empresa. Pendência não conta como sucesso.

O script não requer elevação para configurar certificados. Não há acesso por
certificado nesta execução.

Alternativa manual, em PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd electron
npm.cmd ci --no-audit --no-fund
node node_modules/electron/install.js
npm.cmd run dev
```

O instalador de dependências Electron acima também atende versões de npm que
deixam scripts de instalação pendentes. O aplicativo usa Chrome instalado;
não é necessário copiar perfis ou instalar certificados.

## Confirmar a página seguinte com a conta de teste

Os seletores de usuário, senha e Entrar foram confirmados na página pública com
Chrome/Playwright em 10/09/2026. A seleção de usuário existe no DOM inicial, mas
está oculta; só é tratada quando visível.

**`SAT_SELECTOR_LOGIN_OK` está vazio de propósito.** Nenhum indicador autenticado
foi observado com uma conta real. Uma navegação ou clique isolado não gera sucesso:
retorna `UNCONFIRMED` ou `ADDITIONAL_STEP`. A configuração já permite inserir o
indicador real quando observado. Seleção de usuário/perfil retorna
`USER_SELECTION_REQUIRED`, sem escolher nenhuma opção automaticamente.

Para observar a etapa seguinte mantendo o navegador aberto:

```powershell
.\.venv\Scripts\python.exe tools\test_sat_login.py
```

O utilitário solicita credenciais com entrada oculta, faz uma tentativa e aguarda
Enter antes de fechar. Não grava credenciais nem captura o conteúdo da sessão.
Depois de observar o indicador de autenticação, configure **LOGIN OK** em
**Configurações**. Também há campos para indicadores reais de credenciais inválidas
e erro do portal. Não preencha esses campos com seletores presumidos.

## Cadastro e arquivos locais

Planilhas aceitas: XLSX/XLSM. Colunas `cnpj`/`cpf`/`documento`, `nome`, `usuario`,
`senha`, `ativo`. Também aceita `USUARIO_SAT`/`SENHA_SAT` e os nomes legados
`USUARIO_NFSE`/`SENHA_NFSE`. Importe e clique em **Salvar**. Use células de texto
para documentos e senhas para preservar zeros iniciais.

Em desenvolvimento, configuração e cadastro ficam na raiz do novo projeto. No
aplicativo instalado, ficam no diretório `data` dentro do `userData` do Electron
do produto SAT. `SAT_DATA_DIR` permite escolher outra pasta. A origem aparece na
tela Clientes. A pasta Downloads mantém a convenção base da NFSe; nenhuma estrutura
de arquivos fiscais é criada nesta etapa de login.

As credenciais seguem o armazenamento local herdado em XLSX/JSON, **sem criptografia
em repouso**. Não entram nos logs, nas chamadas de sincronização de clientes ou no
instalador. Veja as limitações em [docs/RELATORIO_TECNICO.md](docs/RELATORIO_TECNICO.md).

O cadastro SAT é local por padrão para não sobrescrever clientes NFSe no servidor
compartilhado. A infraestrutura remota foi mantida, mas só é usada com
`SAT_CLIENTES_REMOTE=1` e `SAT_CLIENTES_URL` apontando para um serviço separado e
compatível. A validação de licença continua usando as variáveis `NFSE_LICENSE_*`
e o contrato original, sem alterar o servidor fornecido.

## Testar

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools\inspect_sat_login.py
.\.venv\Scripts\python.exe tools\smoke_renderer.py
.\.venv\Scripts\python.exe tools\smoke_electron.py
.\.venv\Scripts\python.exe tools\smoke_electron.py --packaged
```

`pytest`: lógica e API com dependências externas simuladas somente nos testes.
`inspect_sat_login.py`: inspeção pública real, sem preencher nem enviar credenciais.
`smoke_renderer.py`: UI compilada com IPC simulado, sem conexão fiscal/licenciamento.
`smoke_electron.py`: Electron real e health autenticado FastAPI, sem ativar licença;
abre janelas ocultas, usa dados temporários e encerra somente seus próprios processos.
Os dois últimos exigem `npm.cmd run build:renderer` em `electron`.
A opção `--packaged` exige também o build do instalador e verifica a aplicação
em `electron/dist/win-unpacked`.

## Executável e instalador

Execute `CONSTRUIR_INSTALADOR.bat`. O processo roda testes, PyInstaller, Vite e
electron-builder/NSIS. Não publica releases e não copia `config.py` ou cadastros
locais para o pacote.

Saídas:

- `dist/server/server.exe`: backend, acompanhado de sua pasta `_internal`.
- `electron/dist/ZNX-SAT-Setup-0.1.0.exe`: instalador Windows.

O computador de destino precisa de Google Chrome, acesso ao SAT e licença válida.
O pacote não tem assinatura digital configurada. A infraestrutura de auto-update
permanece no Electron, mas só verifica atualizações se `SAT_UPDATE_FEED_URL` apontar
para um canal próprio do SAT. O repositório de releases da NFSe não é utilizado.

Próximo passo: usar uma conta de teste autorizada para observar o indicador de
login concluído, eventuais erros e a seleção de perfil. Depois mapear a aplicação
CONX e o fluxo de consulta/download.
