# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: tests/test_bbconfig.py
#
# USAGE: python3 -m unittest discover tests -v
#        (ou, so este arquivo: python3 -m unittest tests.test_bbconfig -v)
#
# DESCRIPTION: Sincronizacao do arquivo de configuracao remoto:
#              tratamento de chattr +i no arquivo original.
#              Roda em qualquer maquina, sem SSH real: tudo que toca
#              rede e mockado via unittest.mock. Nenhuma dependencia
#              alem da stdlib.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.3
# REVISION: 2026-09-28 - v2.3.3 - simulacao aceita o grep -a da leitura e da
#                        confirmacao; TestBbconfigV233 (variavel ausente
#                        acrescentada, chattr +i so depois da confirmacao ou
#                        do rollback, grep -a, execucao real do comando de
#                        acrescimo).
# REVISION: 2026-09-23 - v2.3.0 - c[0][0] no lugar de c.args[0] (call.args
#                        so existe a partir do Python 3.8; no 3.6 do runner
#                        os testes falhavam sem relacao com o codigo).
# CREATED: 2026-08-10
# REVISION: 2026-08-10 - v2.2.9 - arquivo criado a partir da divisao de
#                        tests/test_regressao.py, que havia chegado a
#                        1107 linhas. Os testes sao os mesmos, sem
#                        alteracao de logica; muda so a organizacao,
#                        agora um arquivo por modulo testado.
#
# =======================================================================

import base64
import os
import shutil
import subprocess
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

from update_dmi_tag import bbconfig as bbconfig_mod  # noqa: E402

class TestSincronizaBbconfigLocalChattrOriginal(unittest.TestCase):
    """Regressao para o bug real da v2.2.8 (revisao 2026-07-20):
    sincroniza_bbconfig_local nao tratava chattr +i no arquivo ORIGINAL
    (so no backup), ao contrario de sincroniza_bbconfig_remoto. Confere
    que, com o original imutavel, chattr -i roda antes do sed e chattr +i
    roda depois (restauracao), e que sem imutabilidade nenhum dos dois
    e chamado."""

    def _prepara_arquivo(self, valor_final):
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".conf", delete=False, encoding="utf-8")
        f.write("BEM_NUMERO={}\n".format(valor_final))
        f.close()
        return f.name

    @staticmethod
    def _eh(cmd, *esperado):
        """True se cmd (lista) comeca exatamente com os tokens esperados
        e tem o mesmo comprimento (evita falso-positivo por slicing)."""
        return len(cmd) == len(esperado) and list(cmd) == list(esperado)

    def test_chattr_removido_e_restaurado_quando_original_imutavel(self):
        caminho = self._prepara_arquivo("74171618303986")
        try:
            def fake_run(cmd, **kw):
                if len(cmd) == 5 and cmd[:3] == ["sudo", "cp", "-p"]:
                    return mock.Mock(returncode=0, stdout="", stderr="")
                if len(cmd) == 4 and cmd[:3] == ["sudo", "chattr", "+i"] and cmd[3] != caminho:
                    return mock.Mock(returncode=0, stdout="", stderr="")
                if self._eh(cmd, "lsattr", caminho):
                    return mock.Mock(
                        returncode=0,
                        stdout="----i---------e------- {}".format(caminho),
                        stderr="")
                if self._eh(cmd, "sudo", "chattr", "-i", caminho):
                    return mock.Mock(returncode=0, stdout="", stderr="")
                if len(cmd) == 5 and cmd[:3] == ["sudo", "sed", "-i"]:
                    return mock.Mock(returncode=0, stdout="", stderr="")
                if self._eh(cmd, "sudo", "chattr", "+i", caminho):
                    return mock.Mock(returncode=0, stdout="", stderr="")
                raise AssertionError("comando nao previsto pelo teste: {}".format(cmd))

            with mock.patch.object(bbconfig_mod.subprocess, "run",
                                   side_effect=fake_run) as m:
                resultado = bbconfig_mod.sincroniza_bbconfig_local(
                    caminho, "BEM_NUMERO", "PENDENTE", "74171618303986",
                    "", False, True)

            self.assertEqual(resultado["motivo"], "OK")
            comandos = [list(c[0][0]) for c in m.call_args_list]
            self.assertIn(["sudo", "chattr", "-i", caminho], comandos)
            self.assertIn(["sudo", "chattr", "+i", caminho], comandos)
            idx_remove = comandos.index(["sudo", "chattr", "-i", caminho])
            idx_sed = next(i for i, c in enumerate(comandos)
                          if len(c) == 5 and c[:3] == ["sudo", "sed", "-i"])
            idx_restaura = comandos.index(["sudo", "chattr", "+i", caminho])
            self.assertLess(idx_remove, idx_sed,
                            "chattr -i deve rodar ANTES do sed")
            self.assertLess(idx_sed, idx_restaura,
                            "chattr +i deve rodar DEPOIS do sed")
        finally:
            os.remove(caminho)

    def test_chattr_original_nao_tocado_quando_nao_imutavel(self):
        caminho = self._prepara_arquivo("74171618303986")
        try:
            def fake_run(cmd, **kw):
                if len(cmd) == 5 and cmd[:3] == ["sudo", "cp", "-p"]:
                    return mock.Mock(returncode=0, stdout="", stderr="")
                if len(cmd) == 4 and cmd[:3] == ["sudo", "chattr", "+i"] and cmd[3] != caminho:
                    return mock.Mock(returncode=0, stdout="", stderr="")
                if self._eh(cmd, "lsattr", caminho):
                    # sem o "i" na saida: arquivo NAO imutavel
                    return mock.Mock(
                        returncode=0,
                        stdout="-------------e------- {}".format(caminho),
                        stderr="")
                if len(cmd) == 5 and cmd[:3] == ["sudo", "sed", "-i"]:
                    return mock.Mock(returncode=0, stdout="", stderr="")
                raise AssertionError("comando nao previsto pelo teste: {}".format(cmd))

            with mock.patch.object(bbconfig_mod.subprocess, "run",
                                   side_effect=fake_run) as m:
                resultado = bbconfig_mod.sincroniza_bbconfig_local(
                    caminho, "BEM_NUMERO", "PENDENTE", "74171618303986",
                    "", False, True)

            self.assertEqual(resultado["motivo"], "OK")
            comandos = [list(c[0][0]) for c in m.call_args_list]
            self.assertNotIn(["sudo", "chattr", "-i", caminho], comandos)
            self.assertNotIn(["sudo", "chattr", "+i", caminho], comandos)
        finally:
            os.remove(caminho)

