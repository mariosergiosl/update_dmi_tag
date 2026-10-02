# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_ssh_bootstrap.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_ssh_bootstrap -v)
#
# DESCRIPTION: Distribuicao de chave por senha (_ssh_copy_id_com_senha),
#              exercitada de verdade: pty real e um ssh-copy-id falso no
#              PATH, que imita o sshd. Mede o fato observavel (tempo ate
#              desistir, quantas vezes a senha foi enviada), nao so o
#              codigo de retorno. So roda em POSIX (pty).
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.4
# REVISION: 2026-10-02 - v2.3.4 - TestEscolhaChaveV234; TestChaveRsaV231
#                        passa a fixar o banner (a escolha da chave depende
#                        dele) e o caso de falha ao gerar a RSA vale para
#                        banner nao lido. TestLoginLentoV234: aviso de login
#                        lento e indicacao de teste cortado pelo limite.
# REVISION: 2026-09-24 - v2.3.1 - TestChaveRsaV231 e
#                        TestLimpaTemporariosV231.
# CREATED: 2026-09-23
# REVISION: 2026-09-23 - v2.3.0 - criado.
#
# =======================================================================

import os
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

from update_dmi_tag import ssh_bootstrap as sb  # noqa: E402

# ssh-copy-id falso. $MODO define o comportamento do "servidor":
#   repete - pede a senha, le, pede de novo e fica esperando (sshd com
#            keyboard-interactive recusando, como no SLE 11)
#   aceita - pede a senha, le e sai com 0
# Cada senha lida e anotada em $CONTADOR.
FALSO = """#!/bin/sh
printf 'Password: '
read -r s
echo "$s" >> "$CONTADOR"
if [ "$MODO" = "aceita" ]; then
    echo 'Number of key(s) added: 1'
    exit 0
fi
printf 'Password: '
sleep 60
"""


@unittest.skipUnless(os.name == "posix", "pty so existe em POSIX")
class TestSshCopyIdComSenha(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        falso = os.path.join(self.dir, "ssh-copy-id")
        with open(falso, "w") as f:
            f.write(FALSO)
        os.chmod(falso, stat.S_IRWXU)
        self.contador = os.path.join(self.dir, "senhas.txt")
        self.chave = os.path.join(self.dir, "id.pub")
        with open(self.chave, "w") as f:
            f.write("ssh-ed25519 AAAA teste\n")
        self.env = {
            "PATH": self.dir + os.pathsep + os.environ.get("PATH", ""),
            "CONTADOR": self.contador,
        }

    def tearDown(self):
        for nome in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, nome))
        os.rmdir(self.dir)

    def _roda(self, modo):
        env = dict(self.env, MODO=modo)
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(sb, "gravar_log") as m_log:
            inicio = time.time()
            ok = sb._ssh_copy_id_com_senha(
                "192.0.2.1", "testmec3", "senha#;%", self.chave,
                "", False, nivel_falha="WARNING")
            decorrido = time.time() - inicio
        with open(self.contador) as f:
            senhas = f.read().splitlines()
        return ok, decorrido, senhas, m_log

    def test_senha_recusada_com_novo_prompt_desiste_na_hora(self):
        """Regressao (bancada 2026-09-23, SLE 11): a recusa sem 'Permission
        denied' custava 30 s de timeout por host."""
        ok, decorrido, senhas, m_log = self._roda("repete")
        self.assertFalse(ok)
        self.assertLess(decorrido, 10, "esperou o timeout em vez de desistir")
        self.assertEqual(senhas, ["senha#;%"],
                         "a senha nao pode ser reenviada")
        niveis_textos = [(c[0][1], c[0][2]) for c in m_log.call_args_list]
        self.assertTrue(any(n == "WARNING" and "senha recusada" in t
                            for n, t in niveis_textos), niveis_textos)

    def test_senha_aceita_retorna_verdadeiro(self):
        ok, decorrido, senhas, _ = self._roda("aceita")
        self.assertTrue(ok)
        self.assertEqual(senhas, ["senha#;%"])


