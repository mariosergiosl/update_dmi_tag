# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_summary.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_summary -v)
#
# DESCRIPTION: Resumo agregado da execucao: contagem de status e do
#              bloco de Teste de Escrita.
#              Roda em qualquer maquina, sem SSH real: tudo que toca
#              rede e mockado via unittest.mock. Nenhuma dependencia
#              alem da stdlib.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.0
# REVISION: 2026-09-23 - v2.3.0 - test_coluna_acesso_no_fim_da_tabela.
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

from update_dmi_tag import summary as summary_mod  # noqa: E402

def _registro(ip, resultado, tag_antes="Not Specified", tag_depois="N/D"):
    """Monta um registro sintetico no formato de processa_host_remoto."""
    return {
        "ip": ip, "hostname": "h-" + ip, "board_vendor": "Dell Inc.",
        "board_name": "X", "bios_vendor": "Dell", "bios_version": "1.0",
        "smbios": "3.2", "wsmt": "Present", "tag_antes": tag_antes,
        "bem_conf": "PENDENTE", "bem_usado": "74171618303986",
        "tag_depois": tag_depois, "mecanismo": "N/D",
        "resultado": resultado, "bbconfig_sync": "N/A",
        "bbconfig_backup": "", "mac": "aa:bb", "teste_escrita": "N/A",
    }


class TestSummary(unittest.TestCase):
    """Resumo agregado (summary.py), incluindo o bucket OK-ja-correto."""

    def _roda(self, registros):
        with tempfile.NamedTemporaryFile("w", suffix=".log",
                                         delete=False) as f:
            caminho = f.name
        try:
            summary_mod.monta_tabela_resumo(
                registros, caminho, False, True, write_ativo=True)
            with open(caminho, encoding="utf-8", errors="replace") as f:
                return f.read()
        finally:
            os.remove(caminho)

    def test_ok_ja_correto_contabilizado(self):
        """OK-ja-correto deve aparecer no sumario com contagem propria."""
        registros = [
            _registro("10.0.0.1", "OK-amidelnx", tag_depois="74171618303986"),
            _registro("10.0.0.2", "OK-ja-correto",
                      tag_antes="74171618303986",
                      tag_depois="74171618303986"),
            _registro("10.0.0.3", "FALHOU-todos"),
            _registro("10.0.0.4", "INACESSIVEL"),
        ]
        saida = self._roda(registros)
        self.assertIn("Ja correto (OK-ja-correto) :   1", saida)
        self.assertIn("Total processado", saida)

    def test_descricao_ok_ja_correto_existe(self):
        """A descricao humanizada do OK-ja-correto deve existir."""
        desc = summary_mod._descricao_resultado("OK-ja-correto")
        self.assertIn("nenhum mecanismo executado", desc)

    def test_te_testado_contabiliza_incompativel_e_bloqueado(self):
        """Bug real (2026-07-20): te_testado nao contava
        INCOMPATIVEL-HW nem BLOQUEADO-* vindos de teste_escrita
        (tenta_teste_escrita_remoto pode retornar ambos), subestimando
        o 'Total testado'. Confirma que os 2 hosts abaixo entram na
        conta (4 no total, nao 2)."""
        registros = []
        for ip, te in [
            ("10.0.1.1", "OK-amidelnx"),
            ("10.0.1.2", "FALHOU-todos"),
            ("10.0.1.3", "INCOMPATIVEL-HW"),
            ("10.0.1.4", "BLOQUEADO-KMP-kernel-incompativel"),
        ]:
            r = _registro(ip, "DRY-RUN")
            r["teste_escrita"] = te
            registros.append(r)
        saida = self._roda(registros)
        self.assertIn("Incompativel (INCOMPATIVEL-HW):   1", saida)
        self.assertIn("Bloqueado (BLOQUEADO-*)    :   1", saida)
        self.assertIn("Total testado              :   4", saida)

    def test_coluna_acesso_no_fim_da_tabela(self):
        """v2.3.0: perfil usado em cada host, na ultima coluna, para nao
        deslocar as posicoes lidas pelos scripts de analise; registro sem
        o campo (versao anterior) sai como N/D."""
        com = _registro("10.0.2.1", "OK-amibios")
        com["acesso"] = "root"
        sem = _registro("10.0.2.2", "OK-amidelnx")
        saida = self._roda([com, sem])
        linhas = [l for l in saida.splitlines() if l.startswith("| ")]
        cabecalho = [c.strip() for c in linhas[0].strip("|").split("|")]
        self.assertEqual(cabecalho[-1], "Acesso")
        self.assertEqual(cabecalho[-2], "MAC")
        valores = {l.split("|")[1].strip(): l.split("|")[-2].strip()
                   for l in linhas[1:3]}
        self.assertEqual(valores["10.0.2.1"], "root")
        self.assertEqual(valores["10.0.2.2"], "N/D")

if __name__ == "__main__":
    unittest.main(verbosity=2)
