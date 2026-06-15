# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: bios_amidelnx.py
#
# DESCRIPTION: Mecanismo 1 de gravacao do DMI Asset Tag: binario AMI
#              amidelnx_64. _parse_resultado_amide interpreta a saida do
#              binario (sucesso "Done" ou "NNN - Error: ..."). 
#              executa_amidelnx_local roda no proprio equipamento (modo
#              standalone). executa_amidelnx_remoto roda via SSH,
#              garantindo o binario no host remoto (scp automatico via
#              garante_amidelnx_remoto, em ssh_utils.py) antes de
#              executar.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.0
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.0 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
#
# =======================================================================

import os
import subprocess

from .constants import MecanismoIndisponivelError
from .logging_utils import gravar_log, gravar_log_remoto
from .ssh_utils import ssh_run, garante_amidelnx_remoto


def _parse_resultado_amide(stdout, stderr):
    """
    NAME: _parse_resultado_amide
    DESCRIPTION: Interpreta a saida do amidelnx_64 e determina se a
                 operacao foi bem-sucedida. A saida esperada de sucesso
                 contem a palavra "Done". Erros aparecem no formato
                 "N - Error: mensagem". Retorna tupla (sucesso, detalhe).
    PARAMETER: stdout - saida padrao do processo amidelnx_64
               stderr - saida de erro do processo
    RETURNS: tuple(bool, str) -- (sucesso, mensagem_de_detalhe)
    """
    saida_completa = (stdout + " " + stderr).strip()

    if "Done" in stdout:
        # Extrai a linha de confirmacao para o log
        for linha in stdout.splitlines():
            if "Done" in linha:
                return True, linha.strip()
        return True, "Done"

    # Tenta extrair mensagem de erro estruturada "N - Error: ..."
    for linha in (stdout + stderr).splitlines():
        if "Error:" in linha:
            return False, linha.strip()

    if saida_completa:
        return False, saida_completa[:120]
    return False, "Sem saida do binario"


def executa_amidelnx_local(tag, caminho_amide, sudo_cmd_lista,
                            caminho_log, verbose, suprime_tela,
                            dry_run=True, caminho_log_local=""):
    """
    NAME: executa_amidelnx_local
    DESCRIPTION: Executa o amidelnx_64 localmente para gravar a asset tag.
                 Verifica existencia e permissao do binario antes de
                 executar. Em dry_run, apenas loga o que seria feito.
                 Levanta MecanismoIndisponivelError se o binario nao
                 existir ou nao for executavel.
    PARAMETER: tag               - valor de 14 digitos a gravar
               caminho_amide     - caminho do binario amidelnx_64
               sudo_cmd_lista    - lista de strings do prefixo sudo
                                   ex: ["sudo"] ou ["sudo", "-S"]
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               dry_run           - se True, nao executa a gravacao
               caminho_log_local - log consolidado (opcional)
    RETURNS: bool -- True se a gravacao foi bem-sucedida
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    if not os.path.isfile(caminho_amide):
        raise MecanismoIndisponivelError(
            "amidelnx_64 nao encontrado em: {}".format(caminho_amide))

    if not os.access(caminho_amide, os.X_OK):
        raise MecanismoIndisponivelError(
            "amidelnx_64 sem permissao de execucao: {}".format(caminho_amide))

    if dry_run:
        _log("WARNING",
             "[DRY-RUN] amidelnx_64: valor que seria gravado: '{}'".format(tag))
        _log("WARNING",
             "[DRY-RUN] Para gravar, passe a flag -w ou --write.")
        return False

    _log("INFO", "Mecanismo 1: executando amidelnx_64 /ca {}".format(tag))
    try:
        cmd = sudo_cmd_lista + [caminho_amide, "/ca", tag]
        resultado = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=30,
        )
        sucesso, detalhe = _parse_resultado_amide(
            resultado.stdout, resultado.stderr)
        if sucesso:
            _log("INFO", "amidelnx_64: gravacao confirmada -- {}".format(detalhe))
            return True
        _log("ERROR", "amidelnx_64: falha -- {}".format(detalhe))
        return False
    except subprocess.TimeoutExpired:
        _log("ERROR", "amidelnx_64: timeout (30s) durante execucao")
        return False
    except Exception as e:
        _log("ERROR", "amidelnx_64: excecao ao executar -- {}".format(e))
        return False


def executa_amidelnx_remoto(ip, ssh_user, sudo_cmd, tag,
                             caminho_amide_remoto, caminho_amide_local,
                             caminho_log, caminho_log_local,
                             verbose, suprime_tela, dry_run=True,
                             amide_repo_url="", amide_package=""):
    """
    NAME: executa_amidelnx_remoto
    DESCRIPTION: Garante a presenca do amidelnx_64 no host remoto (scp se
                 ausente), executa a gravacao via SSH e interpreta o
                 resultado. Em dry_run, apenas loga o que seria feito.
                 Levanta MecanismoIndisponivelError se o binario nao puder
                 ser disponibilizado no alvo.
    PARAMETER: ip                 - endereco IP do host remoto
               ssh_user           - usuario SSH
               sudo_cmd           - prefixo sudo no host remoto (string)
               tag                - valor de 14 digitos a gravar
               caminho_amide_remoto - caminho do binario no alvo
               caminho_amide_local  - caminho local para scp
               caminho_log        - log remoto
               caminho_log_local  - log consolidado local
               verbose            - modo verbose
               suprime_tela       - suprime stdout
               dry_run            - se True, nao executa a gravacao
               amide_repo_url     - repo zypper (reservado para uso futuro)
               amide_package      - pacote zypper (reservado para uso futuro)
    RETURNS: bool -- True se a gravacao foi bem-sucedida
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    # Garante binario no alvo (verifica + scp se necessario)
    disponivel = garante_amidelnx_remoto(
        ip, ssh_user, sudo_cmd,
        caminho_amide_remoto, caminho_amide_local,
        caminho_log, caminho_log_local, verbose, suprime_tela,
    )
    if not disponivel:
        raise MecanismoIndisponivelError(
            "amidelnx_64 indisponivel no alvo {} e scp falhou".format(ip))

    if dry_run:
        _log("WARNING",
             "[DRY-RUN] amidelnx_64 remoto: valor que seria gravado: '{}'".format(tag))
        _log("WARNING",
             "[DRY-RUN] Para gravar, passe a flag -w ou --write.")
        return False

    _log("INFO", "Mecanismo 1: executando amidelnx_64 /ca {} em {}".format(tag, ip))

    cmd_remoto = "{} {} /ca {}".format(sudo_cmd, caminho_amide_remoto, tag)
    rc, stdout, stderr = ssh_run(ip, ssh_user, cmd_remoto, timeout=30)

    sucesso, detalhe = _parse_resultado_amide(stdout, stderr)
    if sucesso:
        _log("INFO", "amidelnx_64: gravacao confirmada -- {}".format(detalhe))
        return True

    _log("ERROR", "amidelnx_64: falha (rc={}) -- {}".format(rc, detalhe))
    return False

