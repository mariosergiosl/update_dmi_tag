# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_write_cascade.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_write_cascade -v)
#
# DESCRIPTION: Cascata de mecanismos de escrita: escalonamento entre
#              Mecanismos 1, 2 e 3, travas de seguranca e avisos.
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
import types
import unittest
from unittest import mock

# Raiz do repositorio (pai da pasta tests/), para importar o pacote sem
# depender de instalacao nem do diretorio corrente do chamador.
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

from update_dmi_tag import write_cascade as wc  # noqa: E402

class TestCascataUnidade(unittest.TestCase):
    """Retornos da cascata de escrita com os mecanismos mockados."""

    def _args(self, write=True, allow_efi=False):
        ns = types.SimpleNamespace()
        ns.write = write
        ns.verbose = False
        ns.csv = False
        ns.amide_remote_path = "~/amidelnx_64"
        ns.amide_local_path = "amidelnx_64"
        ns.amide_repo_url = ""
        ns.amide_package = ""
        ns.target = "/sys/firmware/amibios/chassis/asset_tag"
        ns.module_repo_url = ""
        ns.module_package = "amibios-dmi"
        ns.module_rpm_dir = "./rpm"
        ns.allow_efi_fallback = allow_efi
        ns.log_efi = ""
        return ns

    def _roda(self, m1, m2, args):
        with mock.patch.object(wc, "executa_amidelnx_remoto",
                               side_effect=[m1]), \
             mock.patch.object(wc, "executa_amibios_remoto",
                               side_effect=[m2]), \
             mock.patch.object(wc, "gravar_log_remoto"):
            return wc.tenta_escrever_tag_remoto(
                "192.0.2.1", "u", "sudo", "74171618303986", args, "", "")

    def test_mecanismo1_sucesso_para_cascata(self):
        """Sucesso no Mecanismo 1 encerra a cascata (trava v2.2)."""
        r = self._roda((True, ""), (True, ""), self._args())
        self.assertEqual(r, "OK-amidelnx")

    def test_mecanismo1_falha_mecanismo2_sucesso(self):
        """Falha no 1 cai para o 2; sucesso no 2 encerra."""
        r = self._roda((False, "erro generico"), (True, ""), self._args())
        self.assertEqual(r, "OK-amibios")

    def test_ambos_falham_generico(self):
        """Falha generica nos dois, sem EFI: FALHOU-todos."""
        r = self._roda((False, "timeout"), (False, "rede"), self._args())
        self.assertEqual(r, "FALHOU-todos")

    def test_ambos_incompativeis_sem_efi(self):
        """Assinatura de firmware nos dois, sem EFI: INCOMPATIVEL-HW."""
        r = self._roda(
            (False, "24 - Error: Problem allocating BIOS buffer."),
            (False, "Error: Fail to initialize SMBIOS."),
            self._args())
        self.assertEqual(r, "INCOMPATIVEL-HW")

    def test_dry_run_retorna_dry_run(self):
        """Sem --write a cascata retorna DRY-RUN apos o Mecanismo 1."""
        r = self._roda((True, ""), (True, ""), self._args(write=False))
        self.assertEqual(r, "DRY-RUN")

    def test_kmp_incompativel_kernel_nao_escala_para_efi(self):
        """Trava v2.2.8: falta de KMP para o kernel do host (marcador de
        environment.instala_modulo_remoto) bloqueia o Mecanismo 3 mesmo
        com --allow-efi-fallback ativo (nao e incompatibilidade de
        hardware, so falta o RPM certo, ver rpm/README.md)."""
        r = self._roda(
            (False, "generico, amidelnx indisponivel"),
            (False, "KMP-KERNEL-MISMATCH: host roda o kernel "
                    "'6.4.0-150600.21-default', mas nenhum RPM compativel."),
            self._args(allow_efi=True))
        self.assertEqual(r, "BLOQUEADO-KMP-kernel-incompativel")

    def test_kmp_incompativel_kernel_sem_efi_fallback(self):
        """Mesma trava sem --allow-efi-fallback: resultado identico (a
        trava independe da flag)."""
        r = self._roda(
            (False, "generico"),
            (False, "KMP-KERNEL-MISMATCH: nenhum RPM compativel."),
            self._args(allow_efi=False))
        self.assertEqual(r, "BLOQUEADO-KMP-kernel-incompativel")

class TestAvisoAllowEfiFallback(unittest.TestCase):
    """Regressao para o bug real da v2.2.8 (revisao 2026-07-20): o aviso
    interativo de --allow-efi-fallback ainda citava 'Mecanismo 4', apesar
    da renumeracao para 'Mecanismo 3' na v2.1.14. Guarda de texto, nao de
    comportamento: le o fonte de __main__.py e confere a string exibida
    ao operador antes da confirmacao de reboot fisico."""

    def test_aviso_cita_mecanismo_3_nao_4(self):
        caminho = os.path.join(BASE, "update_dmi_tag", "__main__.py")
        with open(caminho, encoding="utf-8") as f:
            fonte = f.read()
        linha_correta = (
            '"3 (os 2 mecanismos diretos, amidelnx_64 e amibios_dmi, '
            'ja tiverem "')
        linha_com_bug = (
            '"4 (os 2 mecanismos diretos, amidelnx_64 e amibios_dmi, '
            'ja tiverem "')
        self.assertIn(linha_correta, fonte)
        self.assertNotIn(linha_com_bug, fonte)

if __name__ == "__main__":
    unittest.main(verbosity=2)
