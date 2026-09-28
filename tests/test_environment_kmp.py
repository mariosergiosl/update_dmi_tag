# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_environment_kmp.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_environment_kmp -v)
#
# DESCRIPTION: Ciclo de vida do KMP no alvo remoto: escolha do RPM pelo
#              kernel do host, confirmacao de versao instalada,
#              instalacao com fallback e desinstalacao.
#              Roda em qualquer maquina, sem SSH real: tudo que toca
#              rede e mockado via unittest.mock. Nenhuma dependencia
#              alem da stdlib.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.0
# REVISION: 2026-09-23 - v2.3.0 - c[0][2] no lugar de c.args[2] (Python
#                        3.6); TestPacoteKmpParaKernel,
#                        TestInstalaIgnoraUserspaceV230 e
#                        TestDesinstalaUserspaceV230;
#                        test_zypper_remove_bem_sucedido passa a exigir que
#                        o userspace ausente NAO seja removido.
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
import hashlib
import tempfile
import unittest
from unittest import mock

# Raiz do repositorio (pai da pasta tests/), para importar o pacote sem
# depender de instalacao nem do diretorio corrente do chamador.
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.chdir(BASE)

from update_dmi_tag import environment as env  # noqa: E402

class TestInstalaModuloRemotoKernelMatching(unittest.TestCase):
    """Regressao para bug real (2026-07-20): instala_modulo_remoto
    comparava o osrelease completo (formato 'versao-build-flavor', ex.
    '5.3.18-22-default') contra o nome do arquivo (formato
    'amibios-dmi-kmp-flavor-versao-build.rpm', flavor ANTES da versao).
    A comparacao por substring direta nunca batia com nenhum candidato
    real, entao TODO host caia em KMP-KERNEL-MISMATCH mesmo com o RPM
    certo presente na pasta -- regressao total da instalacao automatica
    do KMP. Os testes de TestCascataUnidade nao pegavam isso porque
    mockam executa_amibios_remoto (quem chama instala_modulo_remoto),
    nunca exercitando o matching de verdade. Este teste roda
    instala_modulo_remoto de verdade (arquivos reais em disco), so
    ssh_run/scp/verificacao de pacote sao mockados."""

    def _prepara_rpms(self, tmpdir):
        nomes = [
            "amibios-dmi-kmp-default-5.3.18-22.rpm",
            "amibios-dmi-kmp-default-6.4.0-150700.51.rpm",
            "amibios-dmi-kmp-default-4.12.14-120.rpm",
        ]
        for n in nomes:
            with open(os.path.join(tmpdir, n), "wb") as f:
                f.write(b"conteudo-fake-rpm")
        return nomes

    def test_escolhe_kmp_certo_para_kernel_real(self):
        """Kernel osrelease real de campo ('5.3.18-22-default') deve
        escolher o candidato certo, nao 'o ultimo em ordem alfabetica'
        (que seria o de 6.4.0-150700.51)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._prepara_rpms(tmpdir)
            caminho_certo = os.path.join(
                tmpdir, "amibios-dmi-kmp-default-5.3.18-22.rpm")
            with open(caminho_certo, "rb") as f:
                sha_certo = hashlib.sha256(f.read()).hexdigest()

            def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
                if "osrelease" in cmd:
                    return 0, "5.3.18-22-default\n", ""
                if "sha256sum" in cmd:
                    return 0, sha_certo, ""
                return 0, "", ""

            with mock.patch.object(env, "ssh_run",
                                   side_effect=_fake_ssh_run), \
                 mock.patch.object(env, "_scp_arquivo_com_erro",
                                   return_value=(True, "")) as m_scp, \
                 mock.patch.object(env, "verifica_pacote_rpm_remoto",
                                   return_value=True), \
                 mock.patch.object(env, "gravar_log_remoto"):
                sucesso, detalhe = env.instala_modulo_remoto(
                    "192.0.2.1", "u", "sudo", tmpdir,
                    "amibios-dmi-kmp-default", "amibios-dmi",
                    "", False, False, "")

            self.assertTrue(sucesso, detalhe)
            caminho_copiado = m_scp.call_args[0][2]
            self.assertIn("5.3.18-22", os.path.basename(caminho_copiado))

    def test_nenhum_kmp_bate_retorna_marcador(self):
        """Kernel sem candidato compativel na pasta deve retornar o
        marcador de kernel incompativel, sem tentar scp/zypper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._prepara_rpms(tmpdir)

            def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
                if "osrelease" in cmd:
                    return 0, "9.9.9-1-default\n", ""
                return 0, "", ""

            with mock.patch.object(env, "ssh_run",
                                   side_effect=_fake_ssh_run), \
                 mock.patch.object(env, "_scp_arquivo_com_erro") as m_scp, \
                 mock.patch.object(env, "gravar_log_remoto"):
                sucesso, detalhe = env.instala_modulo_remoto(
                    "192.0.2.1", "u", "sudo", tmpdir,
                    "amibios-dmi-kmp-default", "amibios-dmi",
                    "", False, False, "")

            self.assertFalse(sucesso)
            self.assertIn("KMP-KERNEL-MISMATCH", detalhe)
            m_scp.assert_not_called()

    def test_nao_cruza_versoes_com_prefixo_comum(self):
        """Fragilidade latente apontada em revisao (2026-07-20): o
        matching antigo era por substring ('kernel_base in nome'), que
        cruzaria erroneamente kernel '5.3.18-22' com um arquivo
        '...-5.3.18-220.rpm' (prefixo em comum). Comparacao agora e por
        IGUALDADE do nome completo do arquivo, entao so o candidato
        exato deve ser escolhido, mesmo com um 'quase-igual' na pasta."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nomes = [
                "amibios-dmi-kmp-default-5.3.18-22.rpm",
                "amibios-dmi-kmp-default-5.3.18-220.rpm",
            ]
            for n in nomes:
                with open(os.path.join(tmpdir, n), "wb") as f:
                    f.write(b"fake")
            caminho_certo = os.path.join(tmpdir, nomes[0])
            with open(caminho_certo, "rb") as f:
                sha_certo = hashlib.sha256(f.read()).hexdigest()

            def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
                if "osrelease" in cmd:
                    return 0, "5.3.18-22-default\n", ""
                if "sha256sum" in cmd:
                    return 0, sha_certo, ""
                return 0, "", ""

            with mock.patch.object(env, "ssh_run",
                                   side_effect=_fake_ssh_run), \
                 mock.patch.object(env, "_scp_arquivo_com_erro",
                                   return_value=(True, "")) as m_scp, \
                 mock.patch.object(env, "verifica_pacote_rpm_remoto",
                                   return_value=True), \
                 mock.patch.object(env, "gravar_log_remoto"):
                sucesso, detalhe = env.instala_modulo_remoto(
                    "192.0.2.1", "u", "sudo", tmpdir,
                    "amibios-dmi-kmp-default", "amibios-dmi",
                    "", False, False, "")

            self.assertTrue(sucesso, detalhe)
            caminho_copiado = m_scp.call_args[0][2]
            self.assertEqual(os.path.basename(caminho_copiado), nomes[0])

    def test_zypper_falha_usa_fallback_rpm_nodeps(self):
        """BUG REAL de campo (2026-07-22, host 10.124.60.133): um servico
        zypper corporativo quebrado no host fazia QUALQUER comando zypper
        falhar (mesmo sem relacao com o RPM/KMP em si). Kernel ja bate
        exatamente com o KMP nesse ponto, entao instala_modulo_remoto deve
        cair para 'rpm -i --nodeps' e ainda assim ter sucesso."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._prepara_rpms(tmpdir)
            caminho_certo = os.path.join(
                tmpdir, "amibios-dmi-kmp-default-5.3.18-22.rpm")
            with open(caminho_certo, "rb") as f:
                sha_certo = hashlib.sha256(f.read()).hexdigest()

            def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
                if "osrelease" in cmd:
                    return 0, "5.3.18-22-default\n", ""
                if "sha256sum" in cmd:
                    return 0, sha_certo, ""
                if "zypper" in cmd:
                    return 1, "", "Repository already exists."
                if "rpm -i --nodeps" in cmd:
                    return 0, "", ""
                return 0, "", ""

            with mock.patch.object(env, "ssh_run",
                                   side_effect=_fake_ssh_run), \
                 mock.patch.object(env, "_scp_arquivo_com_erro",
                                   return_value=(True, "")), \
                 mock.patch.object(env, "verifica_pacote_rpm_remoto",
                                   return_value=True), \
                 mock.patch.object(env, "gravar_log_remoto"):
                sucesso, detalhe = env.instala_modulo_remoto(
                    "192.0.2.1", "u", "sudo", tmpdir,
                    "amibios-dmi-kmp-default", "amibios-dmi",
                    "", False, False, "")

            self.assertTrue(sucesso, detalhe)

    def test_instalacao_bem_sucedida_roda_depmod(self):
        """BUG REAL de campo (2026-07-22): mesmo com o pacote confirmado
        instalado, o modprobe seguinte falhava com 'Module not found' em
        hosts sem 'suse-kernel-rpm-scriptlets' (o cache do depmod nunca
        era atualizado). instala_modulo_remoto deve rodar 'depmod -a'
        explicitamente apos confirmar a instalacao, sem depender desse
        pacote estar presente no host."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._prepara_rpms(tmpdir)
            caminho_certo = os.path.join(
                tmpdir, "amibios-dmi-kmp-default-5.3.18-22.rpm")
            with open(caminho_certo, "rb") as f:
                sha_certo = hashlib.sha256(f.read()).hexdigest()

            def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
                if "osrelease" in cmd:
                    return 0, "5.3.18-22-default\n", ""
                if "sha256sum" in cmd:
                    return 0, sha_certo, ""
                return 0, "", ""

            with mock.patch.object(env, "ssh_run",
                                   side_effect=_fake_ssh_run) as m_ssh, \
                 mock.patch.object(env, "_scp_arquivo_com_erro",
                                   return_value=(True, "")), \
                 mock.patch.object(env, "verifica_pacote_rpm_remoto",
                                   return_value=True), \
                 mock.patch.object(env, "gravar_log_remoto"):
                sucesso, detalhe = env.instala_modulo_remoto(
                    "192.0.2.1", "u", "sudo", tmpdir,
                    "amibios-dmi-kmp-default", "amibios-dmi",
                    "", False, False, "")

            self.assertTrue(sucesso, detalhe)
            comandos = [c[0][2] for c in m_ssh.call_args_list]
            self.assertTrue(any("depmod -a" in c for c in comandos))

    def test_zypper_e_fallback_rpm_falham_retorna_falso(self):
        """Se o fallback 'rpm -i --nodeps' tambem falhar, o resultado
        final deve ser falha (nao mascarar o problema real do host)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._prepara_rpms(tmpdir)
            caminho_certo = os.path.join(
                tmpdir, "amibios-dmi-kmp-default-5.3.18-22.rpm")
            with open(caminho_certo, "rb") as f:
                sha_certo = hashlib.sha256(f.read()).hexdigest()

            def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
                if "osrelease" in cmd:
                    return 0, "5.3.18-22-default\n", ""
                if "sha256sum" in cmd:
                    return 0, sha_certo, ""
                if "zypper" in cmd:
                    return 1, "", "Repository already exists."
                if "rpm -i --nodeps" in cmd:
                    return 1, "", "erro generico do rpm"
                return 0, "", ""

            with mock.patch.object(env, "ssh_run",
                                   side_effect=_fake_ssh_run), \
                 mock.patch.object(env, "_scp_arquivo_com_erro",
                                   return_value=(True, "")), \
                 mock.patch.object(env, "gravar_log_remoto"):
                sucesso, detalhe = env.instala_modulo_remoto(
                    "192.0.2.1", "u", "sudo", tmpdir,
                    "amibios-dmi-kmp-default", "amibios-dmi",
                    "", False, False, "")

            self.assertFalse(sucesso)


