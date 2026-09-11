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
nos argumentos do comando. Na versão **0.5.1**, o mesmo fluxo está ligado à tela
Executar e ao instalador. A interface usa a API com A1 por padrão e gera os
relatórios automaticamente ao terminar os jobs. O comando acima continua útil
para diagnóstico de download pelo terminal.

Os relatórios seguem o Excel da NFSe, adaptado para NFC-e: Resumo, NFC-e,
Canceladas, Itens e Eventos. Cada empresa tem somente as pastas `Relatorio` e
`XMLs`; erros e cancelamentos aparecem no relatório da própria empresa. O nome e
a senha do certificado não aparecem no relatório. Arquivos são abertos pelos
botões da interface, que aceitam apenas artefatos registrados no job.

Cancelamentos consideram tipos 110111/110112 com retorno 135/155 e chave/tipo
correspondentes. Referência: [NT 2018.004, portal oficial NF-e](https://www.nfe.fazenda.gov.br/PORTal/exibirArquivo.aspx?AspxAutoDetectCookieSupport=1&conteudo=DEisbx2XCIs%3D).
Eventos posteriores às datas consultadas são considerados quando já distribuídos
e vinculados a uma nota do relatório. Valores de eventos não são somados aos das notas.

## Protocolo e continuação

Implementado conforme a [página oficial da SEF](https://www.sef.sc.gov.br/saiba-mais/web-service-para-download-de-nfce)
e o [BT SC-2026/003 v1.00-1](https://www.sef.sc.gov.br/api/download?id=8609&mime=application/pdf&nomeArquivo=BT+2026-003+-+Servico+de+Distribuicao+de+Nota+Fiscal+de+Consumidor+Eletronica++-+v100-1.pdf):

- SOAP `nfceDownloadContab`, TLS 1.2 com certificado do contador vinculado ao CNPJ.
- Resposta XML compactada em gzip/base64, até 50 documentos por lote.
- Lotes completos continuam pelo NSU retornado. Lote menor que 50 ou status 117
  encerra a rodada e exige esperar 12 horas. Status 110 aguarda uma hora.
- Checkpoint gravado após cada lote. Tentativa é reservada antes da rede para
  impedir repetição imediata após erro de resultado incerto. Lock impede duas
  consultas simultâneas para a mesma empresa/filtro.
- A distribuição oferece mês atual e dois meses anteriores, com possível atraso
  de disponibilização. O filtro por período é local; uma rodada concluída significa
  que os documentos atualmente distribuídos foram recebidos, não comprova que
  um período fora dessa janela esteja completo. Cache já obtido é preservado.

Durante as 12 horas, o aplicativo reexporta os lotes locais sem consulta remota.
O estado NSU fica na área interna do aplicativo, fora da pasta da empresa. Se
outra instalação usar a mesma conta, seus intervalos também precisam ser coordenados.

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

Os testes automatizados cobrem SOAP, gzip, assinatura, normalização, erro de
certificado, continuidade, falhas, cancelamento, intervalos, integração dos jobs,
relatórios, valores decimais e células textuais. Usam documentos sintéticos, sem
certificado ou XML de produção. A validação manual real é registrada separadamente.
