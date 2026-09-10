# Validação realizada em 10/09/2026

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
