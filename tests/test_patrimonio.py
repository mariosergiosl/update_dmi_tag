# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_patrimonio.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_patrimonio -v)
#
# DESCRIPTION: Funcoes puras de patrimonio: digito verificador Modulo 11,
#              validacao/calculo de tag e leitura do CLI patrimonial.
#              Roda em qualquer maquina, sem SSH real: tudo que toca
#              rede e mockado via unittest.mock. Nenhuma dependencia
#              alem da stdlib.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.3
# REVISION: 2026-09-28 - v2.3.3 - DV divergente passa a levantar ValueError
#                        (test_14_digitos_dv_divergente_e_recusado_v233), no
#                        lugar do teste que exigia a aceitacao com aviso.
# REVISION: 2026-09-28 - v2.3.2 - TestFormataBemV232.
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

from update_dmi_tag.patrimonio import calcula_dv_modulo11  # noqa: E402
from update_dmi_tag.patrimonio import valida_e_calcula_tag  # noqa: E402
from update_dmi_tag.patrimonio import valida_via_patrimonial_cli  # noqa: E402
from update_dmi_tag.patrimonio import formata_bem  # noqa: E402

class TestDVModulo11(unittest.TestCase):
    """Vetores confirmados contra o CLI oficial python3-patrimonial
    (2026-07-17, host real)."""

    VETORES = [
        ("7417161830398", "6"),
        ("7417191234567", "4"),
        ("7417191154401", "0"),
        ("7417191231111", "7"),
        ("7417161839999", "1"),
        ("7417161830009", "X"),   # DV=10 vira X (bug corrigido na v2.2.7)
        ("7417191152222", "X"),   # segundo caso real confirmado
    ]

    def test_vetores_confirmados(self):
        """DV de cada base deve bater com o CLI oficial."""
        for base, dv in self.VETORES:
            self.assertEqual(calcula_dv_modulo11(base), dv, base)


class TestValidaECalculaTag(unittest.TestCase):
    """Validacao de formato e calculo da tag final de 14 posicoes."""

    def _chama(self, valor):
        return valida_e_calcula_tag(valor, "", False, True)

    def test_13_digitos_calcula_dv(self):
        """Base de 13 digitos deve ganhar o DV calculado."""
        tag, base = self._chama("7417161830398")
        self.assertEqual(tag, "74171618303986")
        self.assertEqual(base, "7417161830398")

    def test_13_digitos_dv_x(self):
        """Base cujo DV e 10 deve fechar com X."""
        tag, _ = self._chama("7417161830009")
        self.assertEqual(tag, "7417161830009X")

    def test_14_digitos_dv_correto(self):
        """Valor de 14 digitos com DV correto passa sem alteracao."""
        tag, _ = self._chama("74171618303986")
        self.assertEqual(tag, "74171618303986")

    def test_14_digitos_x_maiusculo(self):
        """DV X maiusculo e aceito e preservado."""
        tag, _ = self._chama("7417161830009X")
        self.assertEqual(tag, "7417161830009X")

    def test_14_digitos_x_minusculo_preserva_maiusculo(self):
        """DV x minusculo e aceito e normalizado para maiusculo."""
        tag, _ = self._chama("7417161830009x")
        self.assertEqual(tag, "7417161830009X")

    def test_14_digitos_dv_divergente_e_recusado_v233(self):
        """v2.3.3: DV divergente do calculado levanta ValueError (INVALIDO).

        Ate a v2.3.2 era aceito com aviso. A biblioteca oficial
        (libpatrimonial) descarta esse numero e trata a BIOS como sem
        numero; o operador corrige o valor e roda de novo. Casos reais:
        digito numerico errado e X no lugar de digito."""
        for ruim in ("74171618303989", "7417183822329X", "7417131861156x",
                     "77171830251196"):
            with self.assertRaises(ValueError, msg=ruim):
                self._chama(ruim)

    def test_14_digitos_dv_correto_continua_aceito_v233(self):
        """Regressao: DV correto, numerico ou X, segue aceito."""
        for bom in ("74171618303986", "7417161830009X", "7417161830009x"):
            tag, _ = self._chama(bom)
            self.assertEqual(tag, bom.upper())

    def test_invalidos_levantam_valueerror(self):
        """Formatos invalidos devem levantar ValueError."""
        for ruim in ("123", "12345678901", "123456789012345",
                     "74171618303X86", "ABCDEFGHIJKLM", ""):
            with self.assertRaises(ValueError, msg=ruim):
                self._chama(ruim)


