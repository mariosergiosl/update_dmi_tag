# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: logging_utils.py
#
# DESCRIPTION: Funcoes de gravacao de log usadas em todo o pacote.
#              gravar_log escreve no log principal (standalone ou
#              remoto-do-host) e opcionalmente no log local consolidado.
#              gravar_log_remoto e a variante usada no modo remoto, que
#              prefixa cada linha do log local consolidado com [IP] e
#              executa o comando de log no host remoto via SSH.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.0
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.0 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico.
#
# =======================================================================

import os
import subprocess
import sys
import time

from .constants import SSH_OPTS


def gravar_log(
    caminho_log,
    nivel,
    mensagem,
    verbose,
    suprime_tela,
    caminho_log_local="",
):
    """
    NAME: gravar_log
    DESCRIPTION: Escreve mensagem de log estruturada com timestamp.
                 Ignora silenciosamente se caminho_log for vazio ou None.
                 Se caminho_log_local for fornecido, grava tambem no
                 log local consolidado.
    PARAMETER: caminho_log       - caminho do log principal (vazio = ignorar)
               nivel             - INFO / WARNING / ERROR / DEBUG
               mensagem          - texto da mensagem
               verbose           - se True, imprime no stdout
               suprime_tela      - se True, bloqueia impressao
               caminho_log_local - log consolidado secundario (opcional)
    RETURNS: None
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    linha_log = "{} - {} - {}\n".format(timestamp, nivel, mensagem)

    # Grava no log principal -- ignora se caminho vazio ou None
    if caminho_log:
        try:
            diretorio_log = os.path.dirname(caminho_log)
            if diretorio_log and not os.path.exists(diretorio_log):
                os.makedirs(diretorio_log, exist_ok=True)
            with open(caminho_log, "a", encoding="utf-8") as f:
                f.write(linha_log)
        except Exception as e:
            sys.stderr.write("Erro ao gravar log em {}: {}\n".format(
                caminho_log, e))

    # Grava no log local consolidado se fornecido
    if caminho_log_local:
        try:
            with open(caminho_log_local, "a", encoding="utf-8") as f:
                f.write(linha_log)
        except Exception as e:
            sys.stderr.write("Erro ao gravar log local em {}: {}\n".format(
                caminho_log_local, e))

    # Imprime no stdout se verbose e nao suprimido
    if verbose and not suprime_tela:
        sys.stdout.write(linha_log)




def gravar_log_remoto(
    ip,
    ssh_user,
    sudo_cmd,
    caminho_log_remoto,
    nivel,
    mensagem,
    caminho_log_local,
    verbose,
    suprime_tela,
):
    """
    NAME: gravar_log_remoto
    DESCRIPTION: Grava uma linha de log no arquivo de log do host remoto via
                 SSH, e simultaneamente no log local consolidado e no stdout
                 (se verbose). Falhas de escrita remota sao logadas apenas
                 localmente, sem abortar o fluxo.
    PARAMETER: ip                 - endereco IP do host remoto
               ssh_user           - usuario SSH
               sudo_cmd           - prefixo sudo (ex: "sudo" ou "echo X | sudo -S")
               caminho_log_remoto - caminho do log no host remoto
               nivel              - INFO / WARNING / ERROR / DEBUG
               mensagem           - texto da mensagem
               caminho_log_local  - log consolidado local
               verbose            - se True, imprime no stdout
               suprime_tela       - se True, bloqueia impressao
    RETURNS: None
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    # Prefixo com IP para identificar o host no log local consolidado
    linha_local  = "{} - [{}] - {} - {}\n".format(timestamp, ip, nivel, mensagem)
    linha_remota = "{} - {} - {}\n".format(timestamp, nivel, mensagem)

    # Grava no log local consolidado
    if caminho_log_local:
        try:
            with open(caminho_log_local, "a", encoding="utf-8") as f:
                f.write(linha_local)
        except Exception as e:
            sys.stderr.write("Erro ao gravar log local: {}\n".format(e))

    # Grava no log remoto via SSH
    try:
        linha_escapada = linha_remota.replace("'", "'\\''")
        diretorio_remoto = "/var/log"
        cmd_remoto = (
            "{sudo} mkdir -p {dir} 2>/dev/null; "
            "echo '{linha}' | {sudo} tee -a {log} > /dev/null"
        ).format(
            sudo=sudo_cmd,
            dir=diretorio_remoto,
            linha=linha_escapada.rstrip("\n"),
            log=caminho_log_remoto,
        )
        subprocess.run(
            ["ssh"] + SSH_OPTS + ["{}@{}".format(ssh_user, ip), cmd_remoto],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except Exception as e:
        if caminho_log_local:
            try:
                with open(caminho_log_local, "a", encoding="utf-8") as f:
                    f.write("{} - [{}] - WARNING - Falha ao gravar log remoto: {}\n".format(
                        timestamp, ip, e))
            except Exception:
                pass

    # Imprime no stdout se verbose e nao suprimido
    if verbose and not suprime_tela:
        sys.stdout.write(linha_local)

