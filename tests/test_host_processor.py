# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_host_processor.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_host_processor -v)
#
# DESCRIPTION: Integracao de processa_host_remoto: trava global
#              OK-ja-correto (nao regravar tag ja correta).
#              Roda em qualquer maquina, sem SSH real: tudo que toca
#              rede e mockado via unittest.mock. Nenhuma dependencia
#              alem da stdlib.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.3
# REVISION: 2026-09-28 - v2.3.3 - padrao do arquivo de configuracao passa a
#                        13 (testes de 14 pedem bbconfig_digitos=14 explicito);
#                        DV divergente resulta INVALIDO sem gravar;
#                        TestPadraoArquivoTrezeV233.
# REVISION: 2026-09-28 - v2.3.2 - TestDigitosPorDestinoV232.
# REVISION: 2026-09-24 - v2.3.1 - _BasePerfis; TestSudoFalhaTentaProximo
#                        PerfilV231 e TestMesmoPatrimonioCaixaV231.
# REVISION: 2026-09-23 - v2.3.0 - _roda registra mensagens de log e args da
#                        cascata e aceita kernel; TestMesmoPatrimonio,
#                        TestAvisoBemDivergenteV230,
#                        TestPacoteModuloPeloKernelV230,
#                        TestPerfisDeAcessoV230 e TestTriagemComPerfisV230.
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

from update_dmi_tag.patrimonio import valida_via_patrimonial_cli  # noqa: E402
from update_dmi_tag import host_processor as hp  # noqa: E402
from update_dmi_tag import acesso  # noqa: E402

class _BaseIntegracaoHost(object):
    """Infraestrutura compartilhada dos testes de integracao de
    processa_host_remoto: monta o Namespace de argumentos e executa a
    funcao REAL com toda a camada de rede mockada. Nao herda de
    TestCase de proposito, para nao ser coletada como suite propria."""

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

    def _roda(self, tag_na_bios, bem_lista, args, bem_conf="", kernel=None):
        """Roda processa_host_remoto e devolve (registro, n_chamadas_cascata).

        bem_conf simula o valor lido do arquivo de configuracao remoto
        (vazio = variavel ausente/nao lida no alvo). kernel, se informado,
        vira o osrelease devolvido pela coleta de ambiente (v2.3.0).
        """
        chamadas = {"cascata": 0, "sync_args": None, "cascata_args": None}

        def fake_cascata(*a, **k):
            chamadas["cascata"] += 1
            chamadas["cascata_args"] = a
            return "OK-amidelnx"

        def fake_sync(*a, **k):
            chamadas["sync_args"] = a
            return {"sincronizado": True, "backup": ""}

        ambiente = {
            "hostname": "vm-teste", "board_vendor": "X", "board_name": "Y",
            "bios_vendor": "Z", "bios_version": "1", "smbios_version": "3.2",
            "wsmt": "Present", "tag_atual": tag_na_bios, "mac": "aa:bb",
        }
        if kernel is not None:
            ambiente["kernel"] = kernel

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
                               return_value=bem_conf), \
             mock.patch.object(hp, "valida_via_patrimonial_cli",
                               return_value=""), \
             mock.patch.object(hp, "sincroniza_bbconfig_remoto",
                               side_effect=fake_sync), \
             mock.patch.object(hp, "ssh_run", side_effect=fake_ssh_run), \
             mock.patch.object(hp, "tenta_escrever_tag_remoto",
                               side_effect=fake_cascata), \
             mock.patch.object(hp, "tenta_teste_escrita_remoto",
                               return_value="OK-amidelnx"), \
             mock.patch.object(hp, "gravar_log_remoto") as m_log, \
             mock.patch.object(hp, "gravar_log"):
            registro = hp.processa_host_remoto(
                "192.0.2.1", bem_lista, args, "",
                chave_ja_validada=True)
        # Guarda os argumentos da sincronizacao do arquivo de config para
        # os testes que precisam inspecionar o valor efetivamente enviado.
        self.sync_args = chamadas["sync_args"]
        # v2.3.0: mensagens de log (nivel, texto) e args entregue a cascata.
        self.mensagens = [(c[0][4], c[0][5]) for c in m_log.call_args_list]
        self.cascata_args = chamadas["cascata_args"]
        return registro, chamadas["cascata"]

    def _valor_enviado_ao_arquivo_de_config(self):
        """7o argumento posicional de sincroniza_bbconfig_remoto."""
        self.assertIsNotNone(self.sync_args,
                             "sincronizacao do arquivo nao foi chamada")
        return self.sync_args[6]