class _BaseHomeSsh(unittest.TestCase):
    """~/.ssh falso num diretorio temporario, com as constantes de chave
    do modulo apontando para ele."""

    def setUp(self):
        self.ssh = tempfile.mkdtemp()
        self.rsa = os.path.join(self.ssh, "id_rsa")
        self.ed = os.path.join(self.ssh, "id_ed25519")
        self.p_rsa = mock.patch.object(sb, "DEFAULT_SSH_KEY_RSA", self.rsa)
        self.p_ed = mock.patch.object(sb, "DEFAULT_SSH_KEY_ED25519", self.ed)
        self.p_rsa.start()
        self.p_ed.start()

    def tearDown(self):
        self.p_rsa.stop()
        self.p_ed.stop()
        import shutil
        shutil.rmtree(self.ssh, ignore_errors=True)

    def _cria(self, caminho):
        for c in (caminho, caminho + ".pub"):
            with open(c, "w") as f:
                f.write("x\n")


class TestChaveRsaV231(_BaseHomeSsh):
    """v2.3.1, defeito de campo 2026-09-24: o runner so tinha id_ed25519 e
    o SLE 11 SP3 (OpenSSH 6.2) nao conhece ed25519. O ssh-copy-id gravava a
    chave e a reconexao falhava. A chave distribuida passa a ser RSA."""

    def _keygen(self, falha_rsa=False):
        """ssh-keygen falso: cria o par pedido em -f (ou falha para rsa)."""
        chamadas = []

        def run(argv, **k):
            chamadas.append(argv)
            if argv[0] == "ssh-keygen":
                tipo = argv[argv.index("-t") + 1]
                if tipo == "rsa" and falha_rsa:
                    return mock.Mock(returncode=1, stderr="erro", stdout="")
                self._cria(argv[argv.index("-f") + 1])
            return mock.Mock(returncode=0, stderr="", stdout="")
        return run, chamadas

    def _prepara(self, falha_rsa=False, banner="SSH-2.0-OpenSSH_6.2"):
        run, chamadas = self._keygen(falha_rsa)
        with mock.patch.object(sb.subprocess, "run", side_effect=run), \
             mock.patch.object(sb, "versao_servidor_ssh", return_value=banner), \
             mock.patch.object(sb, "testa_conexao_ssh",
                               side_effect=[False, True]), \
             mock.patch.object(sb, "_ssh_copy_id_com_senha",
                               return_value=True) as m_copy, \
             mock.patch.object(sb, "gravar_log"):
            ok = sb.prepara_autenticacao_ssh("192.0.2.1", "root", "s", "", False)
        return ok, m_copy.call_args[0][3], chamadas

    def test_so_ed25519_gera_rsa_e_distribui_rsa(self):
        """Defeito: com so ed25519 a v2.3.0 distribuia a ed25519."""
        self._cria(self.ed)
        ok, pub, chamadas = self._prepara()
        self.assertTrue(ok)
        self.assertEqual(pub, self.rsa + ".pub")
        self.assertIn("rsa", chamadas[0])

    def test_rsa_existente_e_usada_sem_gerar(self):
        """Regressao: RSA ja existente continua sendo a escolhida."""
        self._cria(self.rsa)
        self._cria(self.ed)
        ok, pub, chamadas = self._prepara()
        self.assertEqual(pub, self.rsa + ".pub")
        self.assertEqual([c for c in chamadas if c[0] == "ssh-keygen"], [])

    def test_falha_ao_gerar_rsa_usa_a_ed25519_existente(self):
        """Adverso: sem RSA possivel, nao perde o acesso que ja funcionava.
        v2.3.4: com banner nao lido a ed25519 ja e a primeira."""
        self._cria(self.ed)
        ok, pub, _ = self._prepara(falha_rsa=True, banner="")
        self.assertTrue(ok)
        self.assertEqual(pub, self.ed + ".pub")

    def test_nenhuma_chave_gera_rsa(self):
        ok, pub, _ = self._prepara()
        self.assertEqual(pub, self.rsa + ".pub")
        self.assertTrue(os.path.isfile(self.rsa))
        self.assertFalse(os.path.isfile(self.ed))

    def test_reconexao_falha_registra_chave_e_banner(self):
        self._cria(self.rsa)
        with mock.patch.object(sb, "testa_conexao_ssh", return_value=False), \
             mock.patch.object(sb, "_ssh_copy_id_com_senha", return_value=True), \
             mock.patch.object(sb, "versao_servidor_ssh",
                               return_value="SSH-2.0-OpenSSH_6.2"), \
             mock.patch.object(sb, "gravar_log") as m_log:
            ok = sb.prepara_autenticacao_ssh("192.0.2.1", "root", "s", "", False)
        self.assertFalse(ok)
        texto = m_log.call_args_list[-1][0][2]
        self.assertIn("OpenSSH_6.2", texto)
        self.assertIn("id_rsa.pub", texto)


