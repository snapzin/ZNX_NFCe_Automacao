# Análise e entrega SAT

Data: 10/09/2026. Projeto novo: `D:\Trabalho\ZNX_NFCe_Automacao`.
Origem: `ZNX_NFSE_AUTOMACAO-main.zip`, preservado no diretório Downloads do usuário.
O material anexado foi usado como contexto da migração; o escopo imediato é o
login descrito na mensagem atual. As etapas fiscais não observadas não foram
implementadas por suposição.

## Arquitetura encontrada antes das alterações

| Área | Implementação original | Decisão SAT |
| --- | --- | --- |
| Desktop | `electron/main.js`, janela principal, splash, IPC/preload isolado | Reutilizar; separar produto e dados |
| Interface ativa | React em `electron/renderer/src/main.jsx`, CSS e Framer Motion, compilados por Vite | Adaptar campos e textos; manter layout/sidebar/componentes |
| Interface antiga | `renderer/js`, `renderer/css`, GUI Python/Tk | Não utilizar, pois não são a interface ativa |
| Inicialização | Electron reserva porta livre, cria token aleatório, inicia Python e espera `/health/auth` | Preservar handshake e ciclo de vida |
| Comunicação | Renderer → `electronAPI` → IPC → main → HTTP loopback FastAPI | Preservar token e cabeçalho de licença |
| Jobs | `Job`, thread em background, `threading.Event`, deque de logs, status/cancelamento por ID | Preservar; acrescentar progresso e resultados estruturados |
| Cadastro | XLSX local ou servidor remoto; overlays locais de seleção/credenciais | Adaptar nomes SAT, importar aliases, separar armazenamento remoto por padrão |
| Login NFSe | `portal_auth.py` usa Playwright/Chromium | Manter Playwright; criar `sat_auth.py` com regras específicas SAT |
| Motor fiscal NFSe | `nfse_automacao.py` baixa via ADN/mTLS, certificados PFX, relatórios XML/ISS e importação Domínio | Não transportar para o motor SAT |
| Licenciamento | Electron e Python validam remotamente; identidade derivada de hostname/arquitetura/SO; chave local no userData | Preservar contrato, módulo e client; não alterar servidor |
| Build | PyInstaller `api/server.spec` + Vite + electron-builder/NSIS | Adaptar imports, nomes e script; não incluir configurações privadas |
| Atualização | electron-updater ligado ao GitHub da NFSe | Preservar mecanismo, aguardando feed próprio SAT |

O login NFSe existente era uma validação paralela ao motor ADN. Não era suficiente
trocar sua URL: o motor continuaria dependendo de certificados e do portal nacional.
A substituição ficou restrita ao motor fiscal e à integração necessária no cadastro,
API, interface e empacotamento.

## Arquivos e migração

Criados: `app/automation/sat_auth.py`, `sat_automacao.py`, `sat_downloader.py`,
testes SAT/API, utilitários de inspeção/teste e documentação.

Adaptados da base: `api/server.py`, `api/server.spec`, `api/version_info.txt`,
`app/config/config_defaults.py`, scripts de inicialização/build, dependências,
`electron/main.js`, renderer React, metadados, splash e configuração do pacote.

Reutilizados sem alterações de conteúdo: `api/license.py`,
`electron/license-client.js`, `electron/preload.js`, `electron/dev-runner.js`,
`electron/vite.config.js`, estilos ativos, ícones, logo e vídeo da splash.

Não utilizados no projeto SAT: `adn_client.py`, `cert_reader.py`, `cert_manager.py`,
`nfse_automacao.py`, `portal_auth.py`, `dominio_importer.py`, `path_finder.py`,
relatório de XML/ISS NFSe, GUI Tk, extensão NFSe, scripts legados de reinstalação,
publicação e atualização NFSe, servidores de licença Java/Node (continuam na origem;
o cliente usa o serviço existente), perfis Chrome, caches e binários do ZIP.

O inventário detalhado está em [INVENTARIO.md](INVENTARIO.md).

## Login implementado

`login_sat(page, usuario, senha)` é responsável por navegar à URL oficial, aguardar
os campos, preencher, acionar o link real Entrar e observar a resposta. O chamador
controla o ciclo de vida do navegador. O fluxo não envia requisições HTTP de login,
não manipula viewstate e não acessa o botão de certificado.

