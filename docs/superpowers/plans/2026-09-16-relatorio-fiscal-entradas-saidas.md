# Relatório Fiscal de Entradas e Saídas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar por empresa e período um relatório único de NF-e modelo 55 e NFC-e modelo 65, separado em entradas, saídas e canceladas, com totais efetivos e cobertura explícita das duas fontes.

**Architecture:** Adicionar um cliente do serviço NF-e v2.02-1 da SEF-SC e generalizar a continuação por NSU já usada pela NFC-e. Um job fiscal consulta as duas fontes para cada CNPJ, exporta os XMLs na mesma pasta e entrega ao gerador Excel dados de cobertura independentes.

**Tech Stack:** Python 3, requests-pkcs12, lxml, cryptography, FastAPI, openpyxl, pytest, Electron/React, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-09-16-relatorio-fiscal-entradas-saidas-design.md`

## Global Constraints

- Usar somente os Web Services oficiais de NF-e e NFC-e da SEF-SC com TLS 1.2 e o certificado A1 informado em memória.
- Consultar a empresa como emitente e destinatária (`indAtor=9`) e preservar checkpoints separados por fonte e filtro.
- Manter dentro de cada período somente as pastas visíveis `Relatorio` e `XMLs`.
- Classificar o movimento em relação ao CNPJ analisado; para emissão própria, `tpNF=0` é entrada e `tpNF=1` é saída.
- Excluir canceladas das abas e totais efetivos de entradas e saídas.
- Não registrar senha, caminho do certificado ou conteúdo fiscal em logs e erros.
- Manter leitura compatível com arquivos NFC-e e eventos já exportados.

---

### Task 1: Transporte certificado e protocolo NF-e da SEF-SC

**Files:**
- Create: `app/automation/sat_sef_api.py`
- Create: `app/automation/sat_nfe_api.py`
- Modify: `app/automation/sat_nfce_api.py`
- Test: `tests/test_sat_nfe_api.py`
- Test: `tests/test_sat_nfce_api.py`

**Interfaces:**
- Produces: `CertificadoAPI`, `ErroAPI`, `LoteAPI`, `abrir_sessao_certificada(certificado, endpoints)` in `sat_sef_api.py`.
- Produces: `mensagem_nfe(cnpj, nsu=0, ator=9)`, `ler_resposta_nfe(data)` and `ClienteNFeAPI.consultar_lote(cnpj, nsu=0, ator=9)`.
- Preserves: public imports currently exposed by `sat_nfce_api.py`.

- [ ] **Step 1: Write the failing NF-e protocol tests**

```python
def test_nfe_request_uses_v2_namespace_and_both_roles():
    root = etree.fromstring(mensagem_nfe(CNPJ, 42))
    assert root.xpath('string(//*[local-name()="indAtor"])') == "9"
    assert root.xpath('string(//*[local-name()="ultNuNSU"])') == "42"
    assert root.xpath('string(//*[local-name()="CNPJ"])') == CNPJ

def test_nfe_response_opens_gzip_batch():
    raw = b'<loteDistNFeSC versao="2.00"/>'
    result = ler_resposta_nfe(soap_response("118", raw, 0, 0))
    assert result.codigo == "118" and result.lote_xml == raw
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sat_nfe_api.py -q`

Expected: collection fails because `app.automation.sat_nfe_api` does not exist.

- [ ] **Step 3: Extract shared certificate transport and implement NF-e v2**

```python
NFE_ENDPOINT = "https://satnfe.sef.sc.gov.br/ws/distribuicao/nfedownloadV2.asmx"
NFE_NAMESPACE = "http://www.satnfe.sef.sc.gov.br/ws/distribuicao-v2"

def mensagem_nfe(cnpj, nsu=0, ator=9) -> bytes:
    xml = (f'<distNFeSC versao="2.00" xmlns="{NFE_NAMESPACE}"><tpAmb>1</tpAmb>'
           f'<verAplic>ZNX-SAT-0.6.0</verAplic><cUF>42</cUF><CNPJ>{cnpj}</CNPJ>'
           f'<solRel><indXML>1</indXML><indAtor>{ator}</indAtor>'
           f'<ultNuNSU>{int(nsu)}</ultNuNSU></solRel></distNFeSC>')
    return (f'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<soap:Body><NfeDownloadContab xmlns="{NFE_NAMESPACE}"><pXml>{xml}</pXml>'
            '</NfeDownloadContab></soap:Body></soap:Envelope>').encode("utf-8")

