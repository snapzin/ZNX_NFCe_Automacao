"""Continuação por NSU, cache de lotes e exportação dos XMLs do período escolhido."""
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time

from lxml import etree

from app.automation.sat_auth import check_cancel
from app.automation.sat_nfce_api import ErroAPI, MENSAGENS, nome_local
from app.automation.sat_nfce_xml import preparar_xml


@dataclass
class ResultadoAPI:
    status: str
    codigo: str
    message: str
    documentos: int = 0
    notas: int = 0
    eventos: int = 0
    ultimo_nsu: int = 0
    proxima_consulta: str = ""
    pasta: str = ""
    from_cache: bool = False


def atomic_write(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def salvar_estado(path, state):
    atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8"))


@contextmanager
def bloquear(path):
    handle = open(path, "a+b")
    try:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise ErroAPI("Já existe uma consulta em andamento para esta empresa") from None
    try:
        yield
    finally:
        handle.close()


def documentos_lote(data):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, remove_blank_text=False)
    root = etree.fromstring(data, parser)
    if root.getroottree().docinfo.doctype or nome_local(root.tag) != "loteDistNFCeSC":
        raise ErroAPI("Lote XML não reconhecido")
    documents = []
    for group in root:
        if nome_local(group.tag) != "distNFCeSC" or not re.fullmatch(r"\d{1,18}", group.get("NSU", "")):
            raise ErroAPI("Registro de lote inválido")
        if len(group) != 1 or nome_local(group[0].tag) not in {"nfeProc", "procEventoNFe"}:
            raise ErroAPI("API não retornou o XML completo esperado")
        doc = group[0]
        dates = [e.text for e in doc.iter() if nome_local(e.tag) == ("dhEmi" if nome_local(doc.tag) == "nfeProc" else "dhEvento")]
        if not dates or not dates[0]:
            raise ErroAPI("XML sem data de emissão ou de evento")
        day = datetime.fromisoformat(dates[0].replace("Z", "+00:00")).date().isoformat()
        models = [e.text for e in doc.iter() if nome_local(e.tag) == "mod"]
        if nome_local(doc.tag) == "nfeProc" and models != ["65"]:
            raise ErroAPI("Documento recebido não é uma NFC-e modelo 65")
        xml = preparar_xml(doc)
        documents.append((int(group.get("NSU")), day, nome_local(doc.tag), xml))
    return documents


def exportar_cache(cache, output, inicio, fim, cancel_event=None):
    found = {}
    for path in sorted(cache.glob("lote_*.xml")):
        check_cancel(cancel_event)
        for nsu, day, kind, xml in documentos_lote(path.read_bytes()):
            if inicio <= day <= fim:
                if nsu in found and found[nsu][2] != xml:
                    raise ErroAPI("O cache contém versões conflitantes do mesmo NSU")
                found[nsu] = (day, kind, xml)
    counts = {"nfeProc": 0, "procEventoNFe": 0}
    for nsu, (day, kind, xml) in found.items():
        check_cancel(cancel_event)
        folder = output / ("NFCe" if kind == "nfeProc" else "Eventos")
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{day}_{nsu}_{kind}.xml"
        if not target.exists() or target.read_bytes() != xml:
            atomic_write(target, xml)
        counts[kind] += 1
    return counts["nfeProc"], counts["procEventoNFe"]