class TestConfirmaKmpKernelCorretoRemoto(unittest.TestCase):
    """Regressao para bug real de campo (2026-07-22, host 10.124.60.133):
    um KMP compilado para o kernel ERRADO ficou instalado no alvo apos um
    fallback bem-sucedido; como 'rpm -q' so confere o nome do pacote,
    execucoes seguintes viam 'ja instalado' para sempre e nunca tentavam
    reinstalar o KMP certo, so o modprobe (que falhava indefinidamente)."""

    def test_pacote_ausente_retorna_falso_sem_desinstalar(self):
        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            if "rpm -q" in cmd:
                return 1, "", ""
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run) as m_ssh, \
             mock.patch.object(env, "gravar_log_remoto"):
            resultado = env.confirma_kmp_kernel_correto_remoto(
                "192.0.2.1", "u", "sudo", "amibios-dmi-kmp-default",
                "", False, False, "")

        self.assertFalse(resultado)
        for chamada in m_ssh.call_args_list:
            self.assertNotIn("rpm -e", chamada.args[2] if len(chamada.args) > 2 else "")

    def test_pacote_kernel_errado_desinstala_e_retorna_falso(self):
        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            if "rpm -q" in cmd:
                return 0, "1.0.0_k4.4.90_92.50", ""
            if "osrelease" in cmd:
                return 0, "4.4.74-92.38-default\n", ""
            if "rpm -e" in cmd:
                return 0, "", ""
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run) as m_ssh, \
             mock.patch.object(env, "gravar_log_remoto"):
            resultado = env.confirma_kmp_kernel_correto_remoto(
                "192.0.2.1", "u", "sudo", "amibios-dmi-kmp-default",
                "", False, False, "")

        self.assertFalse(resultado)
        comandos = [c[0][2] for c in m_ssh.call_args_list]
        self.assertTrue(any("rpm -e" in c for c in comandos))

    def test_pacote_kernel_correto_retorna_verdadeiro_sem_desinstalar(self):
        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            if "rpm -q" in cmd:
                return 0, "1.0.0_k4.4.74_92.38", ""
            if "osrelease" in cmd:
                return 0, "4.4.74-92.38-default\n", ""
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run) as m_ssh, \
             mock.patch.object(env, "gravar_log_remoto"):
            resultado = env.confirma_kmp_kernel_correto_remoto(
                "192.0.2.1", "u", "sudo", "amibios-dmi-kmp-default",
                "", False, False, "")

        self.assertTrue(resultado)
        comandos = [c[0][2] for c in m_ssh.call_args_list]
        self.assertFalse(any("rpm -e" in c for c in comandos))

