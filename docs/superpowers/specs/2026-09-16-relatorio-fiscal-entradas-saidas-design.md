# Relatório fiscal com entradas e saídas de NF-e e NFC-e

Data: 16/09/2026

## Objetivo

Baixar e consolidar, por empresa e período, os documentos fiscais eletrônicos nos quais a empresa participa como emitente ou destinatária. O relatório deve incluir NF-e modelo 55, NFC-e modelo 65 e seus eventos, separar entradas de saídas em relação ao CNPJ analisado e retirar documentos cancelados dos totais efetivos.

O mesmo certificado A1 do contador será usado nos dois serviços oficiais da SEF-SC, desde que o contabilista esteja vinculado à empresa consultada.

## Estrutura de saída

Cada período fica identificado dentro da pasta da empresa:

```text
Nome da empresa/
└── 08 - Agosto 2026/
    ├── Relatorio/
    │   └── Relatorio_Fiscal_2026-08-01_a_2026-08-31.xlsx
    └── XMLs/
        ├── NFe_2026-08-01_<NSU>.xml
        ├── NFCe_2026-08-01_<NSU>.xml
        ├── Evento_NFe_2026-08-05_<NSU>.xml
        └── Evento_NFCe_2026-08-05_<NSU>.xml
```

Intervalos que não correspondem a um mês completo usam `DD-MM-AAAA a DD-MM-AAAA` como nome da pasta do período. Os arquivos antigos `Evento_*.xml` continuam aceitos pelo gerador de relatório.

## Fontes fiscais

### NF-e modelo 55

Uma nova integração consumirá o Web Service de Distribuição de NF-e da SEF-SC, versão 2.02-1, no endpoint de produção documentado pela Secretaria. A consulta usará o filtro que inclui a empresa como emitente e destinatária e manterá continuação própria por NSU.

O serviço tem cache, checkpoint, bloqueio contra consultas simultâneas, tratamento dos intervalos obrigatórios e validação estrutural da resposta. As regras são independentes do cache de NFC-e.

### NFC-e modelo 65

A integração existente passará a pedir documentos em que a empresa aparece como emitente ou destinatária. Sua continuação por NSU será mantida em um cache específico do filtro usado.

### Integridade e deduplicação

Os XMLs completos e os eventos serão verificados antes da exportação. Notas serão deduplicadas pela chave de acesso e eventos pelo identificador fiscal do evento. Um mesmo documento encontrado em mais de uma fonte não poderá ser somado duas vezes. Conteúdos conflitantes para a mesma chave causarão erro explícito.

## Classificação do movimento

A classificação sempre será feita em relação ao CNPJ da empresa do relatório:

1. Se a empresa for destinatária e não for emitente, o documento será `Entrada`.
2. Se a empresa for emitente, `tpNF=0` será `Entrada` e `tpNF=1` será `Saída`. Isso cobre notas de entrada emitidas pela própria empresa.
3. Se emitente e destinatário forem a própria empresa, `tpNF` definirá o movimento.
4. Documento em que a empresa não seja emitente nem destinatária será rejeitado como não relacionado.
5. Modelo diferente de 55 ou 65 será rejeitado e não entrará nos totais.

O período será aplicado pela data de emissão `dhEmi`. Eventos posteriores poderão ser usados para atualizar a situação de uma nota do período quando já estiverem disponíveis no cache.

## Cancelamentos e valores

Um documento será considerado cancelado somente quando houver evento de cancelamento compatível com sua chave e tipo, acompanhado de retorno fiscal aceito. Eventos rejeitados não alteram a situação da nota.

As abas `Entradas` e `Saídas` conterão apenas documentos sem cancelamento identificado. A aba `Canceladas` conterá os documentos retirados dessas duas abas e informará qual era o movimento original.

O resumo mostrará separadamente, para entradas e saídas:

- quantidade e valor bruto localizado;
- quantidade e valor cancelado;
- quantidade e valor efetivo, sem canceladas.

Os totais monetários usarão valores decimais dos XMLs. Linhas repetidas em abas de conferência não serão somadas novamente no resumo.

## Relatório Excel

Será gerado um arquivo por empresa e período com estas abas:

- `Resumo`: cobertura das consultas, contagens, valores brutos, cancelados e efetivos;
- `Entradas`: NF-e e NFC-e classificadas como entrada e não canceladas;
- `Saídas`: NF-e e NFC-e classificadas como saída e não canceladas;
- `Canceladas`: documentos cancelados, com o movimento original;
- `Itens`: itens pertencentes aos documentos ativos de entrada e saída;
- `Eventos`: eventos relacionados, inclusive os posteriores ao período quando vinculados a uma nota incluída.

As linhas de notas e itens informarão modelo, movimento, emitente, destinatário, CFOP, situação, chave e arquivo de origem. Campos de identificação serão gravados como texto para preservar zeros e impedir interpretação como fórmula.

## Estado da execução e cobertura

NF-e e NFC-e terão resultados independentes. O resultado agregado seguirá estas regras:

- `Concluído`: as duas fontes concluíram a distribuição disponível e o relatório foi gerado;
- `Parcial`: pelo menos uma fonte produziu dados ou cache utilizável, mas a outra está pendente ou falhou;
- `Erro`: nenhuma fonte pôde produzir dados confiáveis para o relatório;
- `Cancelado`: a execução foi interrompida pelo usuário.

Um relatório parcial será identificado de forma visível no `Resumo`, indicando separadamente a situação de NF-e e NFC-e. A interface também exibirá o estado parcial. O programa não apresentará um total parcial como se fosse uma apuração completa.

## Fluxo do aplicativo

Para cada empresa selecionada, o job fará:

1. preparar o certificado uma vez;
2. consultar e exportar NF-e e eventos;
3. consultar e exportar NFC-e e eventos;
4. ler todos os XMLs exportados para o período;
5. deduplicar, classificar e aplicar cancelamentos;
6. gerar o Excel na pasta do período;
7. registrar a cobertura de cada fonte e liberar os botões para abrir relatório e pastas.

Falha em uma empresa não interromperá as seguintes. Segredos, caminhos do certificado e conteúdo fiscal não serão incluídos em logs ou mensagens de erro.

## Compatibilidade

O relatório continuará lendo os XMLs de NFC-e já baixados. A primeira execução com os novos filtros poderá iniciar uma sequência de NSU própria sem apagar o cache anterior. A pasta visível continuará contendo apenas `Relatorio` e `XMLs` dentro do período.

## Validação

Os testes automatizados cobrirão:

- requisição SOAP e leitura de lotes do serviço de NF-e;
- continuação por NSU, cache, intervalos e respostas de erro;
- NF-e modelo 55 e NFC-e modelo 65 como emitente e destinatária;
- notas próprias com `tpNF=0` e `tpNF=1`;
- deduplicação por chave e rejeição de documentos não relacionados;
- cancelamento aceito, rejeitado e posterior ao período;
- totais brutos, cancelados e efetivos de entradas e saídas;
- geração das seis abas e preservação dos campos textuais;
- execução parcial quando apenas uma fonte estiver disponível;
- seleção manual de período e pasta mensal;
- fluxo empacotado do aplicativo e geração do instalador.

A validação real com certificado respeitará os limites de consumo dos serviços. Se o serviço estiver em janela de espera, o teste usará o cache existente e registrará essa condição, sem repetir consultas prematuramente.
