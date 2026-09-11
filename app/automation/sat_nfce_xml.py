"""Extrai XML assinado e corrige apenas a indentação acrescentada ao lote pela SEF."""
import base64
from copy import deepcopy
import hashlib
import hmac

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from app.automation.sat_nfce_api import ErroAPI

DS = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
ENVELOPED = DS["ds"] + "enveloped-signature"


def canon(element):
    # Isola o nó com os namespaces em escopo, sem o contexto do envelope do lote.
    return etree.tostring(deepcopy(element), method="c14n", exclusive=False, with_comments=False)


def assinatura_confere(root):
    """Confere digest e assinatura RSA; não substitui validação fiscal ou cadeia ICP."""
    try:
        signatures = root.findall(".//ds:Signature", DS)
        if not signatures:
            return False
        for signature in signatures:
            signed = signature.find("ds:SignedInfo", DS)
            if signed.find("ds:CanonicalizationMethod", DS).get("Algorithm") != C14N:
                return False
            references = signed.findall("ds:Reference", DS)
            if not references:
                return False
            for ref in references:
                uri = ref.get("URI", "")
                if not uri.startswith("#") or not uri[1:]:
                    return False
                targets = root.xpath("descendant-or-self::*[@Id=$id]", id=uri[1:])
                transforms = [e.get("Algorithm") for e in ref.findall("ds:Transforms/ds:Transform", DS)]
                if len(targets) != 1 or transforms != [ENVELOPED, C14N]:
                    return False
                # No padrão NFC-e, Signature é irmã do nó referenciado.
                if targets[0].find(".//ds:Signature", DS) is not None:
                    return False
                algorithm = ref.find("ds:DigestMethod", DS).get("Algorithm")
                digest = {DS["ds"] + "sha1": hashlib.sha1,
                          "http://www.w3.org/2001/04/xmlenc#sha256": hashlib.sha256}.get(algorithm)
                if digest is None or not hmac.compare_digest(
                    digest(canon(targets[0])).digest(),
                    base64.b64decode(ref.find("ds:DigestValue", DS).text)):
                    return False
            algorithm = signed.find("ds:SignatureMethod", DS).get("Algorithm")
            hash_type = {DS["ds"] + "rsa-sha1": hashes.SHA1,
                         "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256": hashes.SHA256}.get(algorithm)
            if hash_type is None:
                return False
            cert = x509.load_der_x509_certificate(base64.b64decode(
                signature.find(".//ds:X509Certificate", DS).text))
            cert.public_key().verify(base64.b64decode(signature.find("ds:SignatureValue", DS).text),
                                     canon(signed), padding.PKCS1v15(), hash_type())
        return True
    except Exception:
        return False


def preparar_xml(documento):
    original = etree.tostring(documento, encoding="UTF-8", xml_declaration=True, with_tail=False)
    if assinatura_confere(documento):
        return original
    # O serviço observado indenta os documentos. Só usar a versão sem indentação
    # quando o digest e a assinatura originais comprovarem sua integridade.
    candidate = etree.fromstring(original, etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, remove_blank_text=True))
    if not assinatura_confere(candidate):
        raise ErroAPI("Integridade da assinatura do XML não confirmada; lote original preservado")
    return etree.tostring(candidate, encoding="UTF-8", xml_declaration=True, with_tail=False)