class TestTravaGlobalIntegracao(_BaseIntegracaoHost, unittest.TestCase):
    """Integracao com mocks: processa_host_remoto de ponta a ponta,
    provando que a trava global (v2.2.8) NAO chama a cascata quando a
    tag ja esta correta, e CHAMA quando esta diferente."""

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


class TestPrecedenciaBemNumero(_BaseIntegracaoHost, unittest.TestCase):
    """Ordem das fontes do BEM_NUMERO, exercitando processa_host_remoto
    real: lista de hosts tem precedencia sobre o arquivo de configuracao
    do equipamento; sem nenhuma das duas o host e ignorado.

    Comportamento documentado em host_processor.py, secao 6. Nunca houve
    teste disso, apesar de ser a regra que decide QUAL numero e gravado
    na BIOS de cada equipamento."""

    def test_lista_tem_precedencia_sobre_arquivo_de_config(self):
        """Com as duas fontes divergentes, vale o valor da lista."""
        registro, n = self._roda(
            "Not Specified", "7417161830398",
            self._args(write=True), bem_conf="74171618309999")
        self.assertEqual(registro["bem_usado"], "7417161830398")
        self.assertEqual(registro["bem_conf"], "74171618309999")
        self.assertEqual(n, 1)

    def test_lista_ausente_usa_arquivo_de_config(self):
        """Sem valor na lista, cai para o do arquivo do equipamento."""
        registro, n = self._roda(
            "Not Specified", "", self._args(write=True),
            bem_conf="74171618303986")
        self.assertEqual(registro["bem_usado"], "74171618303986")
        self.assertEqual(n, 1)

    def test_sem_nenhuma_fonte_resulta_pendente_e_nao_grava(self):
        """Sem lista e sem arquivo: PENDENTE e cascata nunca chamada.

        Este e o unico caso em que o host e abandonado antes de qualquer
        tentativa de escrita, entao a cascata nao pode ser tocada."""
        registro, n = self._roda(
            "Not Specified", "", self._args(write=True), bem_conf="")
        self.assertEqual(registro["resultado"], "PENDENTE")
        self.assertEqual(registro["bem_conf"], "PENDENTE")
        self.assertEqual(n, 0)

    def test_arquivo_com_a_string_pendente_conta_como_ausente(self):
        """Se o arquivo traz literalmente 'PENDENTE', nao e numero valido.

        Cuidado de leitura: a coluna 'BEM conf' do resumo mostra
        'PENDENTE' tanto quando a variavel esta vazia quanto quando o
        proprio arquivo contem essa palavra. Nos dois casos o host cai
        no mesmo caminho."""
        registro, n = self._roda(
            "Not Specified", "", self._args(write=True),
            bem_conf="PENDENTE")
        self.assertEqual(registro["resultado"], "PENDENTE")
        self.assertEqual(n, 0)

    def test_fontes_iguais_nao_e_tratado_como_divergencia(self):
        """Lista e arquivo com o mesmo valor: segue normal pela lista."""
        registro, n = self._roda(
            "Not Specified", "7417161830398",
            self._args(write=True), bem_conf="7417161830398")
        self.assertEqual(registro["bem_usado"], "7417161830398")
        self.assertEqual(n, 1)


