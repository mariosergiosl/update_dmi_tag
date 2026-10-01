# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_packaging.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_packaging -v)
#
# DESCRIPTION: Conferencia estatica do update_dmi_tag.spec, o arquivo de
#              empacotamento RPM usado no OBS. Le o spec como texto;
#              nao depende de rpmbuild nem de rede.
#
#              Defeito que originou o arquivo (2026-10-01): no OBS, o
#              build para SLE 16 falhou na secao prep com
#              "/usr/bin/gzip: No such file or directory", porque o
#              ambiente minimo de build do SLE 16 nao traz o gzip e o
#              spec nao o pedia em BuildRequires.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.3
# CREATED: 2026-10-01
# REVISION: ---
#
# =======================================================================

import os
import re
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from update_dmi_tag.constants import SCRIPT_VERSION  # noqa: E402

SPEC = os.path.join(RAIZ, "update_dmi_tag.spec")


def le_spec():
    """Return the spec file content with normalized line endings."""
    with open(SPEC, "rb") as fh:
        return fh.read().decode("ascii").replace("\r\n", "\n")


def campo(texto, nome):
    """Return the values of a spec tag (e.g. Requires), in file order."""
    return re.findall(r"^%s:\s*(\S+)\s*$" % nome, texto, re.M)


def secao(texto, nome):
    """Return the body of a spec section (e.g. install) up to the next one."""
    m = re.search(r"^%%%s\s*$(.*?)(?=^%%(prep|build|install|post|files|changelog)\b)"
                  % nome, texto, re.M | re.S)
    return m.group(1) if m else ""


class Dependencias(unittest.TestCase):
    """Dependencias de build e de execucao."""

    def test_gzip_em_buildrequires(self):
        """Defeito 2026-10-01: sem gzip, a secao prep falha no SLE 16."""
        self.assertIn("gzip", campo(le_spec(), "BuildRequires"))

    def test_buildrequires_python3_mantido(self):
        """Perda: a dependencia de build anterior continua."""
        self.assertIn("python3", campo(le_spec(), "BuildRequires"))

    def test_requires_de_execucao_mantidos(self):
        """Regressao: python3 e openssh continuam como dependencias."""
        requires = campo(le_spec(), "Requires")
        self.assertIn("python3", requires)
        self.assertIn("openssh", requires)

    def test_noarch(self):
        """Regressao: pacote continua noarch (Python puro)."""
        self.assertEqual(campo(le_spec(), "BuildArch"), ["noarch"])


class VersaoEChangelog(unittest.TestCase):
    """Coerencia entre spec, codigo e changelog."""

    def test_version_igual_ao_codigo(self):
        """Colisao: Version do spec e SCRIPT_VERSION do codigo nao divergem."""
        self.assertEqual(campo(le_spec(), "Version"), [SCRIPT_VERSION])

    def test_source0_segue_nome_da_tarball(self):
        """Regressao: o OBS recebe a tarball com este nome."""
        self.assertEqual(campo(le_spec(), "Source0"), ["%{name}-%{version}.tar.gz"])

    def test_primeira_entrada_do_changelog_bate_com_version_release(self):
        """Colisao: a entrada mais recente do changelog e a da versao atual."""
        texto = le_spec()
        esperado = "%s-%s" % (campo(texto, "Version")[0], campo(texto, "Release")[0])
        primeira = re.search(r"^\* .* - (\S+)\s*$", texto.split("\n%changelog\n", 1)[1], re.M)
        self.assertIsNotNone(primeira)
        self.assertEqual(primeira.group(1), esperado)


class ArquivosDoInstall(unittest.TestCase):
    """Tudo que a secao install copia precisa existir no repositorio."""

    def test_origens_do_install_existem(self):
        """Perda: nenhum arquivo copiado pelo install sumiu do repositorio."""
        corpo = secao(le_spec(), "install")
        self.assertTrue(corpo)
        origens = []
        for linha in corpo.replace("\\\n", " ").split("\n"):
            partes = linha.split()
            if partes[:2] == ["cp", "-a"]:
                origens += [p for p in partes[2:-1]]
            elif partes[:1] == ["install"] and "-Dm755" in partes:
                origens.append(partes[-2])
        self.assertIn("packaging/update_dmi_tag-wrapper.sh", origens)
        self.assertIn("update_dmi_tag.py", origens)
        faltando = [o for o in origens if not os.path.exists(os.path.join(RAIZ, o))]
        self.assertEqual(faltando, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
