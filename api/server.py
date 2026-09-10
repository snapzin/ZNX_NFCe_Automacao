"""
FastAPI backend para NFC-e SAT Automacao.
Expõe endpoints REST para o frontend Electron.
"""
import hmac
import importlib
import logging
import os
import re
import sys
import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import uvicorn

# =============================================================================
# Logging — PRIMEIRO, antes de qualquer import que possa usar logger
# =============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suporte a bundle PyInstaller: config.py e módulos ficam ao lado do server.exe
if getattr(sys, "frozen", False):
    _app_dir = str(Path(sys.executable).parent)
    if _app_dir not in sys.path:
        sys.path.insert(0, _app_dir)
else:
    sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.config.config_defaults import apply_defaults, default_values, ensure_config_file, project_root
except ImportError as e:
    logger.warning(f"Falha ao importar config_defaults: {e}")
    apply_defaults = None
    default_values = lambda: {}
    ensure_config_file = lambda: Path(__file__).parent.parent / "config.py"

try:
    _config_path = ensure_config_file()
    sys.path.insert(0, str(_config_path.parent))
except Exception as e:
    logger.warning("Falha ao criar config.py padrao: %s", e)

try:
    import config
    if apply_defaults:
        apply_defaults(config)
except ImportError:
    logger.warning("Falha ao importar config")
    class config:
        pass
    if apply_defaults:
        apply_defaults(config, create_dirs=False)

from app.automation.sat_automacao import ExecucaoCancelada, executar_local, preparar_parametros

import importlib.util as _ilu
import time as _time

def _load_license_module():
    # Procura license.py em varios locais: ao lado de server.py (dev) e, no app
    # empacotado, ao lado do server.exe / dentro do bundle (_MEIPASS).
    _cands = [Path(__file__).parent / "license.py"]
    if getattr(sys, "frozen", False):
        _cands.append(Path(sys.executable).parent / "license.py")
        _meipass = getattr(sys, "_MEIPASS", None)
        if _meipass:
            _cands.append(Path(_meipass) / "license.py")
    _p = next((c for c in _cands if c.exists()), None)
    if _p is None:
        logger.error("license.py nao encontrado. Procurei em: %s",
                     ", ".join(str(c) for c in _cands))
        return None
    try:
        _spec = _ilu.spec_from_file_location("license", _p)
        _mod  = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        return _mod
    except Exception as e:
        logger.error("Falha ao carregar license.py (%s): %s", _p, e)
        return None

_lic = _load_license_module()
if _lic:
    license_activate   = _lic.activate
    check_license      = _lic.check_license
    validate_license_key = _lic.validate_key
    load_key           = _lic.load_key
    license_deactivate = _lic.deactivate
    logger.info("Módulo de licença carregado.")
else:
    logger.error("LICENÇA: módulo não encontrado — execução BLOQUEADA.")
    def license_activate(key): return False, "Módulo de licença não encontrado."
    def check_license(key=None): return False, "Módulo de licença não encontrado."
    def validate_license_key(key): return False, "Módulo de licença não encontrado."
    def load_key(): return None
    def license_deactivate(): pass

# =============================================================================
# Job management
# =============================================================================
@dataclass
class Job:
    id: str
    status: str  # "running", "ok", "cancelado", "erro"
    logs: deque = None
    thread: Optional[threading.Thread] = None
    cancel_event: Optional[threading.Event] = None
    resultado: Optional[dict] = None
    progress: dict = None
    created_at: float = 0.0

    def __post_init__(self):
        if self.progress is None:
            self.progress = {"total": 0, "processed": 0, "clients": [], "stage": "Preparando"}
        if self.logs is None:
            self.logs = deque(maxlen=2000)
        if self.cancel_event is None:
            self.cancel_event = threading.Event()
        if self.created_at == 0.0:
            self.created_at = _time.time()

JOBS = {}
_MAX_JOBS = 50
_JOB_TTL_S = 7200  # 2 horas


def _prune_jobs() -> None:
    """Remove jobs finalizados mais antigos quando o limite é atingido."""
    if len(JOBS) <= _MAX_JOBS:
        return
    cutoff = _time.time() - _JOB_TTL_S
    to_remove = [
        jid for jid, j in JOBS.items()
        if j.status != "running" and j.created_at < cutoff
    ]
    for jid in to_remove:
        del JOBS[jid]
    # Se ainda acima do limite, remove os mais antigos independente do TTL
    if len(JOBS) > _MAX_JOBS:
        finished = sorted(
            [(jid, j) for jid, j in JOBS.items() if j.status != "running"],
            key=lambda x: x[1].created_at,
        )
        for jid, _ in finished[:len(JOBS) - _MAX_JOBS]:
            del JOBS[jid]