class ClienteNFeAPI:
    def __init__(self, session): self.session = session
    def consultar_lote(self, cnpj, nsu=0, ator=9) -> LoteAPI:
        response = self.session.post(NFE_ENDPOINT, data=mensagem_nfe(cnpj, nsu, ator),
                                     headers={"Content-Type": "text/xml; charset=utf-8",
                                              "SOAPAction": f'"{NFE_NAMESPACE}/NfeDownloadContab"'},
                                     allow_redirects=False, timeout=(20, 120), stream=True)
        return ler_resposta_nfe(b"".join(response.iter_content(65536)))
```

Move certificate loading and TLS adapter creation without changing their error text or secret-redaction behavior. Mount adapters only for the two fixed SEF endpoints.

- [ ] **Step 4: Run protocol and existing NFC-e tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sat_nfe_api.py tests/test_sat_nfce_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/automation/sat_sef_api.py app/automation/sat_nfe_api.py app/automation/sat_nfce_api.py tests/test_sat_nfe_api.py tests/test_sat_nfce_api.py
git commit -m "feat: integrar protocolo de distribuicao nfe"
```

### Task 2: Download, cache e exportação das duas fontes

**Files:**
- Create: `app/automation/sat_dfe_download.py`
- Create: `app/automation/sat_nfe_download.py`
- Modify: `app/automation/sat_nfce_download.py`
- Test: `tests/test_sat_nfe_api.py`
- Test: `tests/test_sat_nfce_api.py`

**Interfaces:**
- Produces: `FonteDFe(nome, modelo, lote, grupo, prefixo_nota, prefixo_evento, cache)`.
- Produces: `baixar_distribuicao(api, fonte, *, cnpj, inicio, fim, pasta_saida, pasta_cache, ator=9, cancel_event=None, on_step=None, on_response=None) -> ResultadoAPI`.
- Produces wrappers `baixar_nfe_periodo(api, **kwargs)` and existing `baixar_periodo(api, **kwargs)` for NFC-e.

- [ ] **Step 1: Add failing tests for model 55 and collision-free names**

```python
def test_nfe_batch_exports_note_and_event_with_source_names(tmp_path, signed_nfe55, cancel_event):
    api = FakeAPI([batch_nfe(signed_nfe55, cancel_event)])
    result = baixar_nfe_periodo(api, cnpj=CNPJ, inicio="2026-08-01", fim="2026-08-31",
                                pasta_saida=tmp_path, pasta_cache=tmp_path / "cache")
    assert result.notas == 1 and result.eventos == 1
    assert len(list(tmp_path.glob("NFe_*.xml"))) == 1
    assert len(list(tmp_path.glob("Evento_NFe_*.xml"))) == 1
```

- [ ] **Step 2: Run the new downloader tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sat_nfe_api.py -q`

Expected: import or assertion failure because the NF-e downloader is absent.

- [ ] **Step 3: Extract the generic NSU engine and add source wrappers**

```python
NFCE = FonteDFe("NFC-e", "65", "loteDistNFCeSC", "distNFCeSC",
                "NFCe", "Evento_NFCe", "api_sef_nfce_ator_9")
NFE = FonteDFe("NF-e", "55", "loteDistNFeSC", "distNFeSC",
               "NFe", "Evento_NFe", "api_sef_nfe_ator_9")
```

Preserve atomic writes, signature verification, 50-document continuation, one-hour reprocessing wait, 12-hour completed wait, attempt reservation and per-cache lock.

- [ ] **Step 4: Run all distribution tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sat_nfe_api.py tests/test_sat_nfce_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/automation/sat_dfe_download.py app/automation/sat_nfe_download.py app/automation/sat_nfce_download.py tests/test_sat_nfe_api.py tests/test_sat_nfce_api.py
git commit -m "feat: baixar nfe e nfce com cache independente"
```

### Task 3: Job fiscal com cobertura por fonte