class TestFormatoGravadoNoArquivoDeConfig(_BaseIntegracaoHost,
                                          unittest.TestCase):
    """O arquivo de configuracao do equipamento recebe SEMPRE a tag de 14
    digitos, a mesma gravada na BIOS, independente do formato da origem.

    Regressao para a divergencia corrigida em 2026-08-10: o modo remoto
    enviava o valor cru da fonte (bem_usar), entao uma lista com 13
    digitos deixava o arquivo com 13, enquanto o modo standalone ja
    enviava tag_esperada (14). O efeito pratico era o mesmo patrimonio
    ser tratado como divergente por diferenca de formato, ja que a
    comparacao de 'ja sincronizado' e de string pura.

    v2.3.3: o padrao do arquivo passou a 13. Estes testes cobrem o formato
    de 14, agora pedido explicitamente (--bbconfig-digitos 14)."""

    def _args(self, write=True, test_write=False):
        ns = super(TestFormatoGravadoNoArquivoDeConfig, self)._args(
            write=write, test_write=test_write)
        ns.bbconfig_digitos = 14
        return ns

    def test_origem_com_13_digitos_grava_14_no_arquivo(self):
        """13 digitos na lista: o arquivo recebe os 14 com o DV calculado."""
        registro, _ = self._roda("Not Specified", "7417161830398",
                                 self._args(write=True))
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "74171618303986")
        self.assertEqual(registro["bem_usado"], "7417161830398",
                         "a coluna do relatorio segue mostrando a origem")

    def test_origem_com_14_digitos_grava_os_mesmos_14(self):
        """Origem ja com 14 digitos passa intacta, sem recalcular o DV."""
        self._roda("Not Specified", "74171618303986", self._args(write=True))
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "74171618303986")

    def test_dv_x_e_preservado_em_maiusculo(self):
        """DV igual a 10 vira X maiusculo, mesmo formato usado na BIOS."""
        self._roda("Not Specified", "7417161830009", self._args(write=True))
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "7417161830009X")

    def test_dv_divergente_informado_resulta_invalido_v233(self):
        """v2.3.3: 14 digitos com DV divergente: INVALIDO, nada gravado.

        Ate a v2.3.2 o valor era gravado como informado, com aviso. O
        numero nao e corrigido por conta propria: o operador informa o
        valor certo e roda de novo. Nem a BIOS nem o arquivo sao tocados."""
        registro, n = self._roda("Not Specified", "74171618303980",
                                 self._args(write=True))
        self.assertEqual(registro["resultado"], "INVALIDO")
        self.assertEqual(n, 0, "a cascata nao pode ser chamada")
        self.assertIsNone(self.sync_args, "o arquivo nao pode ser tocado")

    def test_dv_divergente_vindo_do_arquivo_tambem_e_invalido_v233(self):
        """Sem lista, o valor com DV errado do proprio arquivo: INVALIDO."""
        registro, n = self._roda("74171618303980", "", self._args(write=True),
                                 bem_conf="74171618303980")
        self.assertEqual(registro["resultado"], "INVALIDO")
        self.assertEqual(n, 0)
        self.assertIsNone(self.sync_args)

    def test_tag_ja_correta_na_bios_ainda_corrige_o_arquivo(self):
        """BIOS ja com 14 digitos e arquivo com 13: corrige so o arquivo.

        Cenario real de campo: uma execucao anterior gravou a BIOS com 14
        digitos mas deixou o arquivo com 13, porque a versao daquela epoca
        comparava o arquivo com o valor cru da origem. Rodando de novo com
        a versao corrigida, a trava global impede qualquer escrita na BIOS
        (nada a corrigir la) e a sincronizacao ajusta apenas o arquivo.
        Nenhum mecanismo e executado, nenhum reboot."""
        registro, n = self._roda(
            "74171618303986", "", self._args(write=True),
            bem_conf="7417161830398")
        self.assertEqual(registro["resultado"], "OK-ja-correto")
        self.assertEqual(n, 0, "nenhum mecanismo pode ser executado")
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "74171618303986")

    def test_valor_vindo_do_proprio_arquivo_tambem_e_normalizado(self):
        """Sem lista, o valor de 13 digitos do arquivo volta com 14."""
        self._roda("Not Specified", "", self._args(write=True),
                   bem_conf="7417161830398")
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "74171618303986")


class TestMesmoPatrimonio(unittest.TestCase):
    """v2.3.0: 13 e 14 digitos do mesmo patrimonio nao sao divergencia."""

    def test_casos(self):
        casos = [
            ("7417161480048", "74171614800489", True),
            ("74171614800489", "7417161480048", True),
            ("74171614800489", "74171614800489", True),
            ("7417161480048", "7417161480048", True),
            ("74171614800489", "74171614800480", False),
            ("7417161480048", "74171618303986", False),
            ("7417161480048", "7417161480049", False),
            (" 7417161480048 ", "74171614800489", True),
        ]
        for a, b, esperado in casos:
            self.assertEqual(hp._mesmo_patrimonio(a, b), esperado, (a, b))


