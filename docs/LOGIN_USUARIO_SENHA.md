# Login com usuário e senha — 0.3.0

Alteração solicitada em 11/09/2026: substituir o certificado global por usuário e
senha globais, mantendo uma sessão do contador para todos os CNPJs da execução.
Sem licença ou ativação. Planilha e cadastro somente NOME/CNPJ; ativo/inativo
permanece como seleção local da interface.

## Implementação

- `sat_auth.login_sat(page, usuario, senha, ...)`: abre a URL oficial, preenche os
  campos observados e clica Entrar uma vez. Respeita postbacks e acompanha popups,
  navegações, erros explícitos, seleção de perfil e cancelamento.
- `CredenciaisSAT`: valida dados em memória, exclui usuário/senha de `repr`.
  `SessaoSAT` remove sua referência às credenciais após autenticar.
- API recebe `credenciais: {usuario, senha}` em `/executar`, exige
  `tipoLogin: usuario_senha` e mantém dados secretos fora de configuração/log/job.
- Interface pede usuário/senha na execução, limpa o campo da senha ao iniciar e
  não persiste as credenciais. Certificado/PFX e seletor de arquivos removidos.
- Login confirmado não significa download concluído. A aplicação fiscal e suas
  consultas ainda precisam ser mapeadas. O job registra `FLOW_NOT_MAPPED` por CNPJ.

## Evidência do navegador real

URL inicial: https://sat.sef.sc.gov.br/tax.NET/Login.aspx

IDs únicos e visíveis confirmados na página pública:

- `Body_pnlMain_rptLoginPanels_tbxUsername_0`
- `Body_pnlMain_rptLoginPanels_tbxUserPassword_0`
- `Body_pnlMain_rptLoginPanels_btnLogin_0`

O título `h4.tit-pan-acc` de seleção está oculto inicialmente; só conta se visível.
O envio autorizado chegou à lista de aplicações em `/tax.NET/Apps.aspx`, sem
seleção intermediária nesta conta. A automação não navega diretamente para essa
URL interna. Foram observados o link `Body_ApplicationMasterFooter_hlkPolicy`
e o controle de busca com texto exato `Buscar aplicações...`; a combinação deles
é o indicador positivo configurado. Só confirma com formulário inicial ausente
e origem HTTPS oficial. Outros perfis e etapas desconhecidas permanecem pendentes.

O menu contém `NFe / NFCe - Consulta`, mas isso sozinho não confirma o fluxo de
consulta/download usado pela CONX. Nenhuma consulta fiscal foi submetida neste teste.

## Verificação

49 testes automatizados de autenticação, sessão compartilhada, API, planilha e
segredos. Teste da interface com IPC simulado verifica envio dos campos globais,
limpeza da senha, ausência de certificado e cadastro somente nome/CNPJ.
Inspeção pública confirma campos reais; teste autorizado confirma o acesso.

Credenciais reais não foram gravadas em arquivos, configuração ou documentação.
Testes automatizados usam exclusivamente dados fictícios.
