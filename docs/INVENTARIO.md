> Versão atual: **0.3.0 — usuário e senha**, conforme [LOGIN_USUARIO_SENHA.md](LOGIN_USUARIO_SENHA.md). O fluxo por certificado abaixo é histórico e foi substituído.

# Inventário da entrega

Comparação de conteúdo com o ZIP NFSe fornecido. Caches, dependências instaladas e builds são excluídos desta lista.

## Reutilizados sem alteração

- `app/__init__.py`
- `app/automation/__init__.py`
- `app/config/__init__.py`
- `electron/assets/automacoes_loading.mp4`
- `electron/assets/icon.ico`
- `electron/assets/icon.png`
- `electron/dev-runner.js`
- `electron/renderer/public/logo.png`
- `electron/renderer/src/styles.css`
- `electron/vite.config.js`

## Adaptados

- `electron/preload.js`

- `.gitignore`
- `CONSTRUIR_INSTALADOR.bat`
- `INICIAR.bat`
- `api/server.py`
- `api/server.spec`
- `api/version_info.txt`
- `app/config/config_defaults.py`
- `electron/main.js`
- `electron/package-lock.json`
- `electron/package.json`
- `electron/renderer/index.html`
- `electron/renderer/src/main.jsx`
- `electron/splash.html`
- `requirements.txt`

## Criados

- `README.md`
- `app/automation/sat_auth.py`
- `app/automation/sat_automacao.py`
- `app/automation/sat_downloader.py`
- `app/automation/sat_session.py`
- `docs/CERTIFICADO_CONTADOR.md`
- `docs/modelo_clientes.xlsx`
- `docs/RELATORIO_TECNICO.md`
- `docs/INVENTARIO.md`
- `docs/VALIDACAO.md`
- `docs/sat-dom-observado.json`
- `requirements-dev.txt`
- `tests/conftest.py`
- `tests/test_api.py`
- `tests/test_sat_auth.py`
- `tests/test_sat_automacao.py`
- `tools/inspect_sat_login.py`
- `tools/smoke_electron.py`
- `tools/smoke_renderer.py`
- `tools/test_sat_login.py`

## Principais itens da origem não utilizados

Motor ADN, certificados, login nacional NFSe, Domínio, GUI Tk, relatórios XML/ISS, perfis Chrome, frontends antigos, servidores de licenciamento e scripts de publicação NFSe. A origem permanece no ZIP.

## Removidos na versão 0.1.1

- `api/license.py`
- `electron/license-client.js`

Removidos também os endpoints, IPCs, painéis e bloqueios de licenciamento, além da sincronização de clientes com o antigo servidor de licenças.

## Alteração 0.2.0

Autenticação com certificado único do contador, sessão compartilhada por todos os
clientes e planilha somente NOME/CNPJ. Detalhes em `CERTIFICADO_CONTADOR.md`.