class TestAvisoBemDivergenteV230(_BaseIntegracaoHost, unittest.TestCase):
    """Regressao para aviso falso visto em campo (2026-09-23, hosts
    10.204.20.5 e 10.98.174.5): lista com 13 digitos e BBconfig com 14 do
    mesmo patrimonio gerava 'BEM_NUMERO da lista ... difere do BBconfig'."""

    def _avisos_de_divergencia(self):
        return [m for n, m in self.mensagens if "difere do BBconfig" in m]

    def test_13_e_14_do_mesmo_patrimonio_nao_avisa(self):
        self._roda("Not Specified", "7417161480048", self._args(write=True),
                   bem_conf="74171614800489")
        self.assertEqual(self._avisos_de_divergencia(), [])

    def test_divergencia_real_continua_avisando(self):
        self._roda("Not Specified", "7417161830398", self._args(write=True),
                   bem_conf="74171618309999")
        self.assertEqual(len(self._avisos_de_divergencia()), 1)


class TestPacoteModuloPeloKernelV230(_BaseIntegracaoHost, unittest.TestCase):
    """v2.3.0: sem --module-package, a cascata recebe o KMP do flavor do
    kernel do host, numa copia de args (o original e compartilhado entre
    as threads do --parallel e nao pode mudar)."""

    def _roda_com(self, kernel, module_package):
        args = self._args(write=True)
        args.module_package = module_package
        registro, n = self._roda("Not Specified", "7417161830398", args,
                                 kernel=kernel)
        return args, registro, n

    def test_kernel_pae_entrega_kmp_pae_a_cascata(self):
        args, _, n = self._roda_com("3.0.101-71-pae", None)
        self.assertEqual(n, 1)
        self.assertEqual(self.cascata_args[4].module_package,
                         "amibios-dmi-kmp-pae")
        self.assertIsNone(args.module_package,
                          "o args original nao pode ser alterado")

    def test_kernel_default_entrega_kmp_default(self):
        self._roda_com("5.14.21-150500.55.39-default", None)
        self.assertEqual(self.cascata_args[4].module_package,
                         "amibios-dmi-kmp-default")

    def test_module_package_explicito_prevalece(self):
        self._roda_com("3.0.101-71-pae", "amibios-dmi-kmp-forcado")
        self.assertEqual(self.cascata_args[4].module_package,
                         "amibios-dmi-kmp-forcado")


class _BasePerfis(object):
    """Harness dos testes de perfis de acesso (v2.3.0 e v2.3.1)."""

    OPERADOR = acesso.Perfil("operador", "f4683594", "senha-op",
                             ("senha-op", "senha-root"))
    ROOT = acesso.Perfil("root", "root", "senha-root", ("senha-root",))

    def _args(self):
        ns = types.SimpleNamespace()
        ns.log_file = ""
        ns.ssh_user = "ignorado"
        ns.sudo_pass = ""
        ns.verbose = False
        ns.csv = False
        ns.write = True
        ns.test_write = False
        ns.production = False
        ns.config = "/etc/BBconfig.conf"
        ns.var = "BEM_NUMERO"
        ns.module_package = "amibios-dmi-kmp-default"
        ns.ssh_pass_efetiva = ""
        ns.perfis_acesso = [self.OPERADOR, self.ROOT]
        return ns

    def _roda(self, fake_prepara, fake_sudo, perfil=None,
              chave_ja_validada=False):
        ambiente = {"hostname": "h", "tag_atual": "Not Specified",
                    "kernel": "3.0.101-71-pae"}
        with mock.patch.object(hp, "testa_porta_ssh", return_value=True), \
             mock.patch.object(hp, "prepara_autenticacao_ssh",
                               side_effect=fake_prepara) as m_prep, \
             mock.patch.object(hp, "detecta_sudo",
                               side_effect=fake_sudo) as m_sudo, \
             mock.patch.object(hp, "coletar_dados_ambiente_remoto",
                               return_value=ambiente), \
             mock.patch.object(hp, "le_valor_configuracao_remoto",
                               return_value="7417161830398"), \
             mock.patch.object(hp, "valida_via_patrimonial_cli",
                               return_value=""), \
             mock.patch.object(hp, "sincroniza_bbconfig_remoto",
                               return_value={"sincronizado": True,
                                             "backup": ""}), \
             mock.patch.object(hp, "ssh_run", return_value=(0, "", "")), \
             mock.patch.object(hp, "tenta_escrever_tag_remoto",
                               return_value="OK-amibios"), \
             mock.patch.object(hp, "gravar_log_remoto"), \
             mock.patch.object(hp, "gravar_log"):
            registro = hp.processa_host_remoto(
                "192.0.2.1", "", self._args(), "",
                chave_ja_validada=chave_ja_validada, perfil=perfil)
        return registro, m_prep, m_sudo