class TestConfirmaKmpKernelCorretoRemotoFormatoOBS(unittest.TestCase):
    """Regressao para bug real de campo (2026-07-22, hosts .96/.117/.145):
    o regex de confirma_kmp_kernel_correto_remoto era ancorado em
    '1.0.0_k...' (formato dos builds manuais via build_sp.sh) e nao
    reconhecia '1.0.0+git<data>_k...' (formato dos builds publicados via
    OBS), caindo sempre no ramo 'formato inesperado' e pulando a
    confirmacao de kernel de verdade (assumia correto sem checar)."""

    def test_versao_obs_com_kernel_correto_retorna_verdadeiro(self):
        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            if "rpm -q" in cmd:
                return 0, "1.0.0+git20260602_k6.4.0_150700.51", ""
            if "osrelease" in cmd:
                return 0, "6.4.0-150700.51-default\n", ""
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run) as m_ssh, \
             mock.patch.object(env, "gravar_log_remoto"):
            resultado = env.confirma_kmp_kernel_correto_remoto(
                "192.0.2.1", "u", "sudo", "amibios-dmi-kmp-default",
                "", False, False, "")

        self.assertTrue(resultado)
        comandos = [c[0][2] for c in m_ssh.call_args_list]
        self.assertFalse(any("rpm -e" in c for c in comandos))

    def test_versao_obs_com_kernel_errado_desinstala_e_retorna_falso(self):
        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            if "rpm -q" in cmd:
                return 0, "1.0.0+git20260602_k6.4.0_150700.51", ""
            if "osrelease" in cmd:
                return 0, "5.14.21-150500.55.19-default\n", ""
            if "rpm -e" in cmd:
                return 0, "", ""
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run) as m_ssh, \
             mock.patch.object(env, "gravar_log_remoto"):
            resultado = env.confirma_kmp_kernel_correto_remoto(
                "192.0.2.1", "u", "sudo", "amibios-dmi-kmp-default",
                "", False, False, "")

        self.assertFalse(resultado)
        comandos = [c[0][2] for c in m_ssh.call_args_list]
        self.assertTrue(any("rpm -e" in c for c in comandos))