class JobLogHandler(logging.Handler):
    """Handler que adiciona logs a um Job específico."""
    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        if (self.job_id in JOBS and record.name == "sat"
                and JOBS[self.job_id].thread
                and record.thread == JOBS[self.job_id].thread.ident):
            msg = self.format(record)
            JOBS[self.job_id].logs.append({
                "timestamp": record.created,
                "level": record.levelname,
                "message": msg,
            })

# =============================================================================
# FastAPI app
# =============================================================================
app = FastAPI(title="NFC-e SAT Automacao API")


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # O erro padrão pode incluir o corpo recebido, inclusive campos secretos.
    return JSONResponse(status_code=422, content={"detail": "Formato de requisição inválido"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "app://"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "x-api-token", "x-license-key"],
)

# Token gerado pelo Electron e passado via env var NFSE_API_TOKEN.
# Se não definido (modo dev sem Electron), a auth é desativada.
_API_TOKEN = os.environ.get("NFSE_API_TOKEN", "")

def _is_license_exempt_path(method: str, path: str) -> bool:
    if path in ("/health", "/health/auth"):
        return True
    if method == "GET" and re.fullmatch(r"/executar/[^/]+/status", path):
        return True
    if method == "POST" and re.fullmatch(r"/executar/[^/]+/cancelar", path):
        return True
    return False

@app.middleware("http")
async def _require_token(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    if _API_TOKEN:
        token = request.headers.get("x-api-token", "")
        if not token or not hmac.compare_digest(token.encode(), _API_TOKEN.encode()):
            return JSONResponse(status_code=401, content={"error": "Não autorizado"})

    if request.method != "OPTIONS" and not _is_license_exempt_path(request.method, request.url.path):
        license_key = request.headers.get("x-license-key", "")
        licensed, message = validate_license_key(license_key)
        if not licensed:
            return JSONResponse(
                status_code=402,
                content={"licensed": False, "detail": message, "message": message},
            )
    return await call_next(request)

# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health")
async def health():
    """Health check — Electron aguarda isso para saber que o backend está pronto."""
    return {"ok": True}


@app.get("/health/auth")
async def authenticated_health():
    """Confirma que Electron e backend compartilham o mesmo token de sessao."""
    return {"ok": True, "authenticated": True}

@app.get("/config")
async def get_config():
    """Retorna seções + valores atuais de config.py."""
    sections = [
        {"title": "Caminhos locais", "fields": [
            ("XLSX_PATH", "Planilha de clientes", "path"),
            ("PASTA_SAIDA", "Pasta de saída", "dir"),
        ]},
        {"title": "SAT / Playwright", "fields": [
            ("CHROME_CHANNEL", "Canal do navegador (chrome)", "text"),
            ("CHROME_EXECUTABLE_PATH", "Executável Chrome (opcional)", "path"),
            ("PLAYWRIGHT_HEADLESS", "Executar sem janela (True/False)", "text"),
            ("PLAYWRIGHT_TIMEOUT_MS", "Timeout por ação (ms, máximo 15000)", "int"),
            ("PLAYWRIGHT_LOGIN_TIMEOUT_S", "Espera da resposta de login (s)", "int"),
        ]},
        {"title": "Seletores SAT — alterar após observar o portal", "fields": [
            (key, key.removeprefix("SAT_SELECTOR_").replace("_", " ").capitalize(), "text")
            for key in default_values() if key.startswith("SAT_SELECTOR_")
        ]},
    ]

    values = {}
    for section in sections:
        for key, label, tipo in section["fields"]:
            val = getattr(config, key, "")
            values[key] = "••••••••" if tipo == "secret" else str(val)

    return {"sections": sections, "values": values}

@app.post("/config")
async def set_config(body: dict):
    """Salva valores em config.py (com backup .bak)."""
    config_path = ensure_config_file()
    if not config_path.exists():
        try:
            config_path = ensure_config_file(config_path.parent)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Falha ao criar config.py: {e}")
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="config.py não encontrado")

    try:
        original = config_path.read_text(encoding="utf-8")
        novo = original
        defaults = default_values()

        for chave, valor in body.items():
            if chave == "SAT_LOGIN_URL":
                continue
            if not hasattr(config, chave):
                continue
            if str(valor).strip() == "" and defaults.get(chave) not in ("", None):
                valor = defaults[chave]
            atual = getattr(config, chave)
            if isinstance(atual, bool):
                literal = "True" if str(valor).lower() in ("true", "1", "sim") else "False"
            elif isinstance(atual, int):
                literal = str(int(valor))
            else:
                literal = repr(str(valor))

            pattern = re.compile(
                rf"^(?P<prefix>{re.escape(chave)}\s*=\s*)(?P<value>.+?)(?P<suffix>\s*(?:#.*)?)$",
                re.MULTILINE,
            )
            novo, count = pattern.subn(
                lambda m: f"{m.group('prefix')}{literal}{m.group('suffix')}",
                novo,
                count=1,
            )
            if count == 0:
                novo = f"{novo.rstrip()}\n{chave} = {literal}\n"

        backup = config_path.with_name(f"config.py.bak.{int(_time.time())}")
        backup.write_text(original, encoding="utf-8")

        # Remove backups mais antigos (mantém últimos 5)
        old_backups = sorted(config_path.parent.glob("config.py.bak.*"),
                             key=lambda p: p.stat().st_mtime)
        for old in old_backups[:-5]:
            try:
                old.unlink()
            except Exception:
                pass
        compile(novo, str(config_path), "exec")
        temporary = config_path.with_suffix(".tmp")
        temporary.write_text(novo, encoding="utf-8")
        temporary.replace(config_path)

        importlib.reload(config)
        if apply_defaults:
            apply_defaults(config)

        return {"ok": True, "backupPath": str(backup)}
    except Exception as e:
        logger.error("Falha ao salvar configuração")
        raise HTTPException(status_code=500, detail="Falha ao salvar configuração")