class TestPerfisDeAcessoV230(_BasePerfis, unittest.TestCase):
    """v2.3.0: perfis tentados em ordem, host a host, e sudo cobrindo os
    tres comportamentos (sem senha, senha do usuario, senha do root)."""

    def test_operador_recusado_entra_como_root(self):
        """SLE 11: o usuario do operador nao existe, o root entra."""
        def prepara(ip, usuario, senha, log, verbose, nivel_falha="ERROR"):
            return usuario == "root"

        registro, m_prep, m_sudo = self._roda(
            prepara, lambda ip, u, s="": ("sudo", True))
        self.assertEqual(registro["acesso"], "root")
        self.assertEqual(registro["resultado"], "OK-amibios")
        # A recusa do primeiro perfil nao e a ultima tentativa: WARNING.
        self.assertEqual(m_prep.call_args_list[0][1]["nivel_falha"], "WARNING")
        self.assertEqual(m_prep.call_args_list[1][1]["nivel_falha"], "ERROR")
        self.assertEqual(m_sudo.call_args_list[0][0][1], "root")

    def test_operador_aceito_nao_tenta_root(self):
        """SLE 12/15: o operador entra de primeira."""
        registro, m_prep, _ = self._roda(
            lambda *a, **k: True, lambda ip, u, s="": ("sudo", True))
        self.assertEqual(registro["acesso"], "operador")
        self.assertEqual(m_prep.call_count, 1)

    def test_nenhum_perfil_entra_resulta_inacessivel(self):
        registro, m_prep, m_sudo = self._roda(
            lambda *a, **k: False, lambda ip, u, s="": ("sudo", True))
        self.assertEqual(registro["resultado"], "INACESSIVEL")
        self.assertEqual(m_prep.call_count, 2)
        m_sudo.assert_not_called()

    def test_perfil_da_triagem_dispensa_bootstrap(self):
        registro, m_prep, _ = self._roda(
            lambda *a, **k: True, lambda ip, u, s="": ("sudo", True),
            perfil=self.ROOT, chave_ja_validada=True)
        self.assertEqual(registro["acesso"], "root")
        m_prep.assert_not_called()

    def test_sudo_tenta_senha_do_usuario_e_depois_do_root(self):
        """Padrao SUSE (targetpw): so a senha do root abre o sudo."""
        def sudo(ip, usuario, senha=""):
            if senha == "senha-root":
                return ("echo 'senha-root' | sudo -S", True)
            return ("sudo", False)

        registro, _, m_sudo = self._roda(lambda *a, **k: True, sudo)
        senhas = [c[0][2] for c in m_sudo.call_args_list]
        self.assertEqual(senhas, ["senha-op", "senha-root"])
        self.assertEqual(registro["resultado"], "OK-amibios")

    def test_sudo_sem_senha_para_na_primeira(self):
        registro, _, m_sudo = self._roda(
            lambda *a, **k: True, lambda ip, u, s="": ("sudo", True))
        self.assertEqual(m_sudo.call_count, 1)


