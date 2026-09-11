"""Cliente SOAP do serviço oficial NFC-e SC, conforme BT SC-2026/003 v1.00-1."""
import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import gzip
import io
from pathlib import Path
import re
import ssl
import warnings

from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, NoEncryption
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates, serialize_key_and_certificates
from defusedxml import ElementTree as ET
import requests
from requests_pkcs12 import Pkcs12Adapter

ENDPOINT = "https://dfe.sat.sef.sc.gov.br/nfce/ws/distribuicao/DistribuicaoNfceDownload.asmx"
NAMESPACE = "http://www.satnfce.sef.sc.gov.br/ws/distribuicao-v1"


class ErroAPI(RuntimeError):
    pass


@dataclass(frozen=True)
class CertificadoAPI:
    arquivo: str = field(repr=False)
    senha: str = field(repr=False)

    def carregar(self):
        try:
            data = Path(self.arquivo).read_bytes()
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="PKCS#12 bundle could not be parsed as DER.*")
                key, cert, chain = load_key_and_certificates(data, self.senha.encode("utf-8"))
        except Exception:
            raise ErroAPI("Não foi possível abrir o certificado A1; confira arquivo e senha") from None
        now = datetime.now(timezone.utc)
        if cert is None or key is None:
            raise ErroAPI("Certificado A1 sem chave privada utilizável")
        if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
            raise ErroAPI("Certificado A1 fora do período de validade")
        encryption = BestAvailableEncryption(self.senha.encode("utf-8")) if self.senha else NoEncryption()
        # Normaliza em memória os A1 BER aceitos pela biblioteca, mantendo chave e cadeia.
        return serialize_key_and_certificates(None, key, cert, chain, encryption), cert


def mensagem(cnpj, nsu=0, ator=1):
    if not re.fullmatch(r"[A-Z0-9]{12}\d{2}", cnpj) or not 0 <= int(nsu) < 10**18 or ator not in {1, 2, 3, 9}:
        raise ValueError("Parâmetros de consulta inválidos")
    return (f'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
            f'<nfceDownloadContab xmlns="{NAMESPACE}"><distNFCeSC versao="1.00">'
            f'<tpAmb>1</tpAmb><verAplic>ZNX-SAT-0.5.1</verAplic><cUF>42</cUF><CNPJ>{cnpj}</CNPJ>'
            f'<solRel><indXML>1</indXML><indAtor>{ator}</indAtor><ultNuNSU>{int(nsu)}</ultNuNSU></solRel>'
            '</distNFCeSC></nfceDownloadContab></soap:Body></soap:Envelope>').encode("utf-8")


def nome_local(tag):
    return tag.rsplit("}", 1)[-1]


@dataclass(repr=False)
class LoteAPI:
    codigo: str
    ultimo_nsu: int
    quantidade: int
    lote_xml: bytes = field(repr=False, default=b"")


def ler_resposta(data):
    try:
        root = ET.fromstring(data)
        result = next((e for e in root.iter() if nome_local(e.tag) == "retDistNFCeSC"), None)
        if result is None:
            raise ValueError()
        fields = {nome_local(e.tag): e.text or "" for e in result}
        code = fields["cStat"]
        if not re.fullmatch(r"\d{3,4}", code):
            raise ValueError()
        lote = b""
        if fields.get("loteDistComp"):
            compressed = base64.b64decode(''.join(fields["loteDistComp"].split()), validate=True)
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                lote = stream.read(32 * 1024 * 1024 + 1)
            if len(lote) > 32 * 1024 * 1024:
                raise ValueError()
            ET.fromstring(lote)
        return LoteAPI(code, int(fields.get("ultNuNSURet") or 0), int(fields.get("qtDfeRet") or 0), lote)
    except Exception:
        raise ErroAPI("Resposta da API NFC-e não reconhecida; conteúdo sensível omitido") from None


MENSAGENS = {
    "117": "Nenhum documento disponível para distribuição",
    "118": "Documentos localizados",
    "108": "Serviço temporariamente indisponível",
    "109": "Serviço indisponível sem previsão",
    "110": "Documentos em reprocessamento; aguardar uma hora",
    "215": "API rejeitou o formato XML da solicitação",
    "280": "API não aceitou o certificado transmissor",
    "281": "API rejeitou a validade do certificado",
    "283": "API rejeitou a cadeia de certificação",
    "284": "Certificado revogado",
    "285": "Certificado não reconhecido como ICP-Brasil",
    "286": "Falha ao consultar a lista de certificados revogados",
    "489": "CNPJ/CPF inválido",
    "632": "Documento fora do período disponível",
    "657": "API bloqueou temporariamente novas tentativas",
    "8002": "Requisitante não é contabilista do CNPJ informado",
    "9999": "Falha de processamento no serviço da SEF",
}


class ClienteNFCeAPI:
    def __init__(self, session):
        self.session = session

    def consultar_lote(self, cnpj, nsu=0, ator=1):
        payload = mensagem(cnpj, nsu, ator)
        try:
            with self.session.post(ENDPOINT, data=payload, headers={
                "Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{NAMESPACE}/nfceDownloadContab"'},
                allow_redirects=False, timeout=(20, 120), stream=True) as response:
                if response.status_code != 200:
                    raise ErroAPI(f"API NFC-e respondeu HTTP {response.status_code}")
                pieces = []
                size = 0
                for piece in response.iter_content(65536):
                    size += len(piece)
                    if size > 16 * 1024 * 1024:
                        raise ErroAPI("Resposta da API excedeu o limite esperado")
                    pieces.append(piece)
                return ler_resposta(b"".join(pieces))
        except requests.RequestException:
            raise ErroAPI("Falha na conexão autenticada com a API NFC-e") from None


@contextmanager
def abrir_api(certificado):
    data, cert = certificado.carregar()
    try:
        adapter = Pkcs12Adapter(pkcs12_data=data, pkcs12_password=certificado.senha)
        adapter.ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        adapter.ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        raise ErroAPI("Não foi possível preparar o certificado A1 para a conexão TLS") from None
    with requests.Session() as session:
        # O certificado só é apresentado ao endpoint oficial; não seguir redirecionamentos.
        session.mount(ENDPOINT, adapter)
        yield ClienteNFCeAPI(session)