**Files:**
- Create: `app/automation/sat_fiscal_job.py`
- Modify: `app/automation/sat_automacao.py`
- Modify: `api/server.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Extends: `ResultadoCNPJ.cobertura: dict[str, dict]`.
- Produces: `executar_fiscal(params, cancel_event=None, *, config, certificado, on_progress=None, on_auth=None)`.

- [ ] **Step 1: Write a failing partial-coverage integration test**

```python
def test_fiscal_job_reports_partial_when_nfe_fails_and_nfce_succeeds(params, config, cert,
                                                                     raises_api_error,
                                                                     returns_one_note):
    result = executar_fiscal(params, config=config, certificado=cert,
                              nfe_download=raises_api_error,
                              nfce_download=returns_one_note)
    assert result[0].status == "parcial"
    assert result[0].cobertura["nfe"]["status"] == "erro"
    assert result[0].cobertura["nfce"]["status"] == "ok"
    assert result[0].notas == 1
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py -k fiscal_job -q`

Expected: failure because `executar_fiscal` and coverage do not exist.

- [ ] **Step 3: Implement independent source execution and aggregation**

```python
status = ("ok" if all(s["status"] == "ok" for s in cobertura.values()) else
          "parcial" if any(s.get("documentos", 0) or s["status"] in {"ok", "pendente"}
                           for s in cobertura.values()) else "erro")
```

Continue to the second source after a source-specific error. Open the certificate transport once per job. Sum notes/events only after source results are known.

- [ ] **Step 4: Update API summaries for `parcial` and run API tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py -q`

Expected: PASS, with `resultado.parcial` and a final job status that never reports partial clients as complete.

- [ ] **Step 5: Commit**

```powershell
git add app/automation/sat_fiscal_job.py app/automation/sat_automacao.py api/server.py tests/test_api.py
git commit -m "feat: consolidar consultas fiscais por empresa"
```

### Task 4: Leitura fiscal e classificação de movimento

**Files:**
- Create: `app/reports/fiscal.py`
- Modify: `app/reports/nfce.py`
- Replace tests in: `tests/test_nfce_reports.py`

**Interfaces:**
- Produces: `read_client(folder, cnpj, inicio, fim) -> (notes, items, events)`.
- Each note produces `modelo`, `movimento`, `situacao`, `valor`, `chave`, emitente and destinatário.
- Preserves compatibility imports from `app.reports.nfce`.

- [ ] **Step 1: Add failing classification tests**

```python
@pytest.mark.parametrize("model,emit,dest,tp_nf,want", [
    ("55", CNPJ, OTHER, "1", "Saída"),
    ("55", CNPJ, OTHER, "0", "Entrada"),
    ("55", OTHER, CNPJ, "1", "Entrada"),
    ("65", OTHER, CNPJ, "1", "Entrada"),
    ("65", CNPJ, "", "1", "Saída"),
])
def test_classifies_movement_relative_to_company(tmp_path, monkeypatch, model, emit, dest, tp_nf, want):
    folder = write_note(tmp_path, model=model, emit=emit, dest=dest, tp_nf=tp_nf)
    monkeypatch.setattr(fiscal, "preparar_xml", lambda root: fiscal.etree.tostring(root))
    notes, _, _ = fiscal.read_client(folder, CNPJ, "2026-08-01", "2026-08-31")
    assert notes[0]["movimento"] == want
```

Add tests proving duplicate keys are counted once, conflicting XMLs fail, unrelated documents fail and accepted cancellation moves a note out of active totals.

- [ ] **Step 2: Run report parser tests and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_nfce_reports.py -q`

Expected: failures for model 55, destination role and missing `movimento`.

- [ ] **Step 3: Implement the unified parser**

```python
def movimento(inf, cnpj):
    emit = txt(inf, "n:emit/n:CNPJ")
    dest = txt(inf, "n:dest/n:CNPJ")
    if emit == cnpj:
        return "Entrada" if txt(inf, "n:ide/n:tpNF") == "0" else "Saída"
    if dest == cnpj:
        return "Entrada"
    raise ValueError("XML não pertence à empresa")
```

Accept `NFe_*.xml`, `NFCe_*.xml`, `Evento_NFe_*.xml`, `Evento_NFCe_*.xml` and legacy `Evento_*.xml`. Deduplicate by access key and event ID.

- [ ] **Step 4: Run parser tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_nfce_reports.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/reports/fiscal.py app/reports/nfce.py tests/test_nfce_reports.py
git commit -m "feat: classificar entradas e saidas fiscais"
```