@app.get("/paths/status")
async def paths_status():
    return {"needsSetup": False, "suggestions": {"PASTA_SAIDA": config.PASTA_SAIDA},
            "saida": {"path": config.PASTA_SAIDA, "ok": Path(config.PASTA_SAIDA).is_dir()}}


@app.get("/admin/maquinas")
async def admin_maquinas():
    """Status do servidor de licencas + lista de licencas/maquinas ativas.

    - 'online': o servidor respondeu (conectividade).
    - 'configurado': LICENSE_ADMIN_TOKEN setado nesta maquina (mostra os dados).
    - 'itens': licencas com suas maquinas; 'maquinas': lista achatada (1 por
      maquina ativa) para exibir direto no Modo Dev.
    """
    url = (
        os.environ.get("NFSE_LICENSE_ADMIN_URL", "").strip()
        or str(getattr(config, "LICENSE_ADMIN_URL", "") or "").strip()
    )
    token = str(getattr(config, "LICENSE_ADMIN_TOKEN", "") or "").strip()
    base = url.split("/api/")[0] if "/api/" in url else url
    out = {"serverUrl": base, "online": False, "configurado": bool(token),
           "ok": False, "total": 0, "itens": [], "maquinas": [], "erro": ""}
    if not url:
        out["erro"] = "LICENSE_ADMIN_URL nao configurada."
        return out
    try:
        import requests
        if token:
            r = requests.post(
                url, json={"op": "list"},
                headers={"x-admin-token": token, "Content-Type": "application/json"},
                timeout=15,
            )
            out["online"] = True
            data = r.json()
            out["ok"] = bool(data.get("ok"))
            out["total"] = data.get("total", 0)
            out["itens"] = data.get("items", [])
            if not out["ok"]:
                out["erro"] = str(data.get("message", ""))
            # Achata as maquinas (1 entrada por maquina com chave ativa)
            for it in out["itens"]:
                for mid, m in (it.get("machines") or {}).items():
                    machine_status = (m or {}).get("status") or it.get("status", "active")
                    if it.get("status") == "blocked":
                        machine_status = "blocked"
                    out["maquinas"].append({
                        "cliente": it.get("clientName") or it.get("keyFmt"),
                        "machineId": mid,
                        "status": machine_status,
                        "expiresAt": it.get("expiresAt"),
                        "lastSeen": (m or {}).get("lastSeen"),
                        "firstSeen": (m or {}).get("firstSeen"),
                    })
            out["maquinas"].sort(key=lambda x: x.get("lastSeen") or "", reverse=True)
        else:
            # Sem token: so verifica se o servidor esta no ar.
            requests.get(base, timeout=10)
            out["online"] = True
        return out
    except Exception as e:
        out["online"] = False
        out["erro"] = str(e)
        return out


def _resolver_xlsx_path() -> Path:
    """Resolve XLSX_PATH relativo ao diretorio do config.py."""
    raw = str(getattr(config, "XLSX_PATH", "clientes.xlsx")).strip() or "clientes.xlsx"
    p = Path(raw)
    if p.is_absolute():
        return p
    config_dir = Path(getattr(config, "__file__", __file__)).parent
    return config_dir / raw


