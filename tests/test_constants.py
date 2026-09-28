# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_constants.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_constants -v)
#
# DESCRIPTION: Assinaturas de incompatibilidade de firmware
#              (eh_incompatibilidade_firmware).
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
import unittest
from unittest import mock

# Raiz do repositorio (pai da pasta tests/), para importar o pacote sem
# depender de instalacao nem do diretorio corrente do chamador.
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

from update_dmi_tag.constants import eh_incompatibilidade_firmware  # noqa: E402

class TestIncompatibilidadeFirmware(unittest.TestCase):
    """Assinaturas de incompatibilidade de firmware (constants.py)."""

    def test_assinaturas_positivas(self):
        """Assinaturas reais de campo devem ser reconhecidas."""
        positivos = [
            "24 - Error: Problem allocating BIOS buffer.",
            "Error: Fail to initialize SMBIOS.",
            "d7 - Error: DMI Data write failed.",
            "sysfs rejeitou a escrita sem mensagem (rc=0)",
        ]
        for p in positivos:
            self.assertTrue(eh_incompatibilidade_firmware(p), p)

    def test_negativos(self):
        """Falhas genericas/transitorias nao devem ser confundidas."""
        negativos = ["", "Connection refused", "Permission denied",
                     "Done", "timeout"]
        for n in negativos:
            self.assertFalse(eh_incompatibilidade_firmware(n), n)


if __name__ == "__main__":
    unittest.main(verbosity=2)