### Task 5: Excel fiscal com totais efetivos

**Files:**
- Modify: `app/reports/fiscal.py`
- Modify: `api/server.py`
- Test: `tests/test_nfce_reports.py`

**Interfaces:**
- Produces workbook tabs `Resumo`, `Entradas`, `Saídas`, `Canceladas`, `Itens`, `Eventos`.
- Produces summary keys `entradas_brutas`, `entradas_canceladas`, `entradas_efetivas`, `saidas_brutas`, `saidas_canceladas`, `saidas_efetivas`.

- [ ] **Step 1: Write a failing workbook behavior test**

```python
def test_workbook_separates_active_and_cancelled_totals(fiscal_data, tmp_path):
    target = tmp_path / "relatorio.xlsx"
    summary = fiscal.gerar_cliente(fiscal_data, "Empresa", CNPJ, "2026-08-01", "2026-08-31",
                                    {"status": "ok", "notas": 3, "cobertura": {}}, target)
    assert summary["entradas_efetivas"] == "80.00"
    assert summary["saidas_efetivas"] == "50.20"
    wb = load_workbook(target, data_only=True)
    assert wb.sheetnames == ["Resumo", "Entradas", "Saídas", "Canceladas", "Itens", "Eventos"]
    assert wb["Canceladas"]["E5"].value == 100.30
```

- [ ] **Step 2: Run and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_nfce_reports.py -k workbook -q`

Expected: old NFC-e workbook sheet names and totals fail.

- [ ] **Step 3: Generate the six-sheet workbook and fiscal filename**

Use `Relatorio_Fiscal_<inicio>_a_<fim>.xlsx`. Entradas/Saídas contain active notes; Canceladas contains cancelled notes with original movement; Itens contains items from active notes only. The Resumo shows NF-e and NFC-e coverage separately and highlights `Parcial`.

- [ ] **Step 4: Run all report tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_nfce_reports.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/reports/fiscal.py api/server.py tests/test_nfce_reports.py
git commit -m "feat: gerar excel fiscal por movimento"
```

### Task 6: Interface, período e empacotamento 0.6.0

**Files:**
- Modify: `electron/renderer/src/main.jsx`
- Modify: `electron/package.json`
- Modify: `electron/package-lock.json`
- Modify: `api/version_info.txt`
- Modify: `api/server.spec`
- Modify: `tools/smoke_renderer.py`
- Modify: `tools/smoke_electron.py`
- Modify: `README.md`
- Modify: `docs/API_NFCE.md`

**Interfaces:**
- UI displays `Parcial`, opens the report and period folder, and sends manual dates unchanged.
- Package version is `0.6.0`; artifact is `electron/dist/ZNX-SAT-Setup-0.6.0.exe`.

- [ ] **Step 1: Extend renderer smoke expectations before UI changes**

Expect the execution copy to mention NF-e and NFC-e, manual dates `01/08/2026` and `31/08/2026`, and partial status without exposing certificate data.

- [ ] **Step 2: Run renderer smoke and confirm RED**

Run: `.venv\Scripts\python.exe tools/smoke_renderer.py`

Expected: failure on new fiscal copy/status.

- [ ] **Step 3: Update UI, PyInstaller hidden imports, docs and all version fields**

Add `sat_sef_api`, `sat_nfe_api`, `sat_dfe_download`, `sat_nfe_download`, `sat_fiscal_job` and `reports.fiscal` to `api/server.spec`. Replace user-facing NFC-e-only descriptions with NF-e/NFC-e fiscal descriptions.

- [ ] **Step 4: Run full source verification**

Run: `.venv\Scripts\python.exe -m pytest -q`

Run: `.venv\Scripts\python.exe tools/smoke_renderer.py`

Expected: all PASS.

- [ ] **Step 5: Build and smoke the packaged app**

Run: `CONSTRUIR_INSTALADOR.bat`

Run: `.venv\Scripts\python.exe tools/smoke_electron.py --packaged`

Expected: installer `electron/dist/ZNX-SAT-Setup-0.6.0.exe` exists and packaged smoke passes.

- [ ] **Step 6: Commit**

```powershell
git add electron api/server.spec api/version_info.txt tools/smoke_renderer.py tools/smoke_electron.py README.md docs/API_NFCE.md
git commit -m "release: preparar instalador 0.6.0"
```