class TestSudoFalhaTentaProximoPerfilV231(_BasePerfis, unittest.TestCase):
    """v2.3.1: o perfil entra mas o sudo nao confirma; o proximo perfil do
    arquivo e tentado antes de o host ficar SEM-SUDO."""

    @staticmethod
    def _sudo_so_root(ip, usuario, senha=""):
        return ("sudo", usuario == "root")

    def test_operador_sem_sudo_passa_para_root(self):
        """Defeito: a v2.3.0 parava em SEM-SUDO com o root disponivel."""
        registro, m_prep, m_sudo = self._roda(lambda *a, **k: True,
                                              self._sudo_so_root)
        self.assertEqual(registro["acesso"], "root")
        self.assertEqual(registro["resultado"], "OK-amibios")
        self.assertEqual([c[0][1] for c in m_prep.call_args_list],
                         ["f4683594", "root"])
        self.assertEqual(m_prep.call_args_list[1][1]["nivel_falha"], "WARNING")

    def test_sudo_do_operador_ok_nunca_tenta_root(self):
        """Regressao: sem falha de sudo, nada muda."""
        registro, m_prep, m_sudo = self._roda(
            lambda *a, **k: True, lambda ip, u, s="": ("sudo", True))
        self.assertEqual(registro["acesso"], "operador")
        self.assertEqual(m_prep.call_count, 1)
        self.assertEqual({c[0][1] for c in m_sudo.call_args_list}, {"f4683594"})

    def test_nenhum_perfil_com_sudo_fica_sem_sudo_no_primeiro(self):
        registro, m_prep, _ = self._roda(
            lambda *a, **k: True, lambda ip, u, s="": ("sudo", False))
        self.assertEqual(registro["resultado"], "SEM-SUDO")
        self.assertEqual(registro["acesso"], "operador")

    def test_root_recusado_no_ssh_mantem_operador(self):
        def prepara(ip, usuario, senha, log, verbose, nivel_falha="ERROR"):
            return usuario != "root"

        registro, m_prep, m_sudo = self._roda(
            prepara, lambda ip, u, s="": ("sudo", False))
        self.assertEqual(registro["resultado"], "SEM-SUDO")
        self.assertEqual({c[0][1] for c in m_sudo.call_args_list}, {"f4683594"})

    def test_perfil_da_triagem_sem_sudo_tambem_tenta_proximo(self):
        """Colisao: host escolhido pela chave na triagem (sem bootstrap)."""
        registro, m_prep, _ = self._roda(
            lambda *a, **k: True, self._sudo_so_root,
            perfil=self.OPERADOR, chave_ja_validada=True)
        self.assertEqual(registro["acesso"], "root")
        self.assertEqual(m_prep.call_count, 1)

    def test_ultimo_perfil_sem_sudo_nao_tenta_nada(self):
        registro, m_prep, _ = self._roda(
            lambda *a, **k: True, lambda ip, u, s="": ("sudo", False),
            perfil=self.ROOT, chave_ja_validada=True)
        self.assertEqual(registro["resultado"], "SEM-SUDO")
        m_prep.assert_not_called()


class TestMesmoPatrimonioCaixaV231(unittest.TestCase):

    def test_x_minusculo_e_maiusculo_sao_o_mesmo(self):
        self.assertTrue(hp._mesmo_patrimonio("7417172690121x", "7417172690121X"))
        self.assertTrue(hp._mesmo_patrimonio("7417172690121", "7417172690121x"))

    def test_dv_diferente_continua_divergente(self):
        self.assertFalse(hp._mesmo_patrimonio("74171726901210", "7417172690121X"))


class TestDigitosPorDestinoV232(_BaseIntegracaoHost, unittest.TestCase):
    """v2.3.2: --bios-digitos e --bbconfig-digitos, independentes; a
    validacao continua sendo feita com as 14 posicoes."""

    def _args_dig(self, bios=14, bbconfig=14, write=True):
        args = self._args(write=write)
        args.bios_digitos = bios
        args.bbconfig_digitos = bbconfig
        return args

    def _tag_enviada_a_cascata(self):
        return self.cascata_args[3]

    def test_padrao_sem_atributo_bios_14_arquivo_14(self):
        """Ajuste de 30/09/2026: sem as opcoes, 14 na BIOS e 14 no arquivo.

        Na v2.3.3 original o arquivo ia a 13."""
        registro, n = self._roda("Not Specified", "7417161830398",
                                 self._args(write=True))
        self.assertEqual(self._tag_enviada_a_cascata(), "74171618303986")
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "74171618303986")

    def test_bbconfig_14_explicito_continua_disponivel_v233(self):
        """Perda de funcionalidade: quem quiser 14 no arquivo ainda pode."""
        self._roda("Not Specified", "7417161830398", self._args_dig(bbconfig=14))
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "74171618303986")

    def test_bbconfig_13_bios_14(self):
        """Defeito que motivou: aplicacao le o arquivo e quer 13."""
        self._roda("Not Specified", "7417161830398", self._args_dig(bbconfig=13))
        self.assertEqual(self._tag_enviada_a_cascata(), "74171618303986")
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "7417161830398")

    def test_bios_13_bbconfig_14(self):
        self._roda("Not Specified", "7417161830398", self._args_dig(bios=13))
        self.assertEqual(self._tag_enviada_a_cascata(), "7417161830398")
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "74171618303986")

    def test_bios_13_ja_gravado_com_13_nao_regrava(self):
        """Colisao com a trava OK-ja-correto."""
        registro, n = self._roda("7417161830398", "7417161830398",
                                 self._args_dig(bios=13, bbconfig=13))
        self.assertEqual(registro["resultado"], "OK-ja-correto")
        self.assertEqual(n, 0)
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "7417161830398")

    def test_bios_13_com_14_na_bios_regrava(self):
        """Adverso: equipamento ja gravado com 14 e regravado com 13."""
        registro, n = self._roda("74171618303986", "7417161830398",
                                 self._args_dig(bios=13))
        self.assertEqual(n, 1)
        self.assertEqual(self._tag_enviada_a_cascata(), "7417161830398")

    def test_bios_14_com_13_na_bios_regrava(self):
        """Regressao: tag incompleta na BIOS continua sendo completada."""
        registro, n = self._roda("7417161830398", "7417161830398",
                                 self._args_dig())
        self.assertEqual(n, 1)
        self.assertEqual(self._tag_enviada_a_cascata(), "74171618303986")

    def test_bem_com_dv_x_em_13_sai_sem_o_x(self):
        self._roda("Not Specified", "7417161830009", self._args_dig(bbconfig=13))
        self.assertEqual(self._tag_enviada_a_cascata(), "741716183000" + "9X")
        self.assertEqual(self._valor_enviado_ao_arquivo_de_config(),
                         "7417161830009")


