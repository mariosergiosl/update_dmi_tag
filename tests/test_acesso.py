# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_acesso.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_acesso -v)
#
# DESCRIPTION: Leitura do arquivo de perfis de acesso (--acesso, v2.3.0):
#              ordem dos perfis, senhas literais com '#', ';' e '%',
#              recusa de permissao aberta, erros de formato, ordem das
#              senhas do sudo e o perfil unico da linha de comando, que
#              preserva o comportamento anterior a v2.3.0.
#              Nenhuma dependencia alem da stdlib.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.0
# CREATED: 2026-09-23
# REVISION: 2026-09-23 - v2.3.0 - criado.
#
# =======================================================================

import os
import sys
import tempfile
import types
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

from update_dmi_tag import acesso  # noqa: E402

EXEMPLO = (
    "# comentario de linha inteira\n"
    "[operador]\n"
    "; outro comentario\n"
    "usuario = f4683594\n"
    "senha = s3nh#a;com%tudo\n"
    "senha_sudo =\n"
    "\n"
    "[root]\n"
    "usuario = root\n"
    "senha = Temp#2026;X\n"
)


class _BaseArquivo(object):
    """Grava o conteudo num arquivo temporario com permissao 600."""

    def _arquivo(self, conteudo, modo=0o600):
        fd, caminho = tempfile.mkstemp(suffix=".conf")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(conteudo)
        os.chmod(caminho, modo)
        self.addCleanup(os.remove, caminho)
        return caminho


class TestCarregaPerfisAcesso(_BaseArquivo, unittest.TestCase):
    """Formato e validacoes do arquivo de acesso."""

    def test_perfis_na_ordem_do_arquivo(self):
        perfis = acesso.carrega_perfis_acesso(self._arquivo(EXEMPLO))
        self.assertEqual([p.nome for p in perfis], ["operador", "root"])
        self.assertEqual([p.usuario for p in perfis], ["f4683594", "root"])

    def test_senha_e_literal_com_hash_ponto_e_virgula_e_percent(self):
        """Senhas geradas contem esses caracteres; nada pode ser cortado
        como comentario nem interpolado."""
        perfis = acesso.carrega_perfis_acesso(self._arquivo(EXEMPLO))
        self.assertEqual(perfis[0].senha, "s3nh#a;com%tudo")
        self.assertEqual(perfis[1].senha, "Temp#2026;X")

    def test_senha_sudo_vazia_tenta_propria_e_depois_root(self):
        """Tres casos do sudo: a tentativa sem senha e feita antes, em
        ssh_utils.detecta_sudo; aqui ficam a do proprio usuario (padrao do
        sudo) e a do root (padrao SUSE, targetpw), nessa ordem."""
        perfis = acesso.carrega_perfis_acesso(self._arquivo(EXEMPLO))
        self.assertEqual(perfis[0].senhas_sudo,
                         ("s3nh#a;com%tudo", "Temp#2026;X"))

    def test_perfil_root_nao_repete_a_propria_senha(self):
        perfis = acesso.carrega_perfis_acesso(self._arquivo(EXEMPLO))
        self.assertEqual(perfis[1].senhas_sudo, ("Temp#2026;X",))

    def test_senha_sudo_preenchida_e_a_unica_tentada(self):
        conteudo = EXEMPLO.replace("senha_sudo =\n", "senha_sudo = outra\n")
        perfis = acesso.carrega_perfis_acesso(self._arquivo(conteudo))
        self.assertEqual(perfis[0].senhas_sudo, ("outra",))

    @unittest.skipUnless(os.name == "posix", "permissao so existe em POSIX")
    def test_permissao_aberta_e_recusada(self):
        caminho = self._arquivo(EXEMPLO, modo=0o644)
        with self.assertRaises(acesso.ArquivoAcessoInvalido) as ctx:
            acesso.carrega_perfis_acesso(caminho)
        self.assertIn("chmod 600", str(ctx.exception))

    def test_chave_desconhecida_e_recusada(self):
        """Erro de digitacao nao pode virar perfil sem senha em silencio."""
        conteudo = EXEMPLO.replace("senha = Temp", "sneha = Temp")
        with self.assertRaises(acesso.ArquivoAcessoInvalido) as ctx:
            acesso.carrega_perfis_acesso(self._arquivo(conteudo))
        self.assertIn("sneha", str(ctx.exception))

    def test_usuario_ausente_e_recusado(self):
        conteudo = "[x]\nsenha = a\n"
        with self.assertRaises(acesso.ArquivoAcessoInvalido):
            acesso.carrega_perfis_acesso(self._arquivo(conteudo))

    def test_arquivo_sem_perfil_e_recusado(self):
        with self.assertRaises(acesso.ArquivoAcessoInvalido):
            acesso.carrega_perfis_acesso(self._arquivo("# vazio\n"))

    def test_arquivo_ausente_e_recusado(self):
        with self.assertRaises(acesso.ArquivoAcessoInvalido):
            acesso.carrega_perfis_acesso("/nao/existe/acesso.conf")

    def test_exemplo_distribuido_carrega(self):
        """O acesso.conf.example do pacote precisa ser um arquivo valido."""
        with open(os.path.join(BASE, "acesso.conf.example"),
                  encoding="utf-8") as f:
            perfis = acesso.carrega_perfis_acesso(self._arquivo(f.read()))
        self.assertEqual([(p.nome, p.usuario) for p in perfis],
                         [("operador", "SEU_USUARIO"), ("root", "root")])

    def test_perfil_duplicado_e_recusado(self):
        conteudo = EXEMPLO + "[root]\nusuario = root\n"
        with self.assertRaises(acesso.ArquivoAcessoInvalido):
            acesso.carrega_perfis_acesso(self._arquivo(conteudo))


class TestPerfilDaLinhaDeComando(unittest.TestCase):
    """Sem --acesso, o comportamento anterior a v2.3.0 fica intacto."""

    def _args(self, sudo_pass=""):
        return types.SimpleNamespace(
            ssh_user="testmec3", ssh_pass_efetiva="senha-ssh",
            sudo_pass=sudo_pass)

    def test_sudo_sem_sudo_pass_nao_tenta_a_senha_ssh(self):
        """Antes da v2.3.0 a senha SSH nunca era tentada no sudo."""
        perfil = acesso.perfil_da_linha_de_comando(self._args())[0]
        self.assertEqual(perfil.senhas_sudo, ())
        self.assertEqual(perfil.usuario, "testmec3")
        self.assertEqual(perfil.senha, "senha-ssh")

    def test_sudo_pass_e_a_unica_senha_do_sudo(self):
        perfil = acesso.perfil_da_linha_de_comando(self._args("x"))[0]
        self.assertEqual(perfil.senhas_sudo, ("x",))


class TestDescrevePerfis(_BaseArquivo, unittest.TestCase):
    """O cabecalho do log nunca pode trazer senha."""

    def test_descricao_sem_senhas(self):
        perfis = acesso.carrega_perfis_acesso(self._arquivo(EXEMPLO))
        texto = acesso.descreve_perfis(perfis)
        self.assertEqual(texto, "operador (f4683594), root (root)")
        self.assertNotIn("Temp", texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
