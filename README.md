# ZNX NFC-e / SAT — versão 0.5.1

Download pela API oficial da SEF/SC com um único certificado A1 do contador,
sem abrir navegador. Relatório Excel dentro da pasta de cada empresa ao final da
execução. Aplicativo separado da automação NFSe original, sem licença ou ativação.

## Instalar e executar

1. Instale `electron/dist/ZNX-SAT-Setup-0.5.1.exe` no Windows. Não exige Python,
   Node.js ou Chrome na máquina do cliente.
2. Em **Clientes**, importe a planilha com **NOME** e **CNPJ**, salve e selecione
   as empresas. [Planilha modelo](docs/modelo_clientes.xlsx).
3. Em **Executar**, mantenha **API NFC-e — certificado A1 do contador**, selecione
   o `.pfx`/`.p12` e informe a senha. Certificado e senha são usados só nesta execução.
4. Use o mês anterior ou escolha datas no mês atual e nos dois meses anteriores,
   conforme a disponibilidade da distribuição SEF.
5. Clique **Executar agora**. Acompanhe cada empresa e, ao concluir, use os botões
   **Relatório da empresa**, **Pasta Relatorio** e **Pasta dos XMLs**.

O instalador não contém certificado, senha, cadastro ou documentos fiscais.
Na versão instalada, os dados ficam na pasta local de dados do aplicativo.
A pasta de saída pode ser consultada e alterada em **Configurações**.

## Relatórios

Cada empresa tem somente duas pastas visíveis na pasta de saída:

```text
Nome da empresa/
├── Relatorio/
│   └── Relatorio_NFCe_DATA_INICIAL_a_DATA_FINAL.xlsx
└── XMLs/
    ├── NFCe_*.xml
    └── Evento_*.xml
```

Não é criada pasta por CNPJ, período, execução, `api_sef`, NFC-e ou Eventos.
O controle de NSU e os lotes técnicos ficam na área interna do aplicativo.

Cabeçalhos coloridos, filtros, painéis congelados, valores numéricos em reais,
chaves/CNPJs como texto e totais por aba. Os cancelamentos são vinculados às notas
por eventos aceitos; eventos posteriores já presentes no cache também são considerados.
A aba Canceladas é um recorte das NFC-e e não deve ser somada novamente.
O relatório da empresa mostra o que foi distribuído; não afirma ausência de notas fora da
janela disponível nem substitui apuração fiscal.

## Validação real

O A1 fornecido autorizou o CNPJ **35.693.867/0001-54** na API da SEF. Agosto/2026:
**1.187 NFC-e, 2.547 itens e 9 eventos de cancelamento**. Digest e assinatura dos
XMLs conferidos. Relatórios gerados a partir desses arquivos, sem nova busca
durante o intervalo da SEF. [Detalhes](docs/API_NFCE.md).

O modo opcional **Portal SAT — usuário e senha** mantém o acesso HTTP anterior.
A mensagem `HUMAN_VALIDATION_REQUIRED` pertence a esse modo; para o download
automático de XML, use a opção padrão com certificado.

## Desenvolvimento

Instale `requirements-dev.txt`, execute `python -m pytest -q` e compile a interface
com `npm.cmd run build:renderer` na pasta `electron`. Valide com os comandos
`python tools/smoke_renderer.py` e `python tools/smoke_electron.py`.

`INICIAR.bat` executa o projeto em desenvolvimento. `CONSTRUIR_INSTALADOR.bat`
testa, compila o backend e gera o instalador, nessa ordem. Não publica arquivos.
Smoke do aplicativo instalado: `tools/smoke_electron.py --packaged`.
Acrescente `--certificate-test` somente para repetir o teste autorizado do CNPJ
acima usando o cache local e entradas ocultas do certificado.

O comando `tools/baixar_nfce_api.py` continua disponível para uso pelo terminal.
Playwright é usado apenas nos testes da interface; está excluído do backend.
