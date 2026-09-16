# GitHub Auto Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar automaticamente um GitHub Release testado com o instalador Windows sempre que uma tag `vX.Y.Z` for enviada.

**Architecture:** Um validador local confirma que a tag e a versão do Electron coincidem. Um workflow Windows executa testes, PyInstaller, electron-builder e smoke empacotado antes de criar o release com instalador, blockmap e SHA-256.

**Tech Stack:** GitHub Actions, PowerShell, Python, pytest, Node.js 20, electron-builder, GitHub CLI.

**Spec:** Desenho aprovado em conversa em 16/09/2026: release por tag, bloqueio em falha e uso exclusivo de `GITHUB_TOKEN`.

## Global Constraints

- Publicar somente tags `vX.Y.Z` cuja versão seja idêntica a `electron/package.json`.
- Executar no Windows e reutilizar os comandos de build do projeto.
- Não publicar se testes, build ou smoke empacotado falharem.
- Anexar `.exe`, `.exe.blockmap` e `SHA256SUMS.txt` ao GitHub Release.
- Usar apenas `GITHUB_TOKEN` com permissão `contents: write`.

---

### Task 1: Validador de versão do release

**Files:**
- Create: `tools/validate_release.py`
- Create: `tests/test_release.py`

**Interfaces:**
- Produces: `validate(tag: str, package_path: Path) -> str`, returning the normalized version or raising `ValueError`.
- CLI exits 0 and prints the version for a match; exits nonzero without secrets for invalid input.

- [ ] **Step 1: Write failing tests**

```python
def test_release_tag_must_match_package_version(tmp_path):
    package = tmp_path / "package.json"
    package.write_text('{"version":"0.6.0"}', encoding="utf-8")
    assert validate("v0.6.0", package) == "0.6.0"
    with pytest.raises(ValueError, match="não corresponde"):
        validate("v0.6.1", package)

@pytest.mark.parametrize("tag", ["0.6.0", "v1", "latest", "v1.2.3-beta"])
def test_release_rejects_non_final_semver(tag, tmp_path):
    package = tmp_path / "package.json"
    package.write_text('{"version":"0.6.0"}', encoding="utf-8")
    with pytest.raises(ValueError, match="vX.Y.Z"):
        validate(tag, package)
```

- [ ] **Step 2: Run and confirm RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_release.py -q`

Expected: import failure because `tools.validate_release` does not exist.

- [ ] **Step 3: Implement exact SemVer validation**

```python
TAG = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

def validate(tag, package_path):
    if not TAG.fullmatch(tag):
        raise ValueError("Tag deve usar o formato vX.Y.Z")
    version = json.loads(package_path.read_text(encoding="utf-8"))["version"]
    if tag[1:] != version:
        raise ValueError("Tag não corresponde à versão do aplicativo")
    return version
```

- [ ] **Step 4: Run validator tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_release.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add tools/validate_release.py tests/test_release.py
git commit -m "build: validar versao de release"
```

### Task 2: Workflow Windows que cria o GitHub Release

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes tag from `github.ref_name` and `electron/package.json`.
- Produces GitHub Release with generated notes and three assets.

- [ ] **Step 1: Create the tag-triggered workflow**

```yaml
name: Release Windows
on:
  push:
    tags: ["v[0-9]+.[0-9]+.[0-9]+"]
permissions:
  contents: write
jobs:
  release:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: electron/package-lock.json
```

Add sequential PowerShell steps for version validation, Python dependencies/tests, PyInstaller, `npm ci`, renderer/electron build, packaged smoke, SHA-256 creation, artifact upload and `gh release create --generate-notes`.

- [ ] **Step 2: Document the exact release command**

```powershell
git tag v0.6.0
git push origin v0.6.0
```

Document that the release is created only after all validations pass.

- [ ] **Step 3: Validate locally without publishing**

Run: `.venv\Scripts\python.exe tools/validate_release.py v0.6.0 electron/package.json`

Run: `.venv\Scripts\python.exe -m pytest tests/test_release.py -q`

Expected: version `0.6.0` and PASS.

- [ ] **Step 4: Commit**

```powershell
git add .github/workflows/release.yml README.md
git commit -m "ci: publicar instalador em releases"
```
