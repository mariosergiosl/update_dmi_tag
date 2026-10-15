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
from update_dmi_tag.hosts import grava_inacessiveis_por_motivo  # noqa: E402

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


class TestInacessiveisPorMotivoV236(unittest.TestCase):
    """v2.3.6: listas de inacessiveis por motivo, com triagem e Fase 2,
    no formato do --hosts e com nome derivado do log."""

    HOSTS = [("10.0.0.1", "74171"), ("10.0.0.2", "74172"),
             ("10.0.0.3", ""), ("10.0.0.4", "74174"), ("10.0.0.5", "74175")]

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.log = os.path.join(self.dir, "20261015_f4683594-x_v2.3.6_onda2.log")

    def tearDown(self):
        for nome in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, nome))
        os.rmdir(self.dir)

    def _reg(self, ip, resultado, motivo=""):
        return {"ip": ip, "resultado": resultado, "motivo_inacessivel": motivo}

    def _le(self, sufixo):
        with open(os.path.join(self.dir, "20261015_f4683594-x_v2.3.6_onda2"
                               + sufixo), encoding="utf-8") as f:
            return f.read()

    def test_separa_rede_e_acesso_com_fase2(self):
        """Defeito 2026-10-14: o arquivo da triagem nao tinha a Fase 2."""
        registros = [self._reg("10.0.0.4", "INACESSIVEL", "acesso"),  # Fase 2
                     self._reg("10.0.0.1", "INACESSIVEL", "rede"),
                     self._reg("10.0.0.2", "OK-amibios"),
                     self._reg("10.0.0.3", "INACESSIVEL", "rede"),
                     self._reg("10.0.0.5", "INVALIDO")]
        gravados = grava_inacessiveis_por_motivo(registros, self.HOSTS, self.log)
        self.assertEqual(self._le("_inacessiveis_rede.txt"),
                         "10.0.0.1,74171\n10.0.0.3\n")
        self.assertEqual(self._le("_inacessiveis_acesso.txt"), "10.0.0.4,74174\n")
        self.assertEqual([(m, q) for m, _, q in gravados], [("rede", 2), ("acesso", 1)])

    def test_saida_e_aceita_pelo_le_arquivo_hosts(self):
        """Colisao: o arquivo gravado volta pelo --hosts sem edicao."""
        grava_inacessiveis_por_motivo(
            [self._reg("10.0.0.1", "INACESSIVEL", "rede"),
             self._reg("10.0.0.3", "INACESSIVEL", "rede")], self.HOSTS, self.log)
        caminho = os.path.join(self.dir, "20261015_f4683594-x_v2.3.6_onda2"
                               "_inacessiveis_rede.txt")
        self.assertEqual(le_arquivo_hosts(caminho),
                         [("10.0.0.1", "74171"), ("10.0.0.3", "")])

    def test_motivo_vazio_vai_para_indeterminado(self):
        """Nao adivinha: INACESSIVEL sem motivo nao entra em rede nem acesso."""
        gravados = grava_inacessiveis_por_motivo(
            [self._reg("10.0.0.2", "INACESSIVEL")], self.HOSTS, self.log)
        self.assertEqual([m for m, _, _ in gravados], ["indeterminado"])
        self.assertEqual(self._le("_inacessiveis_indeterminado.txt"), "10.0.0.2,74172\n")

    def test_sem_inacessivel_nao_cria_arquivo(self):
        gravados = grava_inacessiveis_por_motivo(
            [self._reg("10.0.0.1", "OK-amibios")], self.HOSTS, self.log)
        self.assertEqual(gravados, [])
        self.assertEqual(os.listdir(self.dir), [])

    def test_ordem_da_lista_e_sem_repeticao(self):
        """IP repetido na lista ou nos registros sai uma vez, na ordem da lista."""
        hosts = self.HOSTS + [("10.0.0.1", "74171")]
        grava_inacessiveis_por_motivo(
            [self._reg("10.0.0.3", "INACESSIVEL", "rede"),
             self._reg("10.0.0.1", "INACESSIVEL", "rede")], hosts, self.log)
        self.assertEqual(self._le("_inacessiveis_rede.txt"),
                         "10.0.0.1,74171\n10.0.0.3\n")

if __name__ == "__main__":
    unittest.main(verbosity=2)
