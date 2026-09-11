import base64
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from threading import Event
from unittest.mock import Mock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree
import pytest
import requests

from app.automation.sat_auth import ExecucaoCancelada
from app.automation.sat_nfce_api import (
    CertificadoAPI, ClienteNFCeAPI, ErroAPI, LoteAPI, ler_resposta, mensagem,
)
from app.automation.sat_nfce_download import baixar_periodo, documentos_lote
from app.automation.sat_nfce_xml import DS, C14N, ENVELOPED, assinatura_confere, canon, preparar_xml

CNPJ = "12345678000195"
NFE = "http://www.portalfiscal.inf.br/nfe"


@pytest.fixture(scope="module")
def signed_xml():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "Teste sintetico")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1)).sign(key, hashes.SHA256()))
    root = etree.fromstring(f'<nfeProc xmlns="{NFE}"><NFe><infNFe Id="NFeTeste">'
        '<ide><mod>65</mod><dhEmi>2026-08-01T10:00:00-03:00</dhEmi></ide>'
        '<det><xProd>Produto com  espacos</xProd></det></infNFe></NFe></nfeProc>')
    nfe = root[0]
    signature = etree.SubElement(nfe, etree.QName(DS["ds"], "Signature"), nsmap={None: DS["ds"]})
    def element(parent, name, **attributes):
        return etree.SubElement(parent, etree.QName(DS["ds"], name), **attributes)
    info = element(signature, "SignedInfo")
    element(info, "CanonicalizationMethod", Algorithm=C14N)
    element(info, "SignatureMethod", Algorithm=DS["ds"] + "rsa-sha1")
    ref = element(info, "Reference", URI="#NFeTeste")
    transforms = element(ref, "Transforms")
    element(transforms, "Transform", Algorithm=ENVELOPED)
    element(transforms, "Transform", Algorithm=C14N)
    element(ref, "DigestMethod", Algorithm=DS["ds"] + "sha1")
    element(ref, "DigestValue").text = base64.b64encode(hashlib.sha1(canon(nfe[0])).digest()).decode()
    element(signature, "SignatureValue").text = base64.b64encode(key.sign(canon(info), padding.PKCS1v15(), hashes.SHA1())).decode()
    cert_node = element(element(element(signature, "KeyInfo"), "X509Data"), "X509Certificate")
    cert_node.text = base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()
    return etree.tostring(root)


def batch(xml, first=1, count=1):
    data = b'<loteDistNFCeSC>' + b''.join(
        f'<distNFCeSC NSU="{i}">'.encode() + xml + b'</distNFCeSC>'
        for i in range(first, first + count)) + b'</loteDistNFCeSC>'
    return LoteAPI("118", first + count - 1, count, data)


def download(api, tmp_path, **kwargs):
    return baixar_periodo(api, cnpj=CNPJ, inicio="2026-08-01", fim="2026-08-31", pasta_saida=tmp_path, **kwargs)


def test_soap_and_gzip_response(signed_xml):
    payload = etree.fromstring(mensagem(CNPJ, 42))
    assert payload.xpath('string(//*[local-name()="ultNuNSU"])') == "42"
    assert payload.xpath('string(//*[local-name()="CNPJ"])') == CNPJ
    data = batch(signed_xml).lote_xml
    encoded = base64.b64encode(gzip.compress(data)).decode()
    response = ler_resposta(f'<Envelope><retDistNFCeSC><cStat>118</cStat><ultNuNSURet>1</ultNuNSURet>'
        f'<qtDfeRet>1</qtDfeRet><loteDistComp>{encoded}</loteDistComp></retDistNFCeSC></Envelope>'.encode())
    assert response.lote_xml == data and response.quantidade == 1


