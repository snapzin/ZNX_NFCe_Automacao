import os
import tempfile

# Não acessa cadastro, licença ou configuração reais durante testes.
_data = tempfile.TemporaryDirectory(prefix="znx_sat_test_")
os.environ["SAT_DATA_DIR"] = _data.name
os.environ["SAT_CLIENTES_REMOTE"] = "0"