class TestTriagemComPerfisV230(unittest.TestCase):
    """v2.3.0: a triagem testa a chave de cada perfil e devolve o perfil
    aceito junto com o host (tupla de 4 elementos)."""

    def _args(self, perfis):
        ns = types.SimpleNamespace(verbose=False, ssh_user="x",
                                   ssh_pass_efetiva="", sudo_pass="",
                                   perfis_acesso=perfis)
        return ns

    def test_chave_so_do_root_escolhe_root(self):
        op = acesso.Perfil("operador", "f4683594", "a", ())
        root = acesso.Perfil("root", "root", "b", ())
        with mock.patch.object(hp, "testa_porta_ssh", return_value=True), \
             mock.patch.object(hp, "testa_conexao_ssh",
                               side_effect=lambda ip, u: u == "root"), \
             mock.patch.object(hp, "gravar_log"):
            validos, descartados, _ = hp.triagem_hosts_remotos(
                [("192.0.2.1", "")], self._args([op, root]), "")
        self.assertEqual(validos, [("192.0.2.1", "", True, root)])
        self.assertEqual(descartados, [])

    def test_sem_chave_e_com_senha_fica_pendente(self):
        op = acesso.Perfil("operador", "f4683594", "a", ())
        with mock.patch.object(hp, "testa_porta_ssh", return_value=True), \
             mock.patch.object(hp, "testa_conexao_ssh", return_value=False), \
             mock.patch.object(hp, "gravar_log"):
            validos, _, _ = hp.triagem_hosts_remotos(
                [("192.0.2.1", "7417161830398")], self._args([op]), "")
        self.assertEqual(validos, [("192.0.2.1", "7417161830398", False, None)])

    def test_sem_chave_e_sem_senha_e_descartado(self):
        op = acesso.Perfil("operador", "f4683594", "", ())
        with mock.patch.object(hp, "testa_porta_ssh", return_value=True), \
             mock.patch.object(hp, "testa_conexao_ssh", return_value=False), \
             mock.patch.object(hp, "gravar_log"):
            validos, descartados, hosts_desc = hp.triagem_hosts_remotos(
                [("192.0.2.1", "")], self._args([op]), "")
        self.assertEqual(validos, [])
        self.assertEqual(hosts_desc, [("192.0.2.1", "")])