class TestLimpaTemporariosV231(_BaseHomeSsh):
    """v2.3.1: pastas ssh-copy-id.* deixadas pelo ssh-copy-id interrompido
    (65 no root do runner em 24/09/2026)."""

    def _pasta(self, nome, idade=0):
        caminho = os.path.join(self.ssh, nome)
        os.mkdir(caminho)
        with open(os.path.join(caminho, "f"), "w") as f:
            f.write("x")
        if idade:
            t = time.time() - idade
            os.utime(caminho, (t, t))
        return caminho

    def test_remove_so_as_desta_execucao(self):
        inicio = time.time() - 5
        nova = self._pasta("ssh-copy-id.AbCdE12345")
        antiga = self._pasta("ssh-copy-id.ZzZzZ00000", idade=3600)
        self.assertEqual(sb.limpa_temporarios_ssh_copy_id(inicio), 1)
        self.assertFalse(os.path.exists(nova))
        self.assertTrue(os.path.exists(antiga), "pasta de outra execucao")

    def test_nao_toca_nome_fora_do_padrao_nem_arquivo(self):
        inicio = time.time() - 5
        outra = self._pasta("ssh-copy-id.curto")
        arquivo = os.path.join(self.ssh, "ssh-copy-id.AbCdE12345")
        with open(arquivo, "w") as f:
            f.write("x")
        self._cria(self.rsa)
        self.assertEqual(sb.limpa_temporarios_ssh_copy_id(inicio), 0)
        self.assertTrue(os.path.exists(outra))
        self.assertTrue(os.path.isfile(arquivo))
        self.assertTrue(os.path.isfile(self.rsa))