def _normalizar_clientes(clientes) -> list[dict]:
    out = []
    for c in clientes or []:
        if not isinstance(c, dict):
            continue
        doc = re.sub(r"\D", "", str(c.get("documento", c.get("cnpj", c.get("cpf", "")))).strip())[:32]
        nome = str(c.get("nome", "")).strip()[:200]
        # 'ativo' controla quais clientes entram na execucao (checkbox na tela).
        # Ausente = True (retrocompatibilidade: tudo ativo por padrao).
        ativo = c.get("ativo", True)
        if isinstance(ativo, str):
            ativo = ativo.strip().lower() not in ("nao", "não", "false", "0", "n", "")
        tipo_login = str(c.get("tipo_login", "usuario_senha") or "usuario_senha").strip().lower()
        if tipo_login not in ("usuario_senha",):
            tipo_login = "usuario_senha"
        usuario_sat = str(c.get("usuario_sat", c.get("usuario", c.get("usuario_nfse", ""))) or "").strip()
        senha_sat = str(c.get("senha_sat", c.get("senha", c.get("senha_nfse", ""))) or "")
        if doc or nome:
            out.append({
                "documento": doc, "nome": nome, "ativo": bool(ativo),
                "tipo_login": tipo_login, "usuario_sat": usuario_sat,
                "senha_sat": senha_sat,
            })
    return out


def _ler_clientes_local() -> dict:
    from openpyxl import load_workbook

    xlsx_path = _resolver_xlsx_path()
    if not xlsx_path.exists():
        return {"clientes": [], "path": str(xlsx_path), "source": "local"}

    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=1, values_only=True))
    wb.close()

    if not rows:
        return {"clientes": [], "path": str(xlsx_path), "source": "local"}

    header = [str(c or "").strip().lower() for c in rows[0]]
    idx_doc = next((i for i, h in enumerate(header)
                    if "cnpj" in h or "cpf" in h or "doc" in h), 0)
    idx_nome = next((i for i, h in enumerate(header)
                     if "nome" in h or "razao" in h or "cliente" in h), 1)
    idx_ativo = next((i for i, h in enumerate(header)
                      if "ativo" in h or "selec" in h), None)
    idx_tipo = next((i for i, h in enumerate(header) if "tipo_login" in h or "tipo login" in h), None)
    idx_usuario = next((i for i, h in enumerate(header) if h in ("usuario_sat", "usuario sat", "usuario", "usuário", "usuario_nfse", "usuario nfse")), None)
    idx_senha = next((i for i, h in enumerate(header) if h in ("senha_sat", "senha sat", "senha", "senha_nfse", "senha nfse")), None)

    clientes = []
    for row in rows[1:]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        doc = str(row[idx_doc] or "").strip() if idx_doc < len(row) else ""
        nome = str(row[idx_nome] or "").strip() if idx_nome < len(row) else ""
        ativo = True
        if idx_ativo is not None and idx_ativo < len(row):
            ativo = str(row[idx_ativo] or "").strip().lower() not in ("nao", "não", "false", "0", "n", "")
        if doc or nome:
            clientes.append({
                "documento": doc, "nome": nome, "ativo": ativo,
                "tipo_login": str(row[idx_tipo] or "usuario_senha") if idx_tipo is not None and idx_tipo < len(row) else "usuario_senha",
                "usuario_sat": str(row[idx_usuario] or "") if idx_usuario is not None and idx_usuario < len(row) else "",
                "senha_sat": str(row[idx_senha] or "") if idx_senha is not None and idx_senha < len(row) else "",
            })

    return {"clientes": _normalizar_clientes(clientes), "path": str(xlsx_path), "source": "local"}


def _salvar_clientes_local(clientes: list[dict]) -> dict:
    from openpyxl import Workbook

    xlsx_path = _resolver_xlsx_path()
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    ws.append(["CNPJ", "NOME", "ATIVO", "TIPO_LOGIN", "USUARIO_SAT", "SENHA_SAT"])
    for c in clientes:
        ativo = "Sim" if c.get("ativo", True) else "Nao"
        ws.append([
            c.get("documento", ""), c.get("nome", ""), ativo,
            c.get("tipo_login", "usuario_senha"), c.get("usuario_sat", ""),
            c.get("senha_sat", ""),
        ])
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    temporary = xlsx_path.with_name(xlsx_path.stem + ".tmp.xlsx")
    wb.save(temporary)
    temporary.replace(xlsx_path)
    wb.close()

    return {"ok": True, "salvos": len(clientes), "path": str(xlsx_path), "source": "local"}