class TestSincronizaBbconfigRemotoFormato(unittest.TestCase):
    """Formato do valor gravado no arquivo de configuracao remoto.

    Esta funcao grava exatamente o valor que recebe: ela NAO normaliza
    nada por conta propria. Quem garante os 14 digitos e o chamador
    (host_processor, que passa tag_esperada desde 2026-08-10; ver
    TestFormatoGravadoNoArquivoDeConfig em tests/test_host_processor.py).
    Os testes abaixo travam esse contrato dos dois lados.

    Importa tambem que a comparacao de 'ja sincronizado' e de string
    pura: 13 e 14 digitos do MESMO numero contam como diferentes e
    disparam reescrita. E por isso que normalizar no chamador elimina
    reescritas causadas so por formato de digito verificador."""

    def _roda(self, bem_conf, bem_usado, arquivo_existe=True):
        """Executa a funcao real com a camada SSH mockada.

        Devolve (resultado, comandos_executados)."""
        comandos = []

        def fake_ssh_run(ip, user, cmd, timeout=30):
            comandos.append(cmd)
            if "test -f" in cmd:
                return (0 if arquivo_existe else 1), "", ""
            if cmd.startswith("lsattr") or " lsattr " in cmd:
                return 0, "---------------- /etc/BBconfig.conf", ""
            if "'^BEM_NUMERO='" in cmd and " -q " not in cmd:
                return 0, bem_usado + "\n", ""
            return 0, "", ""

        with mock.patch.object(bbconfig_mod, "ssh_run",
                               side_effect=fake_ssh_run), \
             mock.patch.object(bbconfig_mod, "gravar_log_remoto"):
            resultado = bbconfig_mod.sincroniza_bbconfig_remoto(
                "192.0.2.1", "testmec3", "sudo", "/etc/BBconfig.conf",
                "BEM_NUMERO", bem_conf, bem_usado, "", "", False, True)
        return resultado, comandos

    @staticmethod
    def _expressao_sed(comandos):
        """Extrai o valor entre aspas da expressao do sed executado."""
        for cmd in comandos:
            if " sed -i " in cmd:
                return cmd
        return ""

    def test_valor_de_13_digitos_e_gravado_com_13(self):
        """Nao ha normalizacao: 13 digitos entram, 13 digitos saem."""
        resultado, comandos = self._roda("PENDENTE", "7417161830398")
        self.assertEqual(resultado["motivo"], "OK")
        self.assertIn('BEM_NUMERO="7417161830398"',
                      self._expressao_sed(comandos))

    def test_valor_de_14_digitos_e_gravado_com_14(self):
        """Com 14 digitos na origem, o arquivo recebe os 14."""
        resultado, comandos = self._roda("PENDENTE", "74171618303986")
        self.assertEqual(resultado["motivo"], "OK")
        self.assertIn('BEM_NUMERO="74171618303986"',
                      self._expressao_sed(comandos))

    def test_mesmo_numero_com_e_sem_dv_nao_conta_como_sincronizado(self):
        """13 no arquivo e 14 em uso: reescreve, nao e considerado igual.

        Comparacao de string pura, entao a mesma base com e sem digito
        verificador dispara uma reescrita do arquivo."""
        resultado, comandos = self._roda("7417161830398", "74171618303986")
        self.assertEqual(resultado["motivo"], "OK")
        self.assertNotEqual(resultado["motivo"], "IGUAL")
        self.assertTrue(self._expressao_sed(comandos))

    def test_valor_identico_nao_toca_no_arquivo(self):
        """Valores exatamente iguais: retorna IGUAL sem executar nada."""
        resultado, comandos = self._roda("74171618303986", "74171618303986")
        self.assertEqual(resultado["motivo"], "IGUAL")
        self.assertTrue(resultado["sincronizado"])
        self.assertIsNone(resultado["backup"])
        self.assertEqual(comandos, [],
                         "nenhum comando deveria ser executado no alvo")

    def test_arquivo_ausente_no_alvo_pula_sincronizacao(self):
        """Sem o arquivo no alvo, nao tenta criar nem falha o host."""
        resultado, _ = self._roda("PENDENTE", "74171618303986",
                                  arquivo_existe=False)
        self.assertEqual(resultado["motivo"], "SEM-ARQUIVO")
        self.assertFalse(resultado["sincronizado"])
        self.assertIsNone(resultado["backup"])