class TestInstalaModuloRemotoRemovePreExistente(unittest.TestCase):
    """Regressao para bug real de campo (2026-07-22, host 10.124.60.133):
    o pacote userspace 'amibios-dmi' de um build de outra SP ja estava
    instalado e bloqueava tanto o zypper install quanto o fallback
    'rpm -i --nodeps' (mesmo NOME+ARQUITETURA, release diferente, sem
    --replacepkgs o rpm recusa). instala_modulo_remoto agora remove
    qualquer pacote pre-existente (KMP e userspace) antes de instalar."""

    def _prepara_rpms(self, tmpdir):
        with open(os.path.join(tmpdir,
                                "amibios-dmi-kmp-default-5.3.18-22.rpm"),
                  "wb") as f:
            f.write(b"conteudo-fake-rpm")

    def test_remove_pacote_userspace_pre_existente_antes_de_instalar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._prepara_rpms(tmpdir)
            caminho_certo = os.path.join(
                tmpdir, "amibios-dmi-kmp-default-5.3.18-22.rpm")
            with open(caminho_certo, "rb") as f:
                sha_certo = hashlib.sha256(f.read()).hexdigest()

            def _fake_verifica_pacote(ip, ssh_user, sudo_cmd, nome_pacote,
                                       *a, **kw):
                # So o pacote userspace ja esta presente (build errado);
                # o KMP nao. Apos a instalacao, ambos devem constar
                # instalados (segunda chamada, para o KMP, no final).
                return nome_pacote == "amibios-dmi"

            def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
                if "osrelease" in cmd:
                    return 0, "5.3.18-22-default\n", ""
                if "sha256sum" in cmd:
                    return 0, sha_certo, ""
                return 0, "", ""

            with mock.patch.object(env, "ssh_run",
                                   side_effect=_fake_ssh_run) as m_ssh, \
                 mock.patch.object(env, "_scp_arquivo_com_erro",
                                   return_value=(True, "")), \
                 mock.patch.object(env, "verifica_pacote_rpm_remoto",
                                   side_effect=_fake_verifica_pacote), \
                 mock.patch.object(env, "gravar_log_remoto"):
                sucesso, detalhe = env.instala_modulo_remoto(
                    "192.0.2.1", "u", "sudo", tmpdir,
                    "amibios-dmi-kmp-default", "amibios-dmi",
                    "", False, False, "")

            # A segunda chamada a verifica_pacote_rpm_remoto (a de
            # confirmacao final, so para module_package) faz o mock
            # retornar False para o KMP -- mas o teste real e que a
            # remocao do userspace foi tentada antes do zypper install.
            comandos = [c[0][2] for c in m_ssh.call_args_list]
            idx_remove = next(
                (i for i, c in enumerate(comandos) if "remove" in c and
                 "amibios-dmi" in c and "kmp" not in c), None)
            idx_install = next(
                (i for i, c in enumerate(comandos) if "install" in c), None)
            self.assertIsNotNone(idx_remove, "zypper remove nao foi chamado")
            self.assertIsNotNone(idx_install, "zypper install nao foi chamado")
            self.assertLess(idx_remove, idx_install,
                             "remocao do pacote pre-existente deve ocorrer "
                             "antes da instalacao")