class TestEscolhaChaveV234(_BaseHomeSsh):
    """v2.3.4, defeito de campo 2026-10-01: em SLED 12 (OpenSSH 7.2) a
    senha foi aceita e a chave RSA gravada, mas a conexao por ela foi
    recusada; com a ed25519 (2.3.0) a mesma conta entrou em 94 SLED 12.
    A chave passa a depender do banner do sshd, com troca para o outro
    tipo se a reconexao falhar."""

    def _keygen(self):
        """ssh-keygen falso: cria o par pedido em -f."""
        tipos = []

        def run(argv, **k):
            if argv[0] == "ssh-keygen":
                tipos.append(argv[argv.index("-t") + 1])
                self._cria(argv[argv.index("-f") + 1])
            return mock.Mock(returncode=0, stderr="", stdout="")
        return run, tipos

    def _roda(self, banner, conexoes, copia=True, nivel="ERROR"):
        """Executa o bootstrap; devolve (ok, chaves copiadas, tipos
        gerados, chamadas de log, banner lido)."""
        run, tipos = self._keygen()
        with mock.patch.object(sb.subprocess, "run", side_effect=run), \
             mock.patch.object(sb, "versao_servidor_ssh",
                               return_value=banner) as m_banner, \
             mock.patch.object(sb, "testa_conexao_ssh",
                               side_effect=conexoes), \
             mock.patch.object(sb, "_ssh_copy_id_com_senha",
                               return_value=copia) as m_copy, \
             mock.patch.object(sb, "gravar_log") as m_log:
            ok = sb.prepara_autenticacao_ssh("192.0.2.1", "f0000000", "s",
                                             "", False, nivel)
        copiadas = [os.path.basename(c[0][3]) for c in m_copy.call_args_list]
        return ok, copiadas, tipos, m_log.call_args_list, m_banner.called

    def test_sle12_distribui_ed25519_mesmo_com_rsa_existente(self):
        """Defeito: a 2.3.3 distribuia a id_rsa para o OpenSSH 7.2."""
        self._cria(self.rsa)
        self._cria(self.ed)
        ok, copiadas, tipos, _, _ = self._roda("SSH-2.0-OpenSSH_7.2",
                                               [False, True])
        self.assertTrue(ok)
        self.assertEqual(copiadas, ["id_ed25519.pub"])
        self.assertEqual(tipos, [])

    def test_sle12_so_com_rsa_gera_ed25519(self):
        """Defeito: usuario que so tem a RSA gerada pela 2.3.1."""
        self._cria(self.rsa)
        ok, copiadas, tipos, _, _ = self._roda("SSH-2.0-OpenSSH_7.2",
                                               [False, True])
        self.assertTrue(ok)
        self.assertEqual(tipos, ["ed25519"])
        self.assertEqual(copiadas, ["id_ed25519.pub"])

    def test_sle11_continua_so_com_rsa(self):
        """Regressao (v2.3.1): OpenSSH 6.2 nao conhece ed25519."""
        self._cria(self.ed)
        ok, copiadas, tipos, _, _ = self._roda("SSH-2.0-OpenSSH_6.2",
                                               [False, False])
        self.assertFalse(ok)
        self.assertEqual(copiadas, ["id_rsa.pub"],
                         "ed25519 nunca deve ir para OpenSSH antigo")
        self.assertEqual(tipos, ["rsa"])

    def test_limite_6_4_rsa_e_6_5_ed25519(self):
        """Fronteira da versao que introduziu ed25519."""
        self._cria(self.rsa)
        self._cria(self.ed)
        _, copiadas, _, _, _ = self._roda("SSH-2.0-OpenSSH_6.4", [False, True])
        self.assertEqual(copiadas, ["id_rsa.pub"])
        _, copiadas, _, _, _ = self._roda("SSH-2.0-OpenSSH_6.5", [False, True])
        self.assertEqual(copiadas, ["id_ed25519.pub"])

    def test_ed25519_recusada_tenta_rsa(self):
        """Adverso: se a ed25519 nao entrar, a RSA e distribuida."""
        self._cria(self.rsa)
        self._cria(self.ed)
        ok, copiadas, _, logs, _ = self._roda("SSH-2.0-OpenSSH_7.2",
                                              [False, False, True])
        self.assertTrue(ok)
        self.assertEqual(copiadas, ["id_ed25519.pub", "id_rsa.pub"])
        self.assertIn("id_rsa.pub", logs[-1][0][2])
        self.assertIn("validada", logs[-1][0][2])

    def test_as_duas_recusadas_registra_chaves_banner_e_nivel(self):
        """Adverso e colisao com o laco de perfis: o nivel pedido pelo
        chamador (WARNING quando ha outro perfil) vale para a falha final."""
        self._cria(self.rsa)
        self._cria(self.ed)
        ok, copiadas, _, logs, _ = self._roda(
            "SSH-2.0-OpenSSH_7.2", [False, False, False], nivel="WARNING")
        self.assertFalse(ok)
        self.assertEqual(copiadas, ["id_ed25519.pub", "id_rsa.pub"])
        nivel, texto = logs[-1][0][1], logs[-1][0][2]
        self.assertEqual(nivel, "WARNING")
        self.assertIn("id_ed25519.pub e id_rsa.pub", texto)
        self.assertIn("OpenSSH_7.2", texto)

    def test_senha_recusada_nao_tenta_outra_chave(self):
        """Adverso: a senha nao pode ser reenviada depois de recusada."""
        self._cria(self.rsa)
        self._cria(self.ed)
        ok, copiadas, _, _, _ = self._roda("SSH-2.0-OpenSSH_7.2", [False],
                                           copia=False)
        self.assertFalse(ok)
        self.assertEqual(copiadas, ["id_ed25519.pub"])

    def test_banner_nao_lido_ed25519_e_depois_rsa(self):
        self._cria(self.rsa)
        self._cria(self.ed)
        ok, copiadas, _, logs, _ = self._roda("", [False, False, False])
        self.assertEqual(copiadas, ["id_ed25519.pub", "id_rsa.pub"])
        self.assertIn("banner nao lido", logs[-1][0][2])

    def test_chave_ja_autorizada_nao_le_banner_nem_copia(self):
        """Regressao: caminho feliz silencioso, sem gerar chave."""
        ok, copiadas, tipos, logs, banner_lido = self._roda(
            "SSH-2.0-OpenSSH_7.2", [True])
        self.assertTrue(ok)
        self.assertEqual((copiadas, tipos, logs, banner_lido),
                         ([], [], [], False))

    def test_sem_senha_nao_le_banner(self):
        with mock.patch.object(sb, "testa_conexao_ssh", return_value=False), \
             mock.patch.object(sb, "versao_servidor_ssh") as m_banner, \
             mock.patch.object(sb, "gravar_log") as m_log:
            ok = sb.prepara_autenticacao_ssh("192.0.2.1", "u", "", "", False)
        self.assertFalse(ok)
        self.assertFalse(m_banner.called)
        self.assertIn("nenhuma senha", m_log.call_args_list[-1][0][2])


