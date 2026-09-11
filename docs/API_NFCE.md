# Distribuição NFC-e SC com certificado A1

Teste autorizado em 11/09/2026, CNPJ 35.693.867/0001-54, emissão de 01/08/2026
a 31/08/2026, filtro emitente (`indAtor=1`). A autenticação mútua com o certificado
fornecido retornou `cStat=118`. Resultado: **1.187 notas e 9 eventos**, último NSU
11962. A data dos eventos é `dhEvento`; a das notas é `dhEmi`.

O ZIP está em `Downloads/35693867000154/NFCe_35693867000154_2026-08.zip`.
O relatório [TESTE_CERTIFICADO_API.json](TESTE_CERTIFICADO_API.json) contém contagens
e hash do ZIP, sem credenciais ou informações dos consumidores.

## Executar

Instale `requirements.txt` no ambiente Python do projeto e execute:

```powershell
.\.venv\Scripts\python.exe tools/baixar_nfce_api.py --cnpj 35693867000154 --inicio 2026-08-01 --fim 2026-08-31
```

Informe caminho e senha do A1 nas entradas ocultas do terminal. Não inclua senha
nos argumentos do comando. O fluxo SOAP funciona pelo terminal; ainda não está
ligado aos jobs da interface nem incorporado no instalador 0.4.0.

## Protocolo e continuação

Implementado conforme a [página oficial da SEF](https://www.sef.sc.gov.br/saiba-mais/web-service-para-download-de-nfce)
e o [BT SC-2026/003 v1.00-1](https://www.sef.sc.gov.br/api/download?id=8609&mime=application/pdf&nomeArquivo=BT+2026-003+-+Servico+de+Distribuicao+de+Nota+Fiscal+de+Consumidor+Eletronica++-+v100-1.pdf):

- SOAP `nfceDownloadContab`, TLS 1.2 com certificado do contador vinculado ao CNPJ.
- Resposta XML compactada em gzip/base64, até 50 documentos por lote.
- Lotes completos continuam pelo NSU retornado. Lote menor que 50 ou status 117
  encerra a rodada e exige esperar 12 horas. Status 110 aguarda uma hora.
- Checkpoint gravado após cada lote. Tentativa é reservada antes da rede para
  impedir repetição imediata após erro de resultado incerto. Lock impede duas
  consultas simultâneas para a mesma empresa/filtro nesta pasta de saída.
- A distribuição oferece mês atual e dois meses anteriores, com possível atraso
  de disponibilização. O filtro por período é local; uma rodada concluída significa
  que os documentos atualmente distribuídos foram recebidos, não comprova que
  um período fora dessa janela esteja completo. Cache já obtido é preservado.

Durante as 12 horas, o comando reexporta os lotes locais sem consulta remota.
Preserve `api_sef/estado.json` junto aos lotes. Se outra instalação usar a mesma
conta, seus intervalos também precisam ser coordenados.

## Integridade e dados locais

Os lotes reais vieram indentados. A extração primeiro verifica o documento como
recebido. Só remove indentação se o resultado conferir com o digest e a assinatura
RSA originais; falha de integridade interrompe a exportação. Conteúdo textual
dos campos não é reformatado. Lotes originais permanecem no cache. Nos 1.196 XMLs
exportados, digest e assinatura conferiram, sem duplicação de identificadores.
Esta verificação não valida schema fiscal, cadeia ICP-Brasil ou revogação.

Chave e senha não são gravadas pelo código da aplicação. A biblioteca TLS usa um
arquivo temporário com chave cifrada por senha aleatória, removido após carregar
o contexto. Erros não reproduzem o caminho do certificado nem dados de requisição.
Certificados e `Downloads/` estão excluídos do Git.

80 testes automatizados aprovados, incluindo 15 novos para SOAP, gzip, assinatura,
normalização, erro de certificado, continuidade, falhas, cancelamento e intervalos.
Os testes usam documentos sintéticos, sem certificado ou XML de produção.
