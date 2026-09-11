"""Estrutura visível: Empresa/Período/{Relatorio,XMLs}."""
import calendar
from datetime import date
from pathlib import Path
import re

INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def nome_pasta(nome):
    clean = INVALID.sub("", str(nome or "")).strip(". ")[:100]
    if not clean or clean.upper() in RESERVED:
        clean = "Empresa"
    return clean


MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")


def nome_periodo(inicio, fim):
    start, end = date.fromisoformat(inicio), date.fromisoformat(fim)
    last_day = calendar.monthrange(start.year, start.month)[1]
    if (start.year, start.month) == (end.year, end.month) and start.day == 1 and end.day == last_day:
        return f"{start.month:02d} - {MESES[start