class TestLoginLentoV234(_BaseHomeSsh):
    """v2.3.4: o defeito de campo era o teste de conexao cortado pelo tempo;
    o log precisa dizer isso em vez de sugerir chave recusada."""

    def _conexao(self, resultados, duracao):
        """testa_conexao_ssh falso que 'demora' avancando o relogio."""
        relogio = [1000.0]
        fila = list(resultados)

        def testa(ip, user):
            relogio[0] += duracao
            return fila.pop(0)
        return testa, (lambda: relogio[0])

    def _roda(self, resultados, duracao, limite=30):
        self._cria(self.rsa)
        self._cria(self.ed)
        testa, agora = self._conexao(resultados, duracao)
        with mock.patch.object(sb, "testa_conexao_ssh", side_effect=testa), \
             mock.patch.object(sb.time, "time", side_effect=agora), \
             mock.patch.object(sb.ssh_utils, "TIMEOUT_TESTE_CONEXAO", limite), \
             mock.patch.object(sb, "versao_servidor_ssh",
                               return_value="SSH-2.0-OpenSSH_7.2"), \
             mock.patch.object(sb, "_ssh_copy_id_com_senha", return_value=True), \
             mock.patch.object(sb, "gravar_log") as m_log:
            ok = sb.prepara_autenticacao_ssh("192.0.2.1", "u", "s", "", False)
        return ok, [(c[0][1], c[0][2]) for c in m_log.call_args_list]

    def test_login_lento_aceito_gera_aviso(self):
        ok, logs = self._roda([True], 11.3)
        self.assertTrue(ok)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0][0], "WARNING")
        self.assertIn("lento (11.3 s", logs[0][1])

    def test_login_rapido_continua_silencioso(self):
        """Regressao: caminho feliz sem log."""
        ok, logs = self._roda([True], 0.5)
        self.assertTrue(ok)
        self.assertEqual(logs, [])

    def test_teste_cortado_pelo_limite_e_indicado_na_falha(self):
        """Defeito: a mensagem falava so em reconexao falhando."""
        ok, logs = self._roda([False, False, False], 30, limite=30)
        self.assertFalse(ok)
        self.assertIn("teste cortado pelo limite de 30 s", logs[-1][1])
        self.assertIn("--ssh-timeout", logs[-1][1])

    def test_recusa_rapida_nao_indica_corte(self):
        """Adverso: chave recusada de verdade nao sugere aumentar o limite."""
        ok, logs = self._roda([False, False, False], 0.3)
        self.assertFalse(ok)
        self.assertNotIn("cortado", logs[-1][1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
