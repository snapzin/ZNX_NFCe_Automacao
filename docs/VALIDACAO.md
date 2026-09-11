# Versão 0.5.1 — saída simplificada por empresa

Após cada operação, a pasta de saída contém uma pasta pelo nome da empresa e,
dentro dela, somente `Relatorio` e `XMLs`. NFC-e e eventos ficam juntos em XMLs,
identificados pelo prefixo do arquivo. Não são expostas pastas de CNPJ, período,
job, API, tipo de documento ou estado NSU. O controle técnico fica na área interna
do aplicativo. Nomes repetidos recebem o CNPJ para evitar mistura de empresas.

90 testes automatizados aprovados. Interface compilada e Electron real aprovados.
O aplicativo empacotado 0.5.1 também abriu e executou o fluxo com o A1 autorizado
sobre o cache real: 1.187 NFC-e, 9 eventos, relatório produzido e status ok. A
pasta real de demonstração ficou com exatamente duas subpastas e 1.196 XMLs.

Instalador 0.5.1: 103.284.690 bytes, SHA-256
`c5e71661c7d010625d37671078d9ee27e5b371731aec52982fd09db2dc8a36f4`.
Pacote de entrega: ENTREGA_0.5.1.json.

# Versão 0.5.0 — aplicativo com A1 e relatórios

API oficial conectada à tela Executar, como opção padrão. Um certificado por job,
planilha somente nome/CNPJ, senha e caminho do A1 fora da configuração e dos logs.
Relatório Excel por empresa, com botões para abrir o arquivo e as duas pastas.

89 testes automatizados aprovados. UI compilada: seletor A1, senha limpa ao iniciar,
requisição correta, botões dos relatórios, cadastro sem credenciais e modo de portal
preservado. Electron real em desenvolvimento e aplicativo empacotado aprovados.

O aplicativo empacotado processou o certificado autorizado e os XMLs reais já
distribuídos para 35.693.867/0001-54, agosto/2026: 1.187 NFC-e, 9 eventos e relatório
com 2.547 itens e 9 cancelamentos identificados. Origem desta rodada: cache local,
respeitando a espera da SEF. Não foi feita nova requisição fiscal neste teste.
Relatórios produzidos pelo backend empacotado, status ok, sem erro ou segredo no
resultado. Evidência: TESTE_APP_CERTIFICADO.json.

Instalador 0.5.0: 103.283.670 bytes, SHA-256
`1393120426654b75d6537fee4aa76b189c9b8aa57e23e1c25d8e1364e5c6a97c`.
Pacote de entrega inclui instalador, guia e planilha modelo; não contém certificado,
senha, cadastro real ou documentos fiscais. Hashes: ENTREGA_0.5.0.json.

O teste abriu os binários empacotados sem efetuar instalação no Windows. Abertura
dos destinos dos relatórios foi validada via IPC/API; o Excel do sistema não foi
iniciado automaticamente. Persistem dois avisos de depreciação TestClient/AnyIO
nos testes e avisos de dependências opcionais no build, sem impedir a execução.

# Teste posterior com A1 — API oficial (antes da integração)

Certificado aceito e acesso autorizado ao CNPJ 35.693.867/0001-54. Baixados
1.187 XML de NFC-e e 9 XML de eventos de agosto/2026. Digest e assinatura RSA
dos 1.196 documentos conferidos após tratamento da indentação do lote da SEF.
Último NSU 11962; lotes originais e checkpoint preservados. ZIP sem certificado.

80 testes aprovados (15 novos), com dois avisos de depreciação existentes no
TestClient/AnyIO. Implementação disponível no comando `tools/baixar_nfce_api.py`;
interface e instalador 0.4.0 não foram alterados neste teste. Consulte API_NFCE.md
e TESTE_CERTIFICADO_API.json.

# Versão 0.4.0 — HTTP sem navegador

65 testes aprovados, incluindo cookies/sessão compartilhada, formulários e estados
ASP.NET, restrição de origem, credenciais omitidas e pendência por Turnstile.
Login por requests confirmado com a conta autorizada. Teste do cliente
35.693.867/0001-54 (agosto/2026): login confirmado, CAPTCHA requerido, zero XML,
busca fiscal não enviada. Evidência em TESTE_CLIENTE_HTTP.json.

O backend usa HTTP e a distribuição PyInstaller exclui Playwright. A API oficial
SOAP de XML exige certificado e ainda não estava integrada naquela versão. Consulte HTTP_SAT.md.

Interface compilada e Electron real (desenvolvimento e empacotado) aprovados:
abre sem licença, campos usuário/senha presentes, configuração HTTP disponível,
Clientes acessível e token Electron/API confirmado.

Instalador 0.4.0: `electron/dist/ZNX-SAT-Setup-0.4.0.exe` (97310115 bytes).
SHA-256: `cd445ef000ae0182b8589d9badcb7ab46adeb6e013c8c426a5be2670c6363b3f`.

# Versão 0.3.0 — usuário e senha

