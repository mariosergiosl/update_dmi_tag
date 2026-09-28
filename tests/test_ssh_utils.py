# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_ssh_utils.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_ssh_utils -v)
#
# DESCRIPTION: Opcoes do cliente SSH para alvos com OpenSSH antigo
#              (habilita_ssh_rsa_legado), leitura de versao OpenSSH e o
#              comando de gravacao do log remoto (gravar_log_remoto).
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.1
# CREATED: 2026-09-24
# REVISION: 2026-09-24 - v2.3.1 - criado.
#
# =======================================================================

import base64
import os
import re
import sys
import unittest
from unittest import mock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

from update_dmi_tag import ssh_utils as su  # noqa: E402
from update_dmi_tag import logging_utils as lu  # noqa: E402


class TestVersaoOpenssh(unittest.TestCase):

    def test_saida_do_cliente_e_banner_do_servidor(self):
        self.assertEqual(su.versao_openssh("OpenSSH_9.6p1, OpenSSL 3.5.0"), (9, 6))
        self.assertEqual(su.versao_openssh("SSH-2.0-OpenSSH_6.2"), (6, 2))
        self.assertEqual(su.versao_openssh("SSH-2.0-OpenSSH_6.6.1"), (6, 6))

    def test_nao_openssh(self):
        self.assertIsNone(su.versao_openssh("SSH-2.0-dropbear_2020"))
        self.assertIsNone(su.versao_openssh(""))


class TestHabilitaSshRsaLegadoV231(unittest.TestCase):
    """v2.3.1, campo 2026-09-24: runner com OpenSSH 9.6 nao usa ssh-rsa
    (SHA-1), a unica assinatura RSA do SLE 11 (6.2 e 6.6)."""

    def setUp(self):
        self.opts = list(su.SSH_OPTS)
        self.extra = list(su.SSH_OPTS_EXTRA)

    def tearDown(self):
        su.SSH_OPTS[:] = self.opts
        su.SSH_OPTS_EXTRA[:] = self.extra

    def _com_cliente(self, texto):
        with mock.patch.object(su.subprocess, "run",
                               return_value=mock.Mock(stderr=texto, stdout="")):
            return su.habilita_ssh_rsa_legado()

    def test_cliente_novo_ganha_opcao_uma_vez(self):
        self._com_cliente("OpenSSH_9.6p1, OpenSSL 3.5.0 8 Apr 2025")
        self._com_cliente("OpenSSH_9.6p1, OpenSSL 3.5.0 8 Apr 2025")
        self.assertEqual(su.SSH_OPTS.count("PubkeyAcceptedAlgorithms=+ssh-rsa"), 1)
        self.assertEqual(su.SSH_OPTS_EXTRA,
                         ["-o", "PubkeyAcceptedAlgorithms=+ssh-rsa"])

    def test_cliente_antigo_nao_muda(self):
        """8.4 ainda aceita ssh-rsa e nem sempre conhece a opcao nova."""
        self._com_cliente("OpenSSH_8.4p1, OpenSSL 1.1.1d")
        self.assertEqual(su.SSH_OPTS, self.opts)
        self.assertEqual(su.SSH_OPTS_EXTRA, [])

    def test_ssh_ausente_nao_quebra(self):
        with mock.patch.object(su.subprocess, "run", side_effect=OSError("x")):
            texto = su.habilita_ssh_rsa_legado()
        self.assertIn("nao identificado", texto)
        self.assertEqual(su.SSH_OPTS, self.opts)

    def test_scp_recebe_as_mesmas_opcoes(self):
        """Colisao: o scp (amidelnx, KMP) tambem precisa da opcao."""
        self._com_cliente("OpenSSH_9.6p1")
        with mock.patch.object(su.subprocess, "run",
                               return_value=mock.Mock(returncode=0)) as m:
            su.scp_arquivo("192.0.2.1", "root", "/tmp/a", "/tmp/b")
        self.assertIn("PubkeyAcceptedAlgorithms=+ssh-rsa", m.call_args[0][0])


class TestGravarLogRemotoV231(unittest.TestCase):
    """v2.3.1: a linha vai em base64 no comando, nao pelo stdin do sudo."""

    def _cmd(self, sudo_cmd, caminho="/var/log/update_dmi_tag.log"):
        with mock.patch.object(lu.subprocess, "run") as m:
            lu.gravar_log_remoto("192.0.2.1", "root", sudo_cmd, caminho,
                                 "INFO", "linha com 'aspas' e $VAR", "",
                                 False, True)
        return m.call_args[0][0][-1]

    def test_linha_decodificada_e_a_original(self):
        cmd = self._cmd("sudo")
        b64 = re.search(r"echo ([A-Za-z0-9+/=]+) \| base64 -d", cmd).group(1)
        linha = base64.b64decode(b64).decode("utf-8")
        self.assertTrue(linha.endswith("INFO - linha com 'aspas' e $VAR\n"))
        self.assertIn(">> /var/log/update_dmi_tag.log", cmd)

    def test_sudo_com_senha_nao_divide_o_stdin_com_a_linha(self):
        """Defeito: 'echo linha | echo senha | sudo -S tee' perdia a linha
        e, com credencial em cache, gravava a senha no arquivo."""
        cmd = self._cmd("echo 'segredo' | sudo -S")
        self.assertNotIn("tee", cmd)
        segundo = cmd.split("; ", 1)[1]
        self.assertTrue(segundo.startswith("echo 'segredo' | sudo -S sh -c '"),
                        segundo)

    def test_diretorio_criado_e_o_do_log(self):
        cmd = self._cmd("sudo", "/opt/logs/x.log")
        self.assertIn("mkdir -p /opt/logs", cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