class TestDesinstalaModuloRemoto(unittest.TestCase):
    """Cobertura da nova funcao desinstala_modulo_remoto: alvo deve voltar
    ao estado anterior a esta execucao quando fomos nos que instalamos o
    KMP/userspace (ver bios_sysfs.py, pacote_instalado_pelo_script)."""

    def test_zypper_remove_bem_sucedido_retorna_verdadeiro(self):
        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run) as m_ssh, \
             mock.patch.object(env, "verifica_pacote_rpm_remoto",
                               return_value=False), \
             mock.patch.object(env, "gravar_log_remoto"):
            resultado = env.desinstala_modulo_remoto(
                "192.0.2.1", "u", "sudo", "amibios-dmi-kmp-default",
                "amibios-dmi", "", False, False, "")

        self.assertTrue(resultado)
        comandos = [c[0][2] for c in m_ssh.call_args_list]
        self.assertTrue(any("modprobe -r amibios_dmi" in c for c in comandos))
        self.assertTrue(any("zypper" in c and "remove" in c and
                             "amibios-dmi-kmp-default" in c for c in comandos))
        # v2.3.0: o userspace ausente (verifica_pacote_rpm_remoto False) nao
        # e mais removido; ver TestDesinstalaUserspaceV230.
        self.assertFalse(any("zypper" in c and "remove" in c and
                              c.strip().endswith("amibios-dmi") for c in comandos))

    def test_zypper_falha_usa_fallback_rpm_e_ainda_retorna_verdadeiro(self):
        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            if "zypper" in cmd and "remove" in cmd:
                return 1, "", "Repository already exists."
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run) as m_ssh, \
             mock.patch.object(env, "verifica_pacote_rpm_remoto",
                               return_value=False), \
             mock.patch.object(env, "gravar_log_remoto"):
            resultado = env.desinstala_modulo_remoto(
                "192.0.2.1", "u", "sudo", "amibios-dmi-kmp-default",
                "amibios-dmi", "", False, False, "")

        self.assertTrue(resultado)
        comandos = [c[0][2] for c in m_ssh.call_args_list]
        self.assertTrue(any("rpm -e --nodeps" in c for c in comandos))

    def test_pacote_ainda_instalado_apos_remocao_retorna_falso(self):
        """Se rpm -q ainda confirmar o pacote instalado apos zypper remove
        e o fallback rpm -e, a funcao deve reportar falha (nao mascarar
        residuo no alvo)."""
        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run), \
             mock.patch.object(env, "verifica_pacote_rpm_remoto",
                               return_value=True), \
             mock.patch.object(env, "gravar_log_remoto"):
            resultado = env.desinstala_modulo_remoto(
                "192.0.2.1", "u", "sudo", "amibios-dmi-kmp-default",
                "amibios-dmi", "", False, False, "")

        self.assertFalse(resultado)


