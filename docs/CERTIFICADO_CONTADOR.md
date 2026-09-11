> Versão atual: **0.3.0 — usuário e senha**, conforme [LOGIN_USUARIO_SENHA.md](LOGIN_USUARIO_SENHA.md). O fluxo por certificado abaixo é histórico e foi substituído.

# Versão 0.2.0 — sessão única do contador

A solicitação atual substitui o fluxo de usuário/senha por empresa. O certificado
pertence ao contador; os clientes são somente alvos de consulta por CNPJ. A remoção
do licenciamento da versão 0.1.1 continua valendo.

## Alterações

- `sat_auth.py`: aciona exclusivamente o botão de certificado observado no DOM.
  Não preenche os campos de login por senha. Mantém detecção conservadora de
  autenticação, erros, postbacks, seleção de perfil, janelas e cancelamento.
- `sat_session.py`: gerencia um navegador/contexto por job e um certificado global.
  Usa o certificado instalado com seleção nativa, ou um PFX/P12 via Playwright.
  Não altera o repositório de certificados ou políticas do Windows.
- `sat_automacao.py`: autentica o contador uma vez antes do laço de clientes. Falha
  ou pendência de autenticação bloqueia as consultas; não dispara logins por CNPJ.
  Após autenticação confirmada, transmite a mesma sessão a cada consulta. Erros por
  empresa não fazem as outras empresas usarem novos certificados.
- API e interface: cadastro apenas com nome/CNPJ e seleção ativo/inativo local;
  planilha gravada com exatamente duas colunas. Configuração do certificado é global.
  O resultado `authentication` do job é separado dos resultados de documentos.
- Senha A1: campo mascarado na execução, não persistido em XLSX, JSON ou config.
  Erros não incluem conteúdo de exceções, senha, PIN ou dados do certificado.
- `sat_downloader.py`: ponto de extensão para consulta na sessão do contador.
  Continua lançando `FluxoNaoMapeado` até observar a funcionalidade CONX real.

## Evidência do portal e API utilizada

Na [página pública oficial](https://sat.sef.sc.gov.br/tax.NET/Login.aspx), Chrome
confirmou o link `#Body_pnlMain_rptLoginPanels_btnLoginCertificado_1`, com texto
“Entrar com Certificado Digital”. Seu `onclick` chama `LoadCertificate(this)` e
o código público observado carrega `CertificateAuth.ashx` antes do postback. A
automação aciona o link real, sem reproduzir a autenticação via HTTP direto.

`#LoginContainers` foi confirmado como o formulário inicial visível; o título
`h4.tit-pan-acc` de seleção está presente, mas oculto antes de autenticar.

O modo A1 usa o contrato oficial
[Playwright Browser.new_context / client_certificates](https://playwright.dev/python/docs/api/class-browser#browser-new-context-option-client-certificates):
um PFX/P12, senha em memória e uma origem HTTPS exata. A origem inicial configurada
é a do SAT. Eventuais outras origens de autenticação precisam ser observadas com
o certificado real; não foram presumidas.

## Limites de homologação

Nenhum certificado real foi fornecido ou usado nesta alteração. O modo instalado
pode exigir seleção nativa no Chrome; A3 pode exigir PIN e driver. O carregamento
A1 foi implementado contra a API do Playwright e testado por dublês, sem comprovar
aceitação fiscal do certificado no SAT.

O indicador positivo de autenticação continua pendente de observação. A seleção
de perfil não escolhe opções automaticamente. Aplicação CONX, consulta por CNPJ,
período, resultados e download continuam sem seletores/URLs presumidos.

Portanto, `authentication.success=true` não significa que documentos foram
baixados. Enquanto o downloader não estiver mapeado, cada cliente recebe pendência
`FLOW_NOT_MAPPED` e zero documentos, mesmo que o login tenha sido confirmado.

## Testes

42 testes locais aprovados: clique exclusivo em certificado, visibilidade da
seleção, postbacks/popups, cancelamento, um login por lote, mesma sessão entre
clientes, falhas individuais, bloqueio por falha compartilhada, ausência de falso
download, importação NOME/CNPJ em qualquer ordem, descarte de credenciais legadas,
planilha com duas colunas, proteção dos segredos e ausência de licença.

Inspeção pública real aprovada. Teste da interface compilada aprovou cadastro
somente com nome/CNPJ, sem campos de acesso por cliente e sem erros JavaScript.
O ZIP NFSe original foi preservado.