# ── Overlay LOCAL da selecao (ativo/inativo) por CNPJ ────────────────────────
# O servidor de licencas so guarda documento+nome (descarta 'ativo'). Para a
# selecao por checkbox funcionar mesmo com armazenamento remoto, guardamos o
# ativo/inativo num arquivo local por CNPJ e aplicamos ao ler/executar.
def _overlay_path() -> Path:
    return _resolver_xlsx_path().with_name("clientes_selecao.json")


def _ler_overlay() -> dict:
    import json
    p = _overlay_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {re.sub(r"\D", "", str(k)): bool(v) for k, v in (data or {}).items()}
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao ler selecao de clientes: %s", e)
        return {}


def _salvar_overlay(clientes: list[dict]) -> None:
    import json
    sel = {}
    for c in clientes or []:
        doc = re.sub(r"\D", "", str(c.get("documento", "")))
        if doc:
            sel[doc] = bool(c.get("ativo", True))
    try:
        _overlay_path().write_text(json.dumps(sel), encoding="utf-8")
    except OSError as e:
        logger.warning("Falha ao salvar selecao de clientes: %s", e)


def _aplicar_overlay(clientes: list[dict]) -> list[dict]:
    """Sobrescreve 'ativo' de cada cliente com a selecao local salva (por CNPJ).
    Clientes sem entrada no overlay mantem o proprio 'ativo' (default True)."""
    ov = _ler_overlay()
    if not ov:
        return clientes
    for c in clientes:
        doc = re.sub(r"\D", "", str(c.get("documento", "")))
        if doc in ov:
            c["ativo"] = ov[doc]
    return clientes


# Credenciais do portal sao locais por maquina. Elas nao sao enviadas ao
# servidor de licencas nem incluidas no repositorio.
def _credenciais_path() -> Path:
    return _resolver_xlsx_path().with_name("clientes_credenciais.json")


def _ler_credenciais_locais() -> dict:
    import json
    p = _credenciais_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001
        logger.warning("Falha ao ler credenciais locais de clientes: %s", e)
        return {}


def _salvar_credenciais_locais(clientes: list[dict]) -> None:
    import json
    dados = {}
    for c in clientes or []:
        doc = re.sub(r"\D", "", str(c.get("documento", "")))
        if not doc:
            continue
        tipo = str(c.get("tipo_login", "usuario_senha"))
        dados[doc] = {
            "tipo_login": tipo if tipo in ("usuario_senha",) else "usuario_senha",
            "usuario_sat": str(c.get("usuario_sat", "") or ""),
            "senha_sat": str(c.get("senha_sat", "") or ""),
        }
    try:
        _credenciais_path().write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        raise RuntimeError("Falha ao gravar credenciais locais") from None


def _aplicar_credenciais_locais(clientes: list[dict]) -> list[dict]:
    dados = _ler_credenciais_locais()
    for c in clientes:
        doc = re.sub(r"\D", "", str(c.get("documento", "")))
        cred = dados.get(doc)
        if isinstance(cred, dict):
            c["tipo_login"] = cred.get("tipo_login", "usuario_senha")
            c["usuario_sat"] = cred.get("usuario_sat", "")
            c["senha_sat"] = cred.get("senha_sat", "")
    return clientes


def _aplicar_dados_locais(clientes: list[dict]) -> list[dict]:
    return _aplicar_credenciais_locais(_aplicar_overlay(clientes))


def _clientes_remotos_ativos() -> bool:
    value = os.environ.get("SAT_CLIENTES_REMOTE", "0").strip().lower()
    return value not in {"0", "false", "no", "off"} and bool(os.environ.get("SAT_CLIENTES_URL", "").strip())


def _license_server_url() -> str:
    url = (
        os.environ.get("NFSE_LICENSE_SERVER_URL", "").strip()
        or str(getattr(_lic, "LICENSE_SERVER_URL", "") or "").strip()
        or "https://license-server-sigma-topaz.vercel.app"
    )
    return url.rstrip("/")


def _clientes_remote_url() -> str:
    return (
        os.environ.get("SAT_CLIENTES_URL", "").strip()
        or f"{_license_server_url()}/api/clientes"
    )


def _clientes_machine_id() -> str:
    if _lic and hasattr(_lic, "get_machine_id"):
        return _lic.get_machine_id()
    raise RuntimeError("Identificador desta maquina indisponivel.")