Em 11/09/2026, o navegador real preencheu os campos SAT observados, clicou Entrar
e chegou à tela de aplicações. A versão final do módulo retornou:

```json
{"success": true, "requires_user_selection": false, "error_type": "", "message": "Login realizado"}
```

O indicador autenticado teve contagem 1, assim como rodapé e busca; formulário
inicial ausente. Nenhuma seleção de perfil foi necessária nessa conta. Nenhuma
consulta fiscal ou download foi submetido. Credenciais não foram salvas.

49 testes automatizados passaram. Inspeção da página pública confirmou os três
campos/controles de login únicos e visíveis, sem falso indicador de sucesso.
Interface compilada aprovada: nome/CNPJ, senha global mascarada, limpa ao iniciar,
requisição de usuário/senha e apresentação correta de pendências.

Abertura Electron real em desenvolvimento: sem ativação, clientes acessíveis,
comunicação autenticada com FastAPI. Consulte LOGIN_USUARIO_SENHA.md para escopo
atual e limites do download ainda não mapeado.

Backend e instalador 0.3.0 recompilados. Aplicação empacotada aprovada: abre sem
licença, mostra usuário/senha, oferece cadastro de clientes e confirma o token
Electron/FastAPI. A configuração embarcada contém o indicador de login observado
e não oferece certificado.

Instalador: `electron/dist/ZNX-SAT-Setup-0.3.0.exe` (123150200 bytes).
SHA-256: `17dc1047cc4a405db42dfb3c47d9d93da939d2103c80993e804d14a64eb2f295`.

# Validação histórica da versão 0.1.1 — remoção do licenciamento

Solicitação atendida: aplicativo e API sem exigência de licença. Removidos o
cliente remoto, endpoints de licença, painel de máquinas, tela de ativação,
verificações antes de executar e sincronização com o antigo servidor. Cadastro
local e proteção pelo token de sessão Electron/API permanecem.

Validação local: 34 testes aprovados, Electron abre diretamente e permite acessar
Clientes sem chave; interface compilada passou no teste de cadastro, senha mascarada
e apresentação de pendências. O teste do Electron usa a API real sem simular licença.

Backend e instalador recompilados. A aplicação empacotada também abriu diretamente,
permitiu acessar Clientes e confirmou a comunicação autenticada com a API local.
O módulo `license.py` não está presente no backend empacotado.

Instalador daquela versão: `electron/dist/ZNX-SAT-Setup-0.1.1.exe` (123147971 bytes).
SHA-256: `c7ec82507fe58fd738ecd155d4b4f5c21c03622dad7b4e327f4796db9392d887`.

# Validação histórica da versão 0.1.0

| Verificação | Resultado |
| --- | --- |
| Testes de autenticação, automação e API | 34 aprovados |
| Página pública real SAT com Chrome/Playwright | Campos de usuário/senha e Entrar únicos e visíveis; seleção de usuário oculta; nenhum login submetido |
| Build da interface React/Vite | Concluído |
| UI compilada com IPC simulado | Cadastro funcional, senha mascarada, pendência sem sucesso, nenhum erro JavaScript |
| Electron real em desenvolvimento | Iniciou; gate de licença visível; IPC → FastAPI `/health/auth` confirmado |
| PyInstaller | Backend compilado com sucesso |
| Backend `server.exe` | Iniciou com dados temporários; health autenticado respondeu; configuração local criada |
| electron-builder / NSIS | Instalador Windows x64 gerado, sem publicação |
| Electron empacotado (`win-unpacked`) | Iniciou; gate de licença visível; IPC → backend empacotado autenticado |

Ambiente: Windows 10 x64, Python 3.14.6, Playwright 1.62.0, Electron 29.4.6,
Vite 5.4.21, PyInstaller 6.22.2 e electron-builder 24.13.3.

Artefato: `electron/dist/ZNX-SAT-Setup-0.1.0.exe`, 123.679.992 bytes.

SHA-256 do instalador:
`58d5056f0280b9a7a751ec873e48a365799369a910a7f987200df8b5ee15fb0a`.

SHA-256 do ZIP original preservado:
`769c5c61b72dc30e78dda70c96d1939991e7ca3dcf780ce251f04478ca041180`.

Os testes de API usam licenciamento simulado somente em teste. A aplicação real
mantém a validação remota. Nenhuma licença foi ativada, nenhuma conta SAT foi
utilizada e nenhuma nota fiscal foi consultada ou baixada.

A suíte emitiu dois avisos de depreciação do TestClient/AnyIO. O build preservou
dependências Electron da base e concluiu com avisos de dependências opcionais; a
inicialização do produto empacotado foi verificada depois do build. Não foi executada
a instalação no Windows do usuário nem validada a assinatura do pacote, que não
está configurada.

Ainda não homologados: autenticação real, mensagens exatas de erro SAT, indicador
positivo autenticado, seleção de perfis, aplicações CONX, consulta/download e
funcionamento em outra máquina. Os campos dependentes desses dados permanecem
explicitamente pendentes.