Os seletores iniciais foram confirmados no DOM de uma página pública real com
Chrome/Playwright. Evidência sem valores de campos em
[sat-dom-observado.json](sat-dom-observado.json). Fonte:
[página oficial do SAT](https://sat.sef.sc.gov.br/tax.NET/Login.aspx).

O link Entrar usa `__doPostBack`; o formulário inclui estados hidden ASP.NET.
O carrossel de seleção de usuário está no HTML inicial, porém invisível. A detecção
usa visibilidade e não apenas presença no DOM.

| Retorno | Interpretação no job |
| --- | --- |
| `success=true` | Indicador positivo configurado está visível e campo de senha ausente |
| `INVALID_CREDENTIALS` | Mensagem explícita reconhecida ou indicador real configurado |
| `PORTAL_ERROR` | Erro HTTP de navegação, indisponibilidade ou indicador de erro |
| `USER_SELECTION_REQUIRED` | Seleção visível, sem escolha automática; pendente |
| `ADDITIONAL_STEP` | Janela/diálogo/tela adicional não confirmada; pendente |
| `UNCONFIRMED` | Espera esgotada sem resultado comprovado; pendente |
| `LAYOUT_CHANGED` | Campos não encontrados/preenchidos; erro seguro |
| `MISSING_CREDENTIALS`, `BROWSER_ERROR` | Falha local por empresa, sem interromper as próximas |

Postbacks e redirecionamentos são acompanhados por polling limitado. Janelas novas
do mesmo contexto recebem observadores; diálogos são classificados e dispensados,
sem copiar seu conteúdo para o resultado. Não há repetição automática de credenciais.
O cancelamento é cooperativo, verificado entre ações e durante espera. Uma ação
Playwright em curso pode levar até 15 s; a inicialização do navegador tem o limite
do Playwright. Não se mata um navegador compartilhado ou uma instância da NFSe.

`SAT_SELECTOR_LOGIN_OK` fica vazio até observação com a conta de teste. As frases
genéricas de erro têm testes de classificação, mas sua forma exata no SAT ainda
precisa ser homologada. Sem evidência suficiente o retorno é pendente, nunca um
sucesso presumido. O campo de configuração permite inserir indicadores reais.

## API, progresso e empresas

Endpoints preservados: `GET/POST /clientes`, `POST /clientes/importar`,
`GET/POST /config`, `POST /executar`, `GET /executar/{id}/status`,
`POST /executar/{id}/cancelar`, `/health` e `/health/auth`.

Uma única execução fica ativa por vez. `/executar` aceita `modo=login` e
`tipoLogin=usuario_senha`; rejeita certificado/download. Valida as datas antes de
criar a thread, seleciona somente clientes ativos e processa as empresas em contextos
de navegador separados. O erro de uma empresa não impede a próxima.

O status inclui `progress` (total, processados, empresa, etapa e resultados já
concluídos) e `resultado` (sucessos, erros e pendências). O frontend usa esses dados;
não infere sucesso ao aparecer a próxima empresa ou ao terminar o job. Um job pode
terminar com erro ou pendência apesar de ter processado todas as empresas. Resultados
anteriores são preservados no cancelamento.

## Credenciais e limitações herdadas

- Senha mascarada no formulário. Logs e resultados SAT usam mensagens fixas, sem
  usuário, senha, traceback Playwright, corpo do portal ou URL de retorno.
- Exceções de preenchimento, clique e navegação são convertidas em códigos seguros.
  Não são gravados screenshots, cookies, vídeos ou traces da sessão autenticada.
- Logs do job são limitados ao logger SAT e à thread correspondente. O erro de
  validação de requisição não devolve seu corpo, que poderia conter segredos.
- Credenciais locais são armazenadas em texto recuperável no XLSX e JSON, como na
  base. Não houve migração para banco/cofre. Os arquivos ficam ignorados pelo Git.
  O instalador recebe somente o backend compilado e os arquivos de interface.
- Células que começam com `=` são gravadas como texto para preservar senhas e nomes.
- O cliente de licença original contém um segredo compartilhado embutido, e a UI
  contém uma senha fixa para o modo desenvolvedor. São limitações herdadas; essa
  senha da UI não substitui a checagem remota de licença da API.
- O contrato remoto original não distingue produtos. Separação comercial de licenças
  SAT/NFSe requer definição no servidor, sem mudar o serviço em uso nesta entrega.

## Homologação pendente

Necessário fornecer/observar: conta SAT de teste autorizada, indicador positivo de
sessão, mensagens reais de rejeição, opções e regra da seleção de perfil, possíveis
etapas adicionais, aplicação CONX, consulta/período/pesquisa/resultados/download.
Pode-se cadastrar a conta diretamente no aplicativo, sem enviar a senha em mensagens.

Consulta, download, nomes de aplicações, URLs internas, contagem fiscal, XML e
relatórios NFC-e permanecem pendentes. `sat_downloader.py` gera erro explícito se
for chamado antes do mapeamento, em vez de simular arquivos ou estatísticas.

O Chrome instalado é pré-requisito do computador de destino. Instalador sem
assinatura digital e funcionamento em outras máquinas precisam de homologação.
Builds não são publicados; o canal de atualização SAT precisa ser definido.

## Como operar e validar

Comandos de desenvolvimento, testes e build estão no [README](../README.md).
O teste manual `tools/test_sat_login.py` mantém a página aberta para a observação
do próximo estado com entrada oculta das credenciais. O teste de execução normal
fecha o contexto ao terminar cada empresa.

Próxima ação: observar uma tentativa com conta de teste e configurar o indicador
positivo real. Depois validar seleção/perfil e somente então mapear a consulta.