def _clientes_client_secret() -> str:
    return (
        os.environ.get("NFSE_CLIENT_SECRET", "").strip()
        or str(getattr(_lic, "_CLIENT_SECRET", "") or "").strip()
    )


def _clientes_remote_call(op: str, license_key: str, clientes: list[dict] | None = None) -> dict:
    if not license_key:
        raise RuntimeError("Licenca nao informada.")

    payload = {
        "op": op,
        "key": license_key,
        "machine_id": _clientes_machine_id(),
    }
    if clientes is not None:
        payload["clientes"] = clientes

    headers = {"Content-Type": "application/json"}
    client_secret = _clientes_client_secret()
    if client_secret:
        headers["x-client-secret"] = client_secret

    resp = requests.post(
        _clientes_remote_url(),
        json=payload,
        headers=headers,
        timeout=10,
    )
    try:
        data = resp.json()
    except Exception:
        data = {}
    if not resp.ok or data.get("ok") is False:
        msg = data.get("message") or data.get("detail") or resp.text or f"HTTP {resp.status_code}"
        raise RuntimeError(str(msg))
    return data


def _clientes_atuais(license_key: str) -> list[dict]:
    """Lista de clientes da aba Clientes para uso na execucao.

    Mesma fonte da tela de Clientes: servidor por maquina (quando remoto
    ativo), com fallback para o XLSX local. Retorna [] se nada cadastrado —
    nesse caso a automacao mantem o comportamento antigo (todos os certs).
    """
    if _clientes_remotos_ativos():
        try:
            data = _clientes_remote_call("get", license_key)
            clientes = _normalizar_clientes(data.get("clientes") or [])
            if clientes:
                return _aplicar_dados_locais(clientes)
        except Exception as remote_err:
            logger.warning("Falha ao obter clientes do servidor p/ execucao: %s", remote_err)
    try:
        return _aplicar_dados_locais(_ler_clientes_local().get("clientes") or [])
    except Exception as local_err:
        logger.warning("Falha ao ler clientes locais p/ execucao: %s", local_err)
        return []


@app.get("/clientes")
async def listar_clientes(request: Request):
    """Le clientes por maquina no servidor; usa XLSX local como fallback/migracao."""
    try:
        if _clientes_remotos_ativos():
            try:
                data = _clientes_remote_call("get", request.headers.get("x-license-key", ""))
                clientes = _aplicar_dados_locais(_normalizar_clientes(data.get("clientes") or []))
                if clientes or data.get("updatedAt"):
                    return {
                        "clientes": clientes,
                        "path": data.get("path") or "",
                        "location": data.get("location") or "Servidor de licencas",
                        "source": "server",
                        "machineId": data.get("machine_id") or _clientes_machine_id(),
                        "updatedAt": data.get("updatedAt"),
                    }

                local = _ler_clientes_local()
                local["clientes"] = _aplicar_dados_locais(local.get("clientes") or [])
                if local.get("clientes"):
                    local["location"] = (
                        f"Arquivo local: {local.get('path')} "
                        "(clique em Salvar para enviar ao servidor desta maquina)"
                    )
                    local["sync_hint"] = "Clique em Salvar para enviar estes clientes ao servidor desta maquina."
                    return local

                return {
                    "clientes": [],
                    "path": data.get("path") or "",
                    "location": data.get("location") or "Servidor de licencas",
                    "source": "server",
                    "machineId": data.get("machine_id") or _clientes_machine_id(),
                    "updatedAt": data.get("updatedAt"),
                }
            except Exception as remote_err:
                logger.warning("Falha ao carregar clientes do servidor: %s", remote_err)

        local = _ler_clientes_local()
        local["clientes"] = _aplicar_dados_locais(local.get("clientes") or [])
        if not local.get("location"):
            local["location"] = f"Arquivo local: {local.get('path')}"
        return local
    except Exception as e:
        logger.exception("Falha ao listar clientes")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clientes")
