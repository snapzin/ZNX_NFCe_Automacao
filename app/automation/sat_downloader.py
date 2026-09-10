"""Ponto de extensão para consulta/download depois da homologação do login.

TODO: observar aplicação CONX, seleção de perfil, consulta, filtros, resultados
e download. Nenhum seletor, URL interna ou formato de XML é presumido.
"""


class FluxoNaoMapeado(RuntimeError):
    pass


def consultar_e_baixar(page, *, cliente, data_inicio, data_fim, pasta_saida):
    raise FluxoNaoMapeado("Consulta e download NFC-e aguardam mapeamento do fluxo real SAT")