class TestBbconfigV233(unittest.TestCase):
    """v2.3.3, tres defeitos vistos em campo na sincronizacao do arquivo:

    1. variavel ausente: o sed de substituicao nao fazia nada e a
       confirmacao acusava falha (10.216.21.148, 24 e 29/07/2026);
    2. chattr +i do original reaplicado antes da confirmacao: o rollback
       falhava com "Operation not permitted" (mesmo host);
    3. grep sem -a: arquivo com bytes nao texto devolvia "Binary file ...
       matches" como valor (10.121.252.20, 21/09/2026).
    Todos reprovam na v2.3.2."""

    ARQ = "/etc/BBconfig.conf"

    def _roda_remoto(self, bem_usado, existe=True, imutavel=False,
                     confirma=None):
        """Sincronizacao remota com a camada SSH simulada. confirma e o
        valor devolvido pela leitura de confirmacao (padrao: bem_usado)."""
        comandos = []
        if confirma is None:
            confirma = bem_usado

        def fake(ip, user, cmd, timeout=30):
            comandos.append(cmd)
            if "test -f" in cmd:
                return 0, "", ""
            if "lsattr" in cmd:
                attr = "----i----------" if imutavel else "---------------"
                return 0, "{} {}".format(attr, self.ARQ), ""
            if " -q " in cmd and "'^BEM_NUMERO='" in cmd:
                return (0 if existe else 1), "", ""
            if "'^BEM_NUMERO='" in cmd:
                if "grep -a" not in cmd:
                    return 0, "Binary file {} matches".format(self.ARQ), ""
                return 0, confirma + "\n", ""
            return 0, "", ""

        with mock.patch.object(bbconfig_mod, "ssh_run", side_effect=fake), \
             mock.patch.object(bbconfig_mod, "gravar_log_remoto"):
            r = bbconfig_mod.sincroniza_bbconfig_remoto(
                "192.0.2.1", "testmec3", "sudo", self.ARQ, "BEM_NUMERO",
                "PENDENTE", bem_usado, "", "", False, True)
        return r, comandos

    @staticmethod
    def _idx(comandos, trecho):
        return next(i for i, c in enumerate(comandos) if trecho in c)

    @staticmethod
    def _idx_fim(comandos, sufixo):
        return next(i for i, c in enumerate(comandos) if c.endswith(sufixo))

    # ---- defeito 1: variavel ausente
    def test_variavel_ausente_e_acrescentada(self):
        r, cmds = self._roda_remoto("7417161830398", existe=False)
        self.assertEqual(r["motivo"], "OK")
        acrescimo = [c for c in cmds if "base64 -d >> " + self.ARQ in c]
        self.assertEqual(len(acrescimo), 1)
        b64 = base64.b64encode(b'BEM_NUMERO="7417161830398"\n').decode()
        self.assertIn(b64, acrescimo[0])
        self.assertFalse([c for c in cmds if " sed -i " in c],
                         "sem a linha, o sed de substituicao nao e usado")

    def test_variavel_existente_continua_com_sed(self):
        """Regressao: com a linha presente, o caminho e o de sempre."""
        r, cmds = self._roda_remoto("7417161830398", existe=True)
        self.assertEqual(r["motivo"], "OK")
        self.assertTrue([c for c in cmds if " sed -i " in c])
        self.assertFalse([c for c in cmds if "base64 -d" in c])

    # ---- defeito 2: ordem do chattr
    def test_imutavel_rollback_antes_de_reaplicar_chattr(self):
        r, cmds = self._roda_remoto("7417161830398", imutavel=True,
                                    confirma="outro")
        self.assertEqual(r["motivo"], "FALHOU-confirmacao-rollback-ok")
        i_restaura = self._idx(cmds, "cp -p /etc/BBconfig.conf.")
        i_chattr = self._idx_fim(cmds, "chattr +i " + self.ARQ)
        self.assertLess(i_restaura, i_chattr,
                        "o rollback precisa acontecer com o arquivo liberado")

    def test_imutavel_sucesso_chattr_depois_da_confirmacao(self):
        r, cmds = self._roda_remoto("7417161830398", imutavel=True)
        self.assertEqual(r["motivo"], "OK")
        i_conf = max(i for i, c in enumerate(cmds)
                     if "'^BEM_NUMERO='" in c and " -q " not in c)
        i_chattr = self._idx_fim(cmds, "chattr +i " + self.ARQ)
        self.assertLess(i_conf, i_chattr)
        self.assertEqual(
            sum(1 for c in cmds if c.endswith("chattr +i " + self.ARQ)), 1,
            "o atributo volta uma unica vez")

    def test_nao_imutavel_nao_reaplica_chattr(self):
        """Colisao: arquivo sem +i nao ganha o atributo."""
        r, cmds = self._roda_remoto("7417161830398", imutavel=False)
        self.assertEqual(r["motivo"], "OK")
        self.assertFalse([c for c in cmds if c.endswith("chattr +i " + self.ARQ)])

    # ---- defeito 3: grep -a
    def test_confirmacao_usa_grep_a(self):
        """A simulacao devolve 'Binary file' a quem nao usa -a."""
        r, _ = self._roda_remoto("7417161830398")
        self.assertEqual(r["motivo"], "OK")

    def test_leitura_remota_usa_grep_a(self):
        def fake(ip, user, cmd, timeout=30):
            if "grep -a" not in cmd:
                return 0, "Binary file /etc/BBconfig.conf matches", ""
            return 0, "7417161830398", ""
        with mock.patch.object(bbconfig_mod, "ssh_run", side_effect=fake), \
             mock.patch.object(bbconfig_mod, "gravar_log_remoto"):
            v = bbconfig_mod.le_valor_configuracao_remoto(
                "192.0.2.1", "testmec3", self.ARQ, "BEM_NUMERO", "", "",
                False, True, "sudo")
        self.assertEqual(v, "7417161830398")

    # ---- execucao real do comando de acrescimo (fato observavel)
    def _executa_acrescimo(self, conteudo_inicial):
        sh = shutil.which("sh") or shutil.which("bash")
        if not sh or not shutil.which("base64") or not shutil.which("tail"):
            self.skipTest("sh, base64 ou tail indisponivel nesta maquina")
        f = tempfile.NamedTemporaryFile("wb", suffix=".conf", delete=False)
        f.write(conteudo_inicial)
        f.close()
        caminho = f.name.replace("\\", "/")

        def fake(ip, user, cmd, timeout=30):
            if "test -f" in cmd or "lsattr" in cmd:
                return 0, "", ""
            if " -q " in cmd:
                return 1, "", ""
            if "base64 -d" in cmd:
                p = subprocess.run([sh, "-c", cmd.strip()],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
                return p.returncode, "", p.stderr.decode("utf-8", "replace")
            if "'^BEM_NUMERO='" in cmd:
                with open(f.name, "rb") as g:
                    for linha in g.read().decode().splitlines():
                        if linha.startswith("BEM_NUMERO="):
                            return 0, linha.split("=", 1)[1].strip('"'), ""
                return 1, "", ""
            return 0, "", ""
        try:
            with mock.patch.object(bbconfig_mod, "ssh_run", side_effect=fake), \
                 mock.patch.object(bbconfig_mod, "gravar_log_remoto"):
                r = bbconfig_mod.sincroniza_bbconfig_remoto(
                    "192.0.2.1", "testmec3", "", caminho, "BEM_NUMERO",
                    "PENDENTE", "7417161830398", "", "", False, True)
            with open(f.name, "rb") as g:
                return r, g.read()
        finally:
            os.remove(f.name)

    def test_real_arquivo_sem_quebra_final(self):
        """Adverso: ultima linha sem quebra nao pode ser colada a nova."""
        r, final = self._executa_acrescimo(b'PERFIL="TAA"')
        self.assertEqual(r["motivo"], "OK")
        self.assertEqual(final, b'PERFIL="TAA"\nBEM_NUMERO="7417161830398"\n')

    def test_real_arquivo_com_quebra_final(self):
        r, final = self._executa_acrescimo(b'PERFIL="TAA"\n')
        self.assertEqual(r["motivo"], "OK")
        self.assertEqual(final, b'PERFIL="TAA"\nBEM_NUMERO="7417161830398"\n')

    def test_real_arquivo_vazio(self):
        r, final = self._executa_acrescimo(b"")
        self.assertEqual(r["motivo"], "OK")
        self.assertEqual(final, b'BEM_NUMERO="7417161830398"\n')

    # ---- modo local (standalone): mesma ordem do chattr
    def test_local_imutavel_rollback_antes_de_reaplicar_chattr(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False,
                                        encoding="utf-8")
        f.write('BEM_NUMERO="1111111111111"\n')
        f.close()
        caminho = f.name
        cmds = []

        def fake_run(cmd, **kw):
            cmds.append(list(cmd))
            if list(cmd) == ["lsattr", caminho]:
                return mock.Mock(returncode=0,
                                 stdout="----i------ {}".format(caminho),
                                 stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")
        try:
            with mock.patch.object(bbconfig_mod.subprocess, "run",
                                   side_effect=fake_run):
                r = bbconfig_mod.sincroniza_bbconfig_local(
                    caminho, "BEM_NUMERO", "1111111111111", "7417161830398",
                    "", False, True)
        finally:
            os.remove(caminho)
        self.assertEqual(r["motivo"], "FALHOU-confirmacao-rollback-ok")
        i_restaura = next(i for i, c in enumerate(cmds)
                          if c[:3] == ["sudo", "cp", "-p"] and c[4] == caminho)
        i_chattr = next(i for i, c in enumerate(cmds)
                        if c == ["sudo", "chattr", "+i", caminho])
        self.assertLess(i_restaura, i_chattr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