async def salvar_clientes(request: Request, payload: dict):
    """Grava clientes por maquina no servidor; local por padrão; remoto SAT somente quando configurado."""
    try:
        clientes = _normalizar_clientes(payload.get("clientes") or [])
        docs = set()
        for cliente in clientes:
            doc = cliente["documento"]
            if len(doc) not in (11, 14) or not cliente["nome"]:
                raise HTTPException(400, "Informe CPF/CNPJ e nome de cada cliente")
            if doc in docs:
                raise HTTPException(400, "CPF/CNPJ duplicado")
            docs.add(doc)
            if not cliente["usuario_sat"] or not cliente["senha_sat"]:
                raise HTTPException(400, "Informe usuário e senha SAT de cada cliente")
        # Guarda a selecao (ativo/inativo) localmente — o servidor descarta esse
        # campo, entao o overlay local e a fonte da verdade da selecao.
        _salvar_overlay(clientes)
        _salvar_credenciais_locais(clientes)

        if _clientes_remotos_ativos():
            try:
                data = _clientes_remote_call(
                    "save",
                    request.headers.get("x-license-key", ""),
                    [
                        {k: c[k] for k in ("documento", "nome", "ativo")}
                        for c in clientes
                    ],
                )
                return {
                    "ok": True,
                    "salvos": int(data.get("salvos", len(clientes))),
                    "path": data.get("path") or "",
                    "location": data.get("location") or "Servidor de licencas",
                    "source": "server",
                    "machineId": data.get("machine_id") or _clientes_machine_id(),
                    "updatedAt": data.get("updatedAt"),
                }
            except Exception as remote_err:
                logger.exception("Falha ao salvar clientes no servidor")
                raise HTTPException(
                    status_code=502,
                    detail=f"Falha ao salvar clientes no servidor: {remote_err}",
                )

        return _salvar_clientes_local(clientes)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error("Falha ao salvar clientes")
        raise HTTPException(status_code=500, detail="Falha ao salvar clientes")


def _parse_xlsx_clientes(path: Path) -> list[dict]:
    """Le um XLSX arbitrario (colunas CNPJ/CPF + Nome; ATIVO opcional) e devolve
    a lista normalizada de clientes. Detecta as colunas pelo cabecalho."""
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=1, values_only=True))
    wb.close()
    if not rows:
        return []
    header = [str(c or "").strip().lower() for c in rows[0]]
    idx_doc = next((i for i, h in enumerate(header)
                    if "cnpj" in h or "cpf" in h or "doc" in h), 0)
    idx_nome = next((i for i, h in enumerate(header)
                     if "nome" in h or "razao" in h or "cliente" in h), 1)
    idx_ativo = next((i for i, h in enumerate(header)
                      if "ativo" in h or "selec" in h), None)
    idx_tipo = next((i for i, h in enumerate(header) if "tipo_login" in h or "tipo login" in h), None)
    idx_usuario = next((i for i, h in enumerate(header) if h in ("usuario_sat", "usuario sat", "usuario", "usuário", "usuario_nfse", "usuario nfse")), None)
    idx_senha = next((i for i, h in enumerate(header) if h in ("senha_sat", "senha sat", "senha", "senha_nfse", "senha nfse")), None)
    clientes = []
    for row in rows[1:]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        doc = str(row[idx_doc] or "").strip() if idx_doc < len(row) else ""
        nome = str(row[idx_nome] or "").strip() if idx_nome < len(row) else ""
        ativo = True
        if idx_ativo is not None and idx_ativo < len(row):
            ativo = str(row[idx_ativo] or "").strip().lower() not in ("nao", "não", "false", "0", "n", "")
        if doc or nome:
            clientes.append({
                "documento": doc, "nome": nome, "ativo": ativo,
                "tipo_login": str(row[idx_tipo] or "usuario_senha") if idx_tipo is not None and idx_tipo < len(row) else "usuario_senha",
                "usuario_sat": str(row[idx_usuario] or "") if idx_usuario is not None and idx_usuario < len(row) else "",
                "senha_sat": str(row[idx_senha] or "") if idx_senha is not None and idx_senha < len(row) else "",
            })
    return _normalizar_clientes(clientes)


@app.post("/clientes/importar")
async def importar_clientes(payload: dict):
    """Le um XLSX (CNPJ/CPF + Nome) do caminho informado e DEVOLVE os clientes
    (nao salva — o frontend mescla com a lista e o usuario clica em Salvar)."""
    caminho = str(payload.get("path") or "").strip()
    if not caminho:
        raise HTTPException(status_code=400, detail="Caminho do arquivo nao informado.")
    p = Path(caminho)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo nao encontrado: {caminho}")
    try:
        clientes = _parse_xlsx_clientes(p)
    except Exception as e:
        logger.error("Falha ao importar planilha")
        raise HTTPException(status_code=400, detail="Não foi possível ler a planilha XLSX/XLSM")
    return {"ok": True, "clientes": clientes, "total": len(clientes)}


@app.get("/license/status")
async def license_status():
    """Endpoint legado: licença agora é validada no Electron contra a Vercel."""
    return {
        "licensed": False,
        "message": "Licenca local desativada. O aplicativo valida diretamente no servidor da Vercel.",
        "key_hint": None,
        "remoteOnly": True,
    }


