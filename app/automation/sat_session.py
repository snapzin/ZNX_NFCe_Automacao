"""Uma sessão do contador por job; credenciais apenas em memória."""
from contextlib import contextmanager
from dataclasses import dataclass, field



@dataclass(frozen=True)
class CredenciaisSAT:
    usuario: str = field(default="", repr=False)
    senha: str = field(default="", repr=False)

    def validar(self):
        if (not isinstance(self.usuario, str) or not self.usuario.strip()
                or not isinstance(self.senha, str) or not self.senha):
            raise ValueError("Informe usuário e senha para acessar o SAT")


@contextmanager
def abrir_sessao(config, credenciais, cancel_event, on_step):
    from app.automation.sat_http import ClienteSATHTTP
    credenciais.validar()
    client = ClienteSATHTTP(config, credenciais, cancel_event, on_step)
    try:
        yield client
    finally:
        client.close()
