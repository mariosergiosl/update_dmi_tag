# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_regressao.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou: python3 -m pytest tests/ -v)
#
# DESCRIPTION: Suite de regressao do update_dmi_tag. Roda em qualquer
#              maquina, sem SSH real: tudo que toca rede e mockado via
#              unittest.mock. Cobre as funcoes puras (Modulo 11,
#              validacao de tag, parse de hosts, assinaturas de
#              incompatibilidade de firmware), o resumo agregado, a
#              trava global OK-ja-correto (integracao de
#              processa_host_remoto com mocks) e os retornos da cascata
#              de escrita. Nenhuma dependencia alem da stdlib.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE
# VERSION: 2.2.8
# CREATED: 2026-07-18
# REVISION: ---
#
# =======================================================================

import os
import sys
import tempfile
import types
import unittest
from unittest import mock

# Raiz do repositorio (pai da pasta tests/), para importar o pacote sem
# depender de instalacao nem do diretorio corrente do chamador.
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

from update_dmi_tag.patrimonio import (  # noqa: E402
    calcula_dv_modulo11, valida_e_calcula_tag, valida_via_patrimonial_cli,
)
from update_dmi_tag.hosts import le_arquivo_hosts  # noqa: E402
from update_dmi_tag.constants import eh_incompatibilidade_firmware  # noqa: E402
from update_dmi_tag import summary as summary_mod  # noqa: E402
from update_dmi_tag import host_processor as hp  # noqa: E402
from update_dmi_tag import write_cascade as wc  # noqa: E402


class TestDVModulo11(unittest.TestCase):
    """Vetores confirmados contra o CLI oficial python3-patrimonial
    (2026-07-17, host de producao)."""

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

    def test_14_digitos_dv_divergente_aceita_com_warning(self):
        """Padrao BB: DV divergente do calculado e aceito (so avisa)."""
        tag, _ = self._chama("74171618303989")
        self.assertEqual(tag, "74171618303989")

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


class TestIncompatibilidadeFirmware(unittest.TestCase):
    """Assinaturas de incompatibilidade de firmware (constants.py)."""

    def test_assinaturas_positivas(self):
        """Assinaturas reais de campo devem ser reconhecidas."""
        positivos = [
            "24 - Error: Problem allocating BIOS buffer.",
            "Error: Fail to initialize SMBIOS.",
            "d7 - Error: DMI Data write failed.",
            "sysfs rejeitou a escrita sem mensagem (rc=0)",
        ]
        for p in positivos:
            self.assertTrue(eh_incompatibilidade_firmware(p), p)

    def test_negativos(self):
        """Falhas genericas/transitorias nao devem ser confundidas."""
        negativos = ["", "Connection refused", "Permission denied",
                     "Done", "timeout"]
        for n in negativos:
            self.assertFalse(eh_incompatibilidade_firmware(n), n)


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


class TestTravaGlobalIntegracao(unittest.TestCase):
    """Integracao com mocks: processa_host_remoto de ponta a ponta,
    provando que a trava global (v2.2.8) NAO chama a cascata quando a
    tag ja esta correta, e CHAMA quando esta diferente."""

    def _args(self, write=True, test_write=False):
        ns = types.SimpleNamespace()
        ns.log_file = ""
        ns.ssh_user = "testmec3"
        ns.sudo_pass = ""
        ns.verbose = False
        ns.csv = False
        ns.write = write
        ns.test_write = test_write
        ns.production = False
        ns.config = "/etc/BBconfig.conf"
        ns.var = "BEM_NUMERO"
        ns.module_package = "amibios-dmi"
        ns.ssh_pass_efetiva = ""
        return ns

    def _roda(self, tag_na_bios, bem_lista, args):
        chamadas = {"cascata": 0}

        def fake_cascata(*a, **k):
            chamadas["cascata"] += 1
            return "OK-amidelnx"

        ambiente = {
            "hostname": "vm-teste", "board_vendor": "X", "board_name": "Y",
            "bios_vendor": "Z", "bios_version": "1", "smbios_version": "3.2",
            "wsmt": "Present", "tag_atual": tag_na_bios, "mac": "aa:bb",
        }

        def fake_ssh_run(ip, user, cmd, timeout=30):
            if "dmidecode" in cmd:
                return 0, tag_na_bios + "\n", ""
            if "rpm -q" in cmd:
                return 0, "AUSENTE\n", ""
            return 0, "", ""

        with mock.patch.object(hp, "testa_porta_ssh", return_value=True), \
             mock.patch.object(hp, "prepara_autenticacao_ssh",
                               return_value=True), \
             mock.patch.object(hp, "detecta_sudo",
                               return_value=("sudo", True)), \
             mock.patch.object(hp, "coletar_dados_ambiente_remoto",
                               return_value=ambiente), \
             mock.patch.object(hp, "le_valor_configuracao_remoto",
                               return_value=""), \
             mock.patch.object(hp, "valida_via_patrimonial_cli",
                               return_value=""), \
             mock.patch.object(hp, "sincroniza_bbconfig_remoto",
                               return_value={"sincronizado": True,
                                             "backup": ""}), \
             mock.patch.object(hp, "ssh_run", side_effect=fake_ssh_run), \
             mock.patch.object(hp, "tenta_escrever_tag_remoto",
                               side_effect=fake_cascata), \
             mock.patch.object(hp, "tenta_teste_escrita_remoto",
                               return_value="OK-amidelnx"), \
             mock.patch.object(hp, "gravar_log_remoto"), \
             mock.patch.object(hp, "gravar_log"):
            registro = hp.processa_host_remoto(
                "192.0.2.1", bem_lista, args, "",
                chave_ja_validada=True)
        return registro, chamadas["cascata"]

    def test_tag_ja_correta_nao_chama_cascata(self):
        """Tag identica na BIOS: OK-ja-correto, cascata nunca chamada."""
        registro, n = self._roda("74171618303986", "7417161830398",
                                 self._args(write=True))
        self.assertEqual(registro["resultado"], "OK-ja-correto")
        self.assertEqual(n, 0)
        self.assertEqual(registro["bbconfig_sync"], "OK")

    def test_tag_diferente_chama_cascata(self):
        """Tag divergente: cascata chamada exatamente uma vez."""
        registro, n = self._roda("Not Specified", "7417161830398",
                                 self._args(write=True))
        self.assertEqual(registro["resultado"], "OK-amidelnx")
        self.assertEqual(n, 1)

    def test_dry_run_nao_ativa_trava(self):
        """Sem --write o fluxo segue para a cascata (que so simula)."""
        _, n = self._roda("74171618303986", "7417161830398",
                          self._args(write=False))
        self.assertEqual(n, 1)

    def test_test_write_nao_ativa_trava(self):
        """Com --test-write a trava nao se aplica; cascata e chamada."""
        _, n = self._roda("74171618303986", "7417161830398",
                          self._args(write=True, test_write=True))
        self.assertEqual(n, 1)

    def test_tag_com_dv_x_ja_correta(self):
        """Trava tambem funciona para tag terminada em X (DV=10)."""
        registro, n = self._roda("7417161830009X", "7417161830009",
                                 self._args(write=True))
        self.assertEqual(registro["resultado"], "OK-ja-correto")
        self.assertEqual(n, 0)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
