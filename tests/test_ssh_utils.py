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
# VERSION: 2.3.4
# REVISION: 2026-10-02 - v2.3.4 - TestTimeoutTesteConexaoV234.
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
        # v2.3.6: a lista passou a ter tambem a opcao da chave de servidor.
        self.assertEqual(su.SSH_OPTS_EXTRA,
                         ["-o", "PubkeyAcceptedAlgorithms=+ssh-rsa",
                          "-o", "HostKeyAlgorithms=+ssh-rsa"])

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


class TestHostKeyRsaV236(unittest.TestCase):
    """v2.3.6, campo 2026-10-14: 3 SLE 11 com sshd que so oferece chave de
    servidor ssh-rsa/ssh-dss terminaram "no matching host key type found";
    a 2.3.1 so habilitava ssh-rsa para a chave do usuario."""

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

    def test_cliente_novo_ganha_hostkey_uma_vez(self):
        self._com_cliente("OpenSSH_9.6p1, OpenSSL 3.5.0 8 Apr 2025")
        self._com_cliente("OpenSSH_9.6p1, OpenSSL 3.5.0 8 Apr 2025")
        self.assertEqual(su.SSH_OPTS.count("HostKeyAlgorithms=+ssh-rsa"), 1)
        self.assertEqual(su.SSH_OPTS_EXTRA.count("HostKeyAlgorithms=+ssh-rsa"), 1)

    def test_cliente_8_8_exato_ganha_hostkey(self):
        """Limite: 8.8 e a primeira versao que recusa ssh-rsa."""
        self._com_cliente("OpenSSH_8.8p1")
        self.assertIn("HostKeyAlgorithms=+ssh-rsa", su.SSH_OPTS)

    def test_cliente_antigo_nao_ganha_hostkey(self):
        self._com_cliente("OpenSSH_8.7p1")
        self.assertNotIn("HostKeyAlgorithms=+ssh-rsa", su.SSH_OPTS)
        self.assertEqual(su.SSH_OPTS_EXTRA, [])

    def test_ssh_run_recebe_hostkey(self):
        """Colisao: o ssh dos comandos remotos usa SSH_OPTS."""
        self._com_cliente("OpenSSH_9.6p1")
        with mock.patch.object(su.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout="",
                                                      stderr="")) as m:
            su.ssh_run("192.0.2.1", "root", "true")
        self.assertIn("HostKeyAlgorithms=+ssh-rsa", m.call_args[0][0])

    def test_scp_recebe_hostkey(self):
        self._com_cliente("OpenSSH_9.6p1")
        with mock.patch.object(su.subprocess, "run",
                               return_value=mock.Mock(returncode=0)) as m:
            su.scp_arquivo("192.0.2.1", "root", "/tmp/a", "/tmp/b")
        self.assertIn("HostKeyAlgorithms=+ssh-rsa", m.call_args[0][0])


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