def baixar_periodo(api, *, cnpj, inicio, fim, pasta_saida, ator=1, cancel_event=None, on_step=None, on_response=None):
    if not re.fullmatch(r"[A-Z0-9]{12}\d{2}", cnpj) or ator not in {1, 2, 3, 9}:
        raise ValueError("CNPJ/filtro inválido")
    if not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) for day in (inicio, fim)):
        raise ValueError("Use datas no formato AAAA-MM-DD")
    start, end = datetime.fromisoformat(inicio).date(), datetime.fromisoformat(fim).date()
    if start > end:
        raise ValueError("Período inválido")
    step = on_step or (lambda _: None)
    base = Path(pasta_saida).resolve() / cnpj
    cache = base / ("api_sef" if ator == 1 else f"api_sef_ator_{ator}")
    output = base / f"{inicio}_a_{fim}" / f"ator_{ator}"
    cache.mkdir(parents=True, exist_ok=True)
    state_path = cache / "estado.json"
    with bloquear(cache / "consulta.lock"):
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"nsu":0,"proxima":0,"completo":False}
        # Recupera o primeiro lote já obtido pelo teste autorizado, sem repetir NSU 0.
        if not state_path.exists() and (cache / "primeiro_lote.json").exists():
            first = json.loads((cache / "primeiro_lote.json").read_text(encoding="utf-8"))
            if first.get("codigo") == "118":
                cached = cache / f'lote_0_{int(first["ultimo_nsu"])}.xml'
                docs = documentos_lote(cached.read_bytes())
                if len(docs) != first["quantidade"]:
                    raise ErroAPI("Primeiro lote incompleto no cache")
                state.update(nsu=first["ultimo_nsu"], completo=len(docs)<50, codigo="118")
                if state["completo"]:
                    state["proxima"] = datetime.fromisoformat(first["data_teste"]).timestamp() + 43200
                salvar_estado(state_path,state)
        consulted = False
        code = state.get("codigo", "")
        while time.time() >= state["proxima"]:
            check_cancel(cancel_event)
            nsu = int(state["nsu"])
            # Reserva a tentativa antes da rede; falhas incertas não causam repetição imediata.
            state.update(proxima=time.time()+3600, completo=False)
            salvar_estado(state_path,state)
            step(f"Consultando lote após NSU {nsu}")
            batch = api.consultar_lote(cnpj, nsu, ator)
            consulted = True
            if on_response:
                on_response(batch.codigo)
            code = batch.codigo
            if code == "118":
                docs = documentos_lote(batch.lote_xml)
                if (len(docs) != batch.quantidade or not 0 < len(docs) <= 50
                        or batch.ultimo_nsu <= nsu
                        or [d[0] for d in docs] != sorted(set(d[0] for d in docs))
                        or any(not nsu < d[0] <= batch.ultimo_nsu for d in docs)):
                    raise ErroAPI("Lote com contagem ou sequência NSU inconsistente")
                atomic_write(cache / f"lote_{nsu}_{batch.ultimo_nsu}.xml", batch.lote_xml)
                complete = len(docs) < 50
                state.update(nsu=batch.ultimo_nsu, completo=complete, proxima=time.time()+43200 if complete else 0)
                step(f"Lote salvo: {len(docs)} documentos; último NSU {batch.ultimo_nsu}")
            elif code == "117":
                state.update(completo=True, proxima=time.time()+43200)
            else:
                state.update(completo=False, proxima=time.time()+43200 if code=="657" else time.time()+3600)
            state["codigo"] = code
            salvar_estado(state_path,state)
            if code != "118" or state["completo"]:
                break
            if cancel_event:
                cancel_event.wait(.2)
            else:
                time.sleep(.2)
        check_cancel(cancel_event)
        step("Conferindo assinaturas e exportando XMLs do período")
        notes, events = exportar_cache(cache, output, inicio, fim, cancel_event)
        complete = state.get("completo", False)
        message = ("Download concluído; XMLs do período disponíveis" if consulted else
                   "XMLs exportados do cache; aguardando intervalo para nova consulta")
        result = ResultadoAPI("ok" if complete else "pendente", code,
            message if complete else MENSAGENS.get(code, "Consulta pendente; respeitando intervalo de novas tentativas"),
            notes+events, notes, events, state["nsu"],
            datetime.fromtimestamp(state["proxima"],timezone.utc).isoformat(), str(output))
        result.from_cache = not consulted
        output.mkdir(parents=True, exist_ok=True)
        salvar_estado(output / "resultado.json", asdict(result))
        return result
