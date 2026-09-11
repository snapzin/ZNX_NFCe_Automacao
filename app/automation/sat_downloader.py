"""Ponto de extensão para consulta/download depois da homologação do login.

TODO: observar aplicação CONX, seleção de perfil, consulta, filtros, resultados
e download. Nenhum seletor, URL interna ou formato de XML é presumido.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoDownload:
    documentos: int


class FluxoNaoMapeado(RuntimeError):
    pass


def consultar_e_baixar(session, *, cliente, data_inicio, data_fim, pasta_saida):
    from app.automation.sat_http import ValidacaoHumanaNecessaria
    session.abrir_consulta_nfce()
    if session.exige_validacao_humana():
        raise ValidacaoHumanaNecessaria("SAT exige validação humana na consulta NFC-e; download não iniciado")
    raise FluxoNaoMapeado("Login HTTP confirmado; resposta da consulta/download ainda não homologada")
