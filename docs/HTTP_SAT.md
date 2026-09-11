# Transporte HTTP SAT — 0.4.0

## Implementação realizada

`abrir_sessao` cria `ClienteSATHTTP` com uma sessão requests por job. Não importa
Playwright nem inicializa navegador. Mantém cookies, aceita somente a origem
HTTPS SAT observada e valida redirecionamentos antes de transmitir a requisição.
Redirecionamentos 302/303 após POST descartam o corpo. Erros e resultados não
incluem requisições, campos secretos ou exceções de transporte.

O login lê os names dos campos e o evento do link real; envia os campos hidden
ASP.NET atuais junto às credenciais. A confirmação usa os elementos do cabeçalho
/rodapé autenticado no HTML, em vez do componente de busca criado pelo JavaScript.
Seleções de perfil ocultas e mensagens de validação ocultas não confirmam erro.

A navegação usa o `window.open` literal observado no link exato **NFe / NFCe -
Consulta**, cujo destino é `Go.ashx?app=DFE00116&source=...`; acompanha a resposta
HTTP até o formulário. Não executa JavaScript arbitrário e não chuta a URL final.
O destino observado foi `/tax.NET/Sat.NFe.Web/Consultas/ConsultaOnlineCC.aspx`.

A consulta oferece tipo NFC-e (valor 20), emitente/destinatário, período e situação.
O campo `Body_Main_Main_sepConsultaNfpe_capValidacao` está presente e obrigatório,
com carregamento de `challenges.cloudflare.com/turnstile/v0/api.js`. A execução
registra pendência ao encontrá-lo, sem enviar a busca nem abrir navegador.
Não há suporte confirmado a XML pelo botão Exportar desse formulário.

## Teste autorizado

65 testes automatizados aprovados. Login HTTP real confirmado. No teste com CNPJ
35.693.867/0001-54 e agosto/2026, a sessão autenticou e abriu a consulta, que exigiu
validação humana. Zero documentos; a busca fiscal por esse CNPJ não foi enviada.
Isso não permite concluir se existem notas ou se a conta tem vínculo com a empresa.
O resultado sem credenciais está em `TESTE_CLIENTE_HTTP.json`.

## API oficial de XML — teste posterior com certificado

A [SEF informa](https://www.sef.sc.gov.br/saiba-mais/web-service-para-download-de-nfce)
que o serviço de distribuição NFC-e requer certificado ICP-Brasil de contador
vinculado ao contribuinte e está em regime de testes na data desta validação.
Não aceita a senha do portal como substituta do certificado.

O [BT SC-2026/003, versão 1.00-1](https://www.sef.sc.gov.br/api/download?id=8609&mime=application/pdf&nomeArquivo=BT+2026-003+-+Servico+de+Distribuicao+de+Nota+Fiscal+de+Consumidor+Eletronica++-+v100-1.pdf)
documenta SOAP `nfceDownloadContab`, TLS com autenticação mútua e a URL
`https://dfe.sat.sef.sc.gov.br/nfce/ws/distribuicao/DistribuicaoNfceDownload.asmx`.
A integração Python agora guarda continuação por CNPJ/NSU e respeita os intervalos
do serviço. Com o A1 fornecido posteriormente, a API autorizou o CNPJ do teste e
entregou 1.187 NFC-e e 9 eventos de agosto/2026. Consulte [API com A1](API_NFCE.md).
O instalador 0.4.0 ainda corresponde ao fluxo de portal documentado acima.