class TestPacoteKmpParaKernel(unittest.TestCase):
    """v2.3.0: nome do KMP derivado do flavor do kernel de cada host, para
    um unico lote atender default (SLE 12/15) e pae (SLE 11 32 bits)."""

    def test_flavores_reais_de_campo(self):
        casos = {
            "5.14.21-150500.55.39-default": "amibios-dmi-kmp-default",
            "4.12.14-95.48-default": "amibios-dmi-kmp-default",
            "3.0.101-71-pae": "amibios-dmi-kmp-pae",
            "3.0.101-71-pae\n": "amibios-dmi-kmp-pae",
        }
        for osrelease, esperado in casos.items():
            self.assertEqual(env.pacote_kmp_para_kernel(osrelease), esperado,
                             osrelease)

    def test_kernel_ilegivel_cai_no_padrao_anterior(self):
        for osrelease in ("", None, "DESCONHECIDO", "5.3.18-22-"):
            self.assertEqual(env.pacote_kmp_para_kernel(osrelease),
                             "amibios-dmi-kmp-default", repr(osrelease))


class TestInstalaIgnoraUserspaceV230(unittest.TestCase):
    """Regressao para defeito reproduzido em 2026-09-23 (VM SLE 11 SP4
    i586): o pacote userspace x86_64 na mesma pasta do KMP entrava na mesma
    transacao do zypper; em host de 32 bits a transacao inteira era
    recusada (zypper rc=104 e fallback rpm -i recusando por arquitetura) e
    o KMP nunca era instalado. Desde a v2.3.0 o userspace (so
    documentacao) nao e copiado nem instalado."""

    def test_userspace_na_pasta_nao_entra_na_instalacao(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kmp = os.path.join(tmpdir, "amibios-dmi-kmp-pae-3.0.101-71-pae.rpm")
            doc = os.path.join(tmpdir, "amibios-dmi-1.0.0.rpm")
            for caminho in (kmp, doc):
                with open(caminho, "wb") as f:
                    f.write(b"conteudo-fake-" + caminho.encode())
            with open(kmp, "rb") as f:
                sha_kmp = hashlib.sha256(f.read()).hexdigest()

            def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
                if "osrelease" in cmd:
                    return 0, "3.0.101-71-pae\n", ""
                if "sha256sum" in cmd:
                    return 0, sha_kmp, ""
                return 0, "", ""

            with mock.patch.object(env, "ssh_run",
                                   side_effect=_fake_ssh_run) as m_ssh, \
                 mock.patch.object(env, "_scp_arquivo_com_erro",
                                   return_value=(True, "")) as m_scp, \
                 mock.patch.object(env, "verifica_pacote_rpm_remoto",
                                   side_effect=[False, False, True]), \
                 mock.patch.object(env, "gravar_log_remoto"):
                sucesso, detalhe = env.instala_modulo_remoto(
                    "192.0.2.1", "root", "sudo", tmpdir,
                    "amibios-dmi-kmp-pae", "amibios-dmi",
                    "", False, False, "")

            self.assertTrue(sucesso, detalhe)
            copiados = [os.path.basename(c[0][2]) for c in m_scp.call_args_list]
            self.assertEqual(copiados,
                             ["amibios-dmi-kmp-pae-3.0.101-71-pae.rpm"])
            installs = [c[0][2] for c in m_ssh.call_args_list
                        if "zypper" in c[0][2] and " install " in c[0][2]]
            self.assertEqual(len(installs), 1)
            self.assertNotIn("amibios-dmi-1.0.0", installs[0])


class TestDesinstalaUserspaceV230(unittest.TestCase):
    """Regressao para o ERROR falso no fim de toda execucao bem-sucedida
    (campo, 2026-09-23): a remocao do userspace era sempre tentada, e com
    o pacote ausente o zypper devolvia rc=104 e o rpm -e rc=1."""

    def _roda(self, userspace_presente):
        estado = {"amibios-dmi": userspace_presente}

        def _fake_verifica(ip, ssh_user, sudo_cmd, nome_pacote, *a, **kw):
            return estado.get(nome_pacote, False)

        def _fake_ssh_run(ip, ssh_user, cmd, timeout=10):
            if "remove" in cmd or "rpm -e" in cmd:
                if cmd.strip().endswith(" amibios-dmi"):
                    if not estado["amibios-dmi"]:
                        return (104 if "zypper" in cmd else 1), "", \
                            "package amibios-dmi is not installed"
                    estado["amibios-dmi"] = False
            return 0, "", ""

        with mock.patch.object(env, "ssh_run",
                               side_effect=_fake_ssh_run) as m_ssh, \
             mock.patch.object(env, "verifica_pacote_rpm_remoto",
                               side_effect=_fake_verifica), \
             mock.patch.object(env, "gravar_log_remoto") as m_log:
            resultado = env.desinstala_modulo_remoto(
                "192.0.2.1", "root", "sudo", "amibios-dmi-kmp-pae",
                "amibios-dmi", "", False, False, "")
        comandos = [c[0][2] for c in m_ssh.call_args_list]
        erros = [c for c in m_log.call_args_list if c[0][4] == "ERROR"]
        return resultado, comandos, erros

    def test_userspace_ausente_nao_gera_error(self):
        resultado, comandos, erros = self._roda(userspace_presente=False)
        self.assertTrue(resultado)
        self.assertEqual(erros, [])
        self.assertFalse(any(c.strip().endswith(" amibios-dmi")
                             for c in comandos))

    def test_userspace_presente_de_versao_anterior_e_removido(self):
        """Residuo de execucao de versao anterior continua sendo limpo."""
        resultado, comandos, erros = self._roda(userspace_presente=True)
        self.assertTrue(resultado)
        self.assertEqual(erros, [])
        self.assertTrue(any("zypper" in c and c.strip().endswith(" amibios-dmi")
                            for c in comandos))


if __name__ == "__main__":
    unittest.main(verbosity=2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