@pytest.mark.parametrize("body", [b'<invalid>', b'<Envelope>secret</Envelope>',
    b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///secret">]><x>&e;</x>'])
def test_invalid_response_does_not_expose_data(body):
    with pytest.raises(ErroAPI) as exc:
        ler_resposta(body)
    assert "secret" not in str(exc.value)


def test_certificate_and_network_errors_hide_secrets(tmp_path):
    cert = CertificadoAPI(str(tmp_path / "secret-name.pfx"), "secret-password")
    assert "secret" not in repr(cert)
    with pytest.raises(ErroAPI) as exc:
        cert.carregar()
    assert "secret" not in str(exc.value)
    session = Mock()
    session.post.side_effect = requests.ConnectionError("secret-password")
    with pytest.raises(ErroAPI) as exc:
        ClienteNFCeAPI(session).consultar_lote(CNPJ)
    assert "secret" not in str(exc.value)


def test_signed_xml_normalization_preserves_content(signed_xml):
    root = etree.fromstring(signed_xml)
    assert assinatura_confere(root)
    assert preparar_xml(root).endswith(signed_xml)
    pretty = etree.fromstring(etree.tostring(root, pretty_print=True))
    assert not assinatura_confere(pretty)
    restored = preparar_xml(pretty)
    assert assinatura_confere(etree.fromstring(restored))
    assert b'Produto com  espacos' in restored


def test_tampered_xml_rejected(signed_xml):
    root = etree.fromstring(signed_xml.replace(b'Produto', b'Alterado'))
    with pytest.raises(ErroAPI, match="Integridade"):
        preparar_xml(root)


def test_full_batch_continues_and_partial_batch_sets_cooldown(tmp_path, signed_xml):
    api = Mock()
    api.consultar_lote.side_effect = [batch(signed_xml, 1, 50), batch(signed_xml, 51, 1)]
    result = download(api, tmp_path)
    assert result.status == "ok" and result.notas == 51
    assert [call.args[1] for call in api.consultar_lote.call_args_list] == [0, 50]
    api.reset_mock()
    cached = download(api, tmp_path)
    api.consultar_lote.assert_not_called()
    assert cached.notas == 51 and "cache" in cached.message


def test_failed_continuation_preserves_checkpoint(tmp_path, signed_xml):
    api = Mock()
    api.consultar_lote.side_effect = [batch(signed_xml, 1, 50), ErroAPI("Falha de transporte")]
    with pytest.raises(ErroAPI):
        download(api, tmp_path)
    cache = tmp_path / ".cache_nfce" / CNPJ / "api_sef"
    state = json.loads((cache / "estado.json").read_text())
    assert state["nsu"] == 50 and not state["completo"]
    assert (cache / "lote_0_50.xml").exists()
    api.reset_mock()
    assert download(api, tmp_path).status == "pendente"
    api.consultar_lote.assert_not_called()


@pytest.mark.parametrize("code, status", [("117", "ok"), ("8002", "pendente"), ("657", "pendente")])
def test_status_and_cooldown(tmp_path, code, status):
    api = Mock()
    api.consultar_lote.return_value = LoteAPI(code, 0, 0)
    result = download(api, tmp_path)
    assert result.status == status and result.documentos == 0
    api.reset_mock()
    download(api, tmp_path)
    api.consultar_lote.assert_not_called()


def test_inconsistent_batch_never_advances_nsu(tmp_path, signed_xml):
    api = Mock()
    response = batch(signed_xml)
    response.quantidade = 2
    api.consultar_lote.return_value = response
    with pytest.raises(ErroAPI, match="inconsistente"):
        download(api, tmp_path)
    state = json.loads((tmp_path / ".cache_nfce" / CNPJ / "api_sef" / "estado.json").read_text())
    assert state["nsu"] == 0


def test_cancellation_does_not_send_request(tmp_path):
    api = Mock()
    cancel = Event()
    cancel.set()
    with pytest.raises(ExecucaoCancelada):
        download(api, tmp_path, cancel_event=cancel)
    api.consultar_lote.assert_not_called()


def test_wrong_model_is_rejected(signed_xml):
    with pytest.raises(ErroAPI, match="modelo 65"):
        documentos_lote(batch(signed_xml.replace(b'<mod>65', b'<mod>55')).lote_xml)