class TestMotivoInacessivelV236(_BasePerfis, unittest.TestCase):
    """v2.3.6: todo INACESSIVEL leva o motivo (rede ou acesso), na triagem e
    na Fase 2, para as listas por motivo do fim da execucao."""

    def _triagem(self, porta, senha):
        op = acesso.Perfil("operador", "f4683594", senha, ())
        args = types.SimpleNamespace(verbose=False, ssh_user="x",
                                     ssh_pass_efetiva="", sudo_pass="",
                                     perfis_acesso=[op])
        with mock.patch.object(hp, "testa_porta_ssh", return_value=porta), \
             mock.patch.object(hp, "testa_conexao_ssh", return_value=False), \
             mock.patch.object(hp, "gravar_log"):
            _, descartados, _ = hp.triagem_hosts_remotos(
                [("192.0.2.1", "")], args, "")
        return descartados

    def test_triagem_offline_e_rede(self):
        descartados = self._triagem(porta=False, senha="a")
        self.assertEqual(descartados[0]["motivo_inacessivel"], "rede")

    def test_triagem_negado_e_acesso(self):
        descartados = self._triagem(porta=True, senha="")
        self.assertEqual(descartados[0]["motivo_inacessivel"], "acesso")

    def test_fase2_bootstrap_falhou_e_acesso(self):
        """Defeito 2026-10-14: 4 de 55 inacessiveis eram da Fase 2."""
        registro, _, _ = self._roda(lambda *a, **k: False,
                                    lambda ip, u, s="": ("sudo", True))
        self.assertEqual(registro["resultado"], "INACESSIVEL")
        self.assertEqual(registro["motivo_inacessivel"], "acesso")

    def test_fase2_porta_fechada_e_rede(self):
        """1 caso em 2026-10-14: ligado na triagem, desligado na Fase 2."""
        with mock.patch.object(hp, "testa_porta_ssh", return_value=False), \
             mock.patch.object(hp, "prepara_autenticacao_ssh") as m_prep, \
             mock.patch.object(hp, "gravar_log_remoto"), \
             mock.patch.object(hp, "gravar_log"):
            registro = hp.processa_host_remoto("192.0.2.1", "", self._args(), "")
        self.assertEqual(registro["resultado"], "INACESSIVEL")
        self.assertEqual(registro["motivo_inacessivel"], "rede")
        m_prep.assert_not_called()

    def test_host_gravado_sem_motivo(self):
        """Regressao: host que entra nao ganha motivo de inacessivel."""
        registro, _, _ = self._roda(lambda *a, **k: True,
                                    lambda ip, u, s="": ("sudo", True))
        self.assertEqual(registro["resultado"], "OK-amibios")
        self.assertEqual(registro["motivo_inacessivel"], "")


class TestPadraoArquivoTrezeV233(unittest.TestCase):
    """Padrao de --bbconfig-digitos na linha de comando: 13 na v2.3.3
    original, 14 desde o ajuste de 30/09/2026, igual ao de --bios-digitos.
    Mede o fato observavel (o Namespace produzido pelo parser real de
    main), sem ler o codigo-fonte."""

    def _args_do_parser(self, extra):
        import update_dmi_tag.__main__ as principal
        capturado = {}

        def para_no_parse(args_ns):
            capturado["args"] = args_ns
            raise SystemExit(0)

        argv = ["update_dmi_tag"] + extra
        with mock.patch.object(sys, "argv", argv),              mock.patch.object(principal.argparse.ArgumentParser,
                               "parse_args", autospec=True,
                               side_effect=lambda self, *a, **k: para_no_parse(
                                   principal.argparse.ArgumentParser.parse_known_args(
                                       self, *a, **k)[0])):
            with self.assertRaises(SystemExit):
                principal.main()
        return capturado["args"]

    def test_padrao_bbconfig_14_bios_14(self):
        args = self._args_do_parser([])
        self.assertEqual(args.bbconfig_digitos, 14)
        self.assertEqual(args.bios_digitos, 14)

    def test_opcoes_explicitas_14_e_14(self):
        """Opcoes passadas iguais ao padrao continuam aceitas."""
        args = self._args_do_parser(["--bios-digitos", "14",
                                     "--bbconfig-digitos", "14"])
        self.assertEqual(args.bios_digitos, 14)
        self.assertEqual(args.bbconfig_digitos, 14)

    def test_opcoes_explicitas_13_e_13(self):
        """Os dois destinos em 13, sem o DV."""
        args = self._args_do_parser(["--bios-digitos", "13",
                                     "--bbconfig-digitos", "13"])
        self.assertEqual(args.bios_digitos, 13)
        self.assertEqual(args.bbconfig_digitos, 13)

    def test_opcao_13_no_arquivo_continua_disponivel(self):
        """Perda de funcionalidade: quem quiser 13 no arquivo ainda pode."""
        args = self._args_do_parser(["--bbconfig-digitos", "13"])
        self.assertEqual(args.bbconfig_digitos, 13)
        self.assertEqual(args.bios_digitos, 14)

    def test_opcoes_explicitas_continuam_valendo(self):
        args = self._args_do_parser(["--bbconfig-digitos", "14",
                                     "--bios-digitos", "13"])
        self.assertEqual(args.bbconfig_digitos, 14)
        self.assertEqual(args.bios_digitos, 13)


if __name__ == "__main__":
    unittest.main(verbosity=2)