class TestTimeoutTesteConexaoV234(unittest.TestCase):
    """v2.3.4, defeito de campo 2026-10-01/02: SLED 12 levavam de 7 a 11 s
    para concluir o login por chave; o teste cortava o ssh aos 5 s e o host
    era dado como sem chave, com a senha aceita e a chave gravada a cada
    execucao."""

    def setUp(self):
        self.p = mock.patch.object(su, "TIMEOUT_TESTE_CONEXAO",
                                   su.TIMEOUT_TESTE_CONEXAO)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def _ssh_falso(self, espera, rc):
        """Cria um ssh falso no PATH que espera e sai com rc."""
        import shutil
        import tempfile
        pasta = tempfile.mkdtemp()
        caminho = os.path.join(pasta, "ssh")
        with open(caminho, "w") as f:
            f.write("#!/bin/sh\nsleep {}\nexit {}\n".format(espera, rc))
        os.chmod(caminho, 0o755)
        self.addCleanup(shutil.rmtree, pasta, True)
        return mock.patch.dict(os.environ,
                               {"PATH": pasta + os.pathsep + os.environ["PATH"]})

    def test_padrao_e_30_s(self):
        """Defeito: a versao anterior passava timeout=5 ao ssh_run."""
        with mock.patch.object(su, "ssh_run", return_value=(0, "", "")) as m:
            self.assertTrue(su.testa_conexao_ssh("192.0.2.1", "u"))
        self.assertEqual(m.call_args[1]["timeout"], 30)

    def test_opcao_ajusta_o_limite(self):
        """--ssh-timeout chega ao teste usado pela triagem e pelo bootstrap."""
        texto = su.define_timeout_teste_conexao(45)
        self.assertIn("45 s", texto)
        with mock.patch.object(su, "ssh_run", return_value=(0, "", "")) as m:
            su.testa_conexao_ssh("192.0.2.1", "u")
        self.assertEqual(m.call_args[1]["timeout"], 45)

    def test_limite_explicito_prevalece(self):
        """Colisao: quem passa o proprio limite continua no controle."""
        su.define_timeout_teste_conexao(45)
        with mock.patch.object(su, "ssh_run", return_value=(0, "", "")) as m:
            su.testa_conexao_ssh("192.0.2.1", "u", timeout=7)
        self.assertEqual(m.call_args[1]["timeout"], 7)

    @unittest.skipUnless(os.name == "posix", "ssh falso em shell")
    def test_login_lento_de_8_s_e_aceito(self):
        """Defeito, fato observavel: ssh que leva 8 s e entra."""
        with self._ssh_falso(8, 0):
            self.assertTrue(su.testa_conexao_ssh("192.0.2.1", "u"))

    @unittest.skipUnless(os.name == "posix", "ssh falso em shell")
    def test_ssh_preso_alem_do_limite_nao_vira_sucesso(self):
        """Adverso: o corte por tempo continua valendo."""
        su.define_timeout_teste_conexao(1)
        with self._ssh_falso(60, 0):
            self.assertFalse(su.testa_conexao_ssh("192.0.2.1", "u"))

    def test_comando_recebe_folga_de_login(self):
        """Defeito: comandos de 10 s eram cortados em host que leva 8 a 11 s
        so para logar (conferencia do scp, deteccao do sudo)."""
        with mock.patch.object(su.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout="",
                                                      stderr="")) as m:
            su.ssh_run("192.0.2.1", "u", "true", timeout=10)
        self.assertEqual(m.call_args[1]["timeout"], 40)

    def test_folga_acompanha_ssh_timeout(self):
        """Colisao: --ssh-timeout ajusta teste de conexao e folga juntos."""
        su.define_timeout_teste_conexao(45)
        with mock.patch.object(su.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout="",
                                                      stderr="")) as m:
            su.ssh_run("192.0.2.1", "u", "true", timeout=10)
            su.testa_conexao_ssh("192.0.2.1", "u")
        self.assertEqual([c[1]["timeout"] for c in m.call_args_list], [55, 45])

    def test_teste_de_conexao_nao_soma_folga(self):
        """Regressao: o teste de conexao continua no proprio limite."""
        with mock.patch.object(su.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout="",
                                                      stderr="")) as m:
            su.testa_conexao_ssh("192.0.2.1", "u")
        self.assertEqual(m.call_args[1]["timeout"], 30)

    def test_scp_recebe_folga_de_login(self):
        with mock.patch.object(su.subprocess, "run",
                               return_value=mock.Mock(returncode=0, stdout="",
                                                      stderr="")) as m:
            su.scp_arquivo("192.0.2.1", "u", "a", "/tmp/a")
            su._scp_arquivo_com_erro("192.0.2.1", "u", "a", "/tmp/a")
        self.assertEqual([c[1]["timeout"] for c in m.call_args_list], [90, 90])

    @unittest.skipUnless(os.name == "posix", "ssh falso em shell")
    def test_comando_de_10_s_em_login_lento_conclui(self):
        """Defeito, fato observavel: login de 8 s + comando, limite 10 s."""
        su.define_timeout_teste_conexao(5)
        with self._ssh_falso(8, 0):
            rc, _, err = su.ssh_run("192.0.2.1", "u", "true", timeout=10)
        self.assertEqual((rc, err), (0, ""))

    @unittest.skipUnless(os.name == "posix", "ssh falso em shell")
    def test_chave_recusada_falha_na_hora(self):
        """Regressao: recusa (rc 255) continua False, sem esperar o limite."""
        import time
        inicio = time.time()
        with self._ssh_falso(0, 255):
            self.assertFalse(su.testa_conexao_ssh("192.0.2.1", "u"))
        self.assertLess(time.time() - inicio, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
