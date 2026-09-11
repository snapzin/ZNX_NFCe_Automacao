# ZNX SAT 0.5.1 — primeiros passos

1. Instale **ZNX-SAT-Setup-0.5.1.exe** e abra o aplicativo. Não precisa instalar
   Python, Node.js ou navegador para os downloads.
2. Em **Clientes**, importe a planilha com duas colunas: **NOME** e **CNPJ**.
   Clique em **Salvar** e marque as empresas que deseja processar.
3. Em **Executar**, mantenha **API NFC-e — certificado A1 do contador**.
   Selecione o arquivo `.pfx` ou `.p12` e digite sua senha. Um certificado atende
   todas as empresas às quais o contador tem acesso na SEF.
4. Selecione o período e clique em **Executar agora**. Por padrão, é usado o mês
   anterior. A API disponibiliza o mês atual e os dois anteriores.
5. Ao terminar, abra o relatório da empresa, a pasta `Relatorio` ou a pasta `XMLs`
   pelos botões da tela.

## O que o Excel mostra

Na pasta de saída, cada cliente aparece somente como:

```text
Nome da empresa/
├── Relatorio/
└── XMLs/
```

O Excel tem as abas **Resumo, NFC-e, Canceladas, Itens e Eventos**.
Mostra quantidades, valores, produtos, impostos informados no XML e cancelamentos
identificados. Erros e pendências aparecem no relatório da respectiva empresa.
A aba Canceladas é um recorte das notas: não some seus valores novamente ao total.

## Mensagens que podem aparecer

- **Arquivos exportados do cache:** os XMLs locais foram reaproveitados. A SEF
  exige esperar 12 horas após concluir uma rodada de distribuição.
- **Requisitante não é contabilista do CNPJ:** confira o vínculo dessa empresa
  com o contador na SEF. Os demais clientes continuam sendo processados.
- **Não foi possível abrir o certificado:** confira arquivo, senha e validade.
- **SAT exige validação humana:** está selecionado o modo antigo do portal.
  Volte para **API NFC-e — certificado A1 do contador**.

Certificado e senha não acompanham o instalador e não ficam gravados no cadastro
dos clientes. Informe-os a cada execução. Os relatórios e XMLs ficam na pasta de
saída indicada em **Configurações**.

O controle de continuação da API é mantido internamente pelo aplicativo. Trocar
de máquina não elimina o intervalo de espera imposto pela SEF.