@app.post("/license/activate")
async def license_activate_endpoint(body: dict):
    """Endpoint legado: ativação local foi desativada."""
    raise HTTPException(
        status_code=410,
        detail="Ativacao local desativada. Use a validacao direta do aplicativo com a Vercel.",
    )


@app.post("/license/deactivate")
async def license_deactivate_endpoint():
    """Remove a chave de licença local."""
    license_deactivate()
    return {"ok": True}


def _filtrar_clientes_por_login(todos_clientes: list[dict], tipo_login: str) -> list[dict]:
    if tipo_login != "usuario_senha":
        raise HTTPException(400, "Este fluxo SAT usa somente usuário e senha")
    selected = [c for c in todos_clientes if c.get("ativo", True)]
    if not selected:
        raise HTTPException(400, "Nenhum cliente ativo selecionado na aba Clientes")
    return selected


@app.post("/executar")
async def start_execution(request: Request, body: dict):
    """Cria um job de LOGIN SAT. Consulta e download aguardam mapeamento."""
    if any(j.status == "running" for j in JOBS.values()):
        raise HTTPException(409, "Já existe uma execução em andamento")
    if body.get("modo", "login") != "login":
        raise HTTPException(400, "Consulta e download NFC-e ainda não mapeados")
    _prune_jobs()
    clients = _filtrar_clientes_por_login(
        _clientes_atuais(request.headers.get("x-license-key", "")),
        body.get("tipoLogin", "usuario_senha"),
    )
    try:
        params = preparar_parametros(body.get("dataInicio"), body.get("dataFim"),
                                    body.get("cnpjs"), clientes=clients)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    from types import SimpleNamespace
    settings = SimpleNamespace(**{key: getattr(config, key) for key in default_values()})
    job_id = str(uuid.uuid4())[:8]
    job = Job(id=job_id, status="running")
    JOBS[job_id] = job
    handler = JobLogHandler(job_id)

    def progress(index, total, doc, name, stage, results):
        done = [asdict(r) for r in results]
        job.progress = {"index": index, "total": total, "processed": len(done),
                        "current": {"cnpj": doc, "nome": name},
                        "stage": stage, "clients": done}

    def summary(results):
        return {"modo": "login", "resultados": results, "total": len(results),
                "ok": sum(r["status"] == "ok" for r in results),
                "erro": sum(r["status"] == "erro" for r in results),
                "pendente": sum(r["status"] == "pendente" for r in results)}

    def run_job():
        sat_logger = logging.getLogger("sat")
        sat_logger.addHandler(handler)
        try:
            results = executar_local(params, cancel_event=job.cancel_event,
                                      config=settings, on_progress=progress)
            job.resultado = summary([asdict(r) for r in results])
            job.status = ("cancelado" if job.cancel_event.is_set() else
                          "erro" if job.resultado["erro"] else
                          "pendente" if job.resultado["pendente"] else "ok")
        except ExecucaoCancelada:
            job.resultado = summary(job.progress["clients"])
            job.status = "cancelado"
        except Exception:
            sat_logger.error("Falha na execução SAT; credenciais e detalhes do navegador omitidos")
            job.resultado = summary(job.progress["clients"])
            job.resultado["message"] = "Falha na execução SAT"
            job.status = "erro"
        finally:
            sat_logger.removeHandler(handler)

    job.thread = threading.Thread(target=run_job, daemon=True)
    job.thread.start()
    return {"jobId": job_id}

@app.get("/executar/{job_id}/status")
async def get_job_status(job_id: str):
    """Retorna status de um job."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = JOBS[job_id]
    logs = list(job.logs)

    resultado = {
        "jobId": job_id,
        "status": job.status,
        "logs": logs,
        "progress": job.progress,
    }

    if job.resultado:
        resultado["resultado"] = job.resultado

    return resultado

@app.post("/executar/{job_id}/cancelar")
async def cancel_job(job_id: str):
    """Cancela um job em execução."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = JOBS[job_id]
    if job.status == "running":
        job.cancel_event.set()
        return {"ok": True, "message": "Cancelamento solicitado"}
    return {"ok": False, "message": "Job não está em execução"}

# =============================================================================
# Entry point
# =============================================================================
if __name__ == "__main__":
    try:
        api_port = int(os.environ.get("NFSE_API_PORT", "17432"))
    except ValueError:
        api_port = 17432
    if not 1 <= api_port <= 65535:
        api_port = 17432
    uvicorn.run(app, host="127.0.0.1", port=api_port, log_level="info")
