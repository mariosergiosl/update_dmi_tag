# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_hosts.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_hosts -v)
#
# DESCRIPTION: Parse do arquivo de hosts (le_arquivo_hosts).
#              Roda em qualquer maquina, sem SSH real: tudo que toca
#              rede e mockado via unittest.mock. Nenhuma dependencia
#              alem da stdlib.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.2.9
# CREATED: 2026-08-10
# REVISION: 2026-08-10 - v2.2.9 - arquivo criado a partir da divisao de
#                        tests/test_regressao.py, que havia chegado a
#                        1107 linhas. Os testes sao os mesmos, sem
#                        alteracao de logica; muda so a organizacao,
#                        agora um arquivo por modulo testado.
#
# =======================================================================

import os
import sys
import tempfile
import unittest
from unittest import mock

# Raiz do repositorio (pai da pasta tests/), para importar o pacote sem
# depender de instalacao nem do diretorio corrente do chamador.
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

from update_dmi_tag.hosts import le_arquivo_hosts  # noqa: E402

class TestLeArquivoHosts(unittest.TestCase):
    """Parse do arquivo de hosts."""

    def test_parse_completo(self):
        """Comentarios, linhas vazias, IP puro, IP,BEM e comentario de
        fim de linha devem ser tratados."""
        conteudo = (
            "# comentario inteiro\n"
            "\n"
            "192.168.56.10\n"
            "192.168.56.11,7417161830398\n"
            "192.168.56.12 # equip-01\n"
            "   \n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="ascii") as f:
            f.write(conteudo)
            caminho = f.name
        try:
            hosts = le_arquivo_hosts(caminho)
        finally:
            os.remove(caminho)
        self.assertEqual(hosts, [
            ("192.168.56.10", ""),
            ("192.168.56.11", "7417161830398"),
            ("192.168.56.12", ""),
        ])

if __name__ == "__main__":
    unittest.main(verbosity=2)
