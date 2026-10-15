# -*- coding: utf-8 -*-
"""Testes dos geradores de diagrama do manual (tools/diagramas).

Rodar da raiz do repositorio: python -m unittest -v tests.test_diagramas

Catalogo (defeito ou risco que motivou cada caso):
  D1 os geradores ficaram so no scratchpad de uma sessao em 07/2026 e se
     perderam; cada um tem de rodar a partir do repositorio e gravar o SVG
     na pasta pedida (DIAGRAMAS_SAIDA)
  D2 os diagramas 01, 02, 05, 06 e 07 ficaram parados na linha 2.2 (sem
     perfis de acesso, sem acesso.py, sem as listas por motivo da 2.3.6)
  D3 gera_diagramas.py nao sobrescreve PNG existente sem -f
"""
import glob
import os
import subprocess
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAG = os.path.join(BASE, "tools", "diagramas")
sys.path.insert(0, DIAG)

try:
    import svglib  # noqa: F401
    import reportlab  # noqa: F401
    import fitz  # noqa: F401
    TEM_CONVERSAO = True
except ImportError:
    TEM_CONVERSAO = False


def _gera_svg(numero, saida):
    """Run generator dNN and return the SVG text."""
    script = glob.glob(os.path.join(DIAG, "d%s_*.py" % numero))[0]
    env = dict(os.environ, DIAGRAMAS_SAIDA=saida)
    subprocess.run([sys.executable, script], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    nome = os.path.basename(script)[1:-3]
    with open(os.path.join(saida, nome + ".svg"), encoding="utf-8") as f:
        return f.read()


class TestGeradores(unittest.TestCase):
    """D1 e D2: cada gerador roda do repositorio, com o conteudo atual."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.svg = {n: _gera_svg(n, cls.tmp)
                   for n in ("01", "02", "03", "04", "05", "06", "07", "08")}

    def test_d1_todos_geram_svg(self):
        for n, texto in self.svg.items():
            self.assertTrue(texto.startswith("<svg"), n)

    def test_d2_01_perfis_e_listas(self):
        self.assertIn("--acesso", self.svg["01"])
        self.assertIn("_inacessiveis_rede.txt", self.svg["01"])

    def test_d2_02_sudo_por_perfil_e_listas(self):
        self.assertIn("_detecta_sudo_perfil", self.svg["02"])
        self.assertIn("grava_inacessiveis_por_motivo", self.svg["02"])

    def test_d2_05_tem_acesso_py(self):
        self.assertIn("acesso.py", self.svg["05"])

    def test_d2_06_listas(self):
        self.assertIn("_inacessiveis_acesso.txt", self.svg["06"])

    def test_d2_07_inacessivel_por_motivo(self):
        self.assertIn("rede: porta 22 sem resposta", self.svg["07"])
        self.assertIn("acesso: sem chave e sem senha", self.svg["07"])

    def test_regressao_03_04_08_inalterados(self):
        """Os que nao mudaram continuam com o conteudo de sempre."""
        self.assertIn("Cascata de Mecanismos de Escrita", self.svg["03"])
        self.assertIn("Mecanismo 3", self.svg["04"])
        self.assertIn("Topologia de Rede", self.svg["08"])


@unittest.skipUnless(TEM_CONVERSAO, "svglib/reportlab/pymupdf ausentes")
class TestGeraPng(unittest.TestCase):
    """D3: conversao para PNG e protecao contra sobrescrita."""

    def test_d3_nao_sobrescreve_sem_f(self):
        import gera_diagramas as g
        tmp = tempfile.mkdtemp()
        png = g.gera("08", tmp, False)
        self.assertTrue(os.path.getsize(png) > 1000)
        with self.assertRaises(SystemExit):
            g.gera("08", tmp, False)
        self.assertEqual(g.gera("08", tmp, True), png)


if __name__ == "__main__":
    unittest.main(verbosity=2)