class TestValidaViaPatrimonialCli(unittest.TestCase):
    """Validacao redundante via CLI patrimonial, com subprocess mockado.
    Cobre as correcoes da v2.2.8: --verbose obrigatorio e preservacao
    do X final no parse."""

    def _mock_run(self, stdout, returncode=0):
        r = mock.Mock()
        r.returncode = returncode
        r.stdout = stdout
        r.stderr = ""
        return r

    def test_inclui_verbose_no_comando(self):
        """Sem --verbose o CLI nao imprime nada; a flag e obrigatoria."""
        with mock.patch("update_dmi_tag.patrimonio.subprocess.run") as m:
            m.return_value = self._mock_run("74171618303986\tNumero valido")
            valida_via_patrimonial_cli("7417161830398", "", False, True)
            args_cmd = m.call_args[0][0]
            self.assertIn("--verbose", args_cmd)
            self.assertIn("--non-strict", args_cmd)

    def test_saida_normal(self):
        """Saida com numero + texto retorna so o numero de 14 posicoes."""
        with mock.patch("update_dmi_tag.patrimonio.subprocess.run") as m:
            m.return_value = self._mock_run("74171618303986\tNumero valido")
            self.assertEqual(
                valida_via_patrimonial_cli("7417161830398", "", False, True),
                "74171618303986")

    def test_saida_com_x(self):
        """O X final (DV=10) deve ser preservado, nao filtrado."""
        with mock.patch("update_dmi_tag.patrimonio.subprocess.run") as m:
            m.return_value = self._mock_run("7417161830009X\tNumero valido")
            self.assertEqual(
                valida_via_patrimonial_cli("7417161830009", "", False, True),
                "7417161830009X")

    def test_saida_vazia_retorna_vazio(self):
        """Saida vazia (CLI sem --verbose, por ex.) retorna vazio."""
        with mock.patch("update_dmi_tag.patrimonio.subprocess.run") as m:
            m.return_value = self._mock_run("")
            self.assertEqual(
                valida_via_patrimonial_cli("7417161830398", "", False, True),
                "")

    def test_saida_invalida_retorna_vazio(self):
        """Saida que nao e um numero de 14 posicoes retorna vazio."""
        with mock.patch("update_dmi_tag.patrimonio.subprocess.run") as m:
            m.return_value = self._mock_run("Numero invalido")
            self.assertEqual(
                valida_via_patrimonial_cli("7417161830398", "", False, True),
                "")

    def test_rc_diferente_de_zero_retorna_vazio(self):
        """returncode != 0 retorna vazio mesmo com stdout plausivel."""
        with mock.patch("update_dmi_tag.patrimonio.subprocess.run") as m:
            m.return_value = self._mock_run("74171618303986", returncode=1)
            self.assertEqual(
                valida_via_patrimonial_cli("7417161830398", "", False, True),
                "")

    def test_cli_ausente_retorna_vazio(self):
        """CLI fora do PATH (FileNotFoundError) retorna vazio."""
        with mock.patch("update_dmi_tag.patrimonio.subprocess.run",
                        side_effect=FileNotFoundError):
            self.assertEqual(
                valida_via_patrimonial_cli("7417161830398", "", False, True),
                "")

class TestFormataBemV232(unittest.TestCase):
    """v2.3.2: formato por destino (--bios-digitos, --bbconfig-digitos)."""

    def test_14_devolve_a_tag_inteira(self):
        self.assertEqual(formata_bem("74171618303986", 14), "74171618303986")

    def test_13_tira_o_dv(self):
        self.assertEqual(formata_bem("74171618303986", 13), "7417161830398")

    def test_13_tira_o_dv_x(self):
        self.assertEqual(formata_bem("7417161830009X", 13), "7417161830009")

    def test_padrao_e_14(self):
        self.assertEqual(formata_bem("74171618303986"), "74171618303986")

    def test_valor_invalido_recusado(self):
        with self.assertRaises(ValueError):
            formata_bem("74171618303986", 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
