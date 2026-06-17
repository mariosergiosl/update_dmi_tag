# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: ssh_utils.py
#
# DESCRIPTION: Utilitarios SSH/SCP do fluxo principal (apos o bootstrap
#              de autenticacao). ssh_run executa comandos remotos com
#              BatchMode=yes; testa_conexao_ssh confere acesso; scp_arquivo
#              e _scp_arquivo_com_erro copiam arquivos (a segunda retorna
#              o stderr em falhas); _filtra_banner remove o banner
#              corporativo da saida de comandos sudo; detecta_sudo
#              identifica se o sudo do host exige senha; e
#              garante_amidelnx_remoto verifica/copia o binario
#              amidelnx_64 para o host remoto.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.1.8
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
# REVISION: 2026-06-15 - v2.1.5 - detecta_sudo passa a retornar tupla
#                        (prefixo_sudo, confirmado) em vez de so a
#                        string do prefixo. confirmado=False quando
#                        sudo -n falha E sudo -S tambem falha (ou
#                        --sudo-pass nao foi fornecido). Permite ao
#                        chamador (host_processor) detectar a ausencia
#                        de privilegio e logar/abortar adequadamente
#                        em vez de tentar gravar sem permissao.
#
# =======================================================================

import os
import subprocess

from .constants import SSH_OPTS
from .logging_utils import gravar_log_remoto


def ssh_run(ip, ssh_user, comando, timeout=30):
    """
    NAME: ssh_run
    DESCRIPTION: Executa um comando no host remoto via SSH sem TTY.
                 Retorna tupla (returncode, stdout, stderr).
                 Nunca lanca excecao: erros de conexao retornam rc=255.
    PARAMETER: ip       - endereco IP do host remoto
               ssh_user - usuario SSH
               comando  - string de comando a executar no shell remoto
               timeout  - timeout em segundos (padrao: 30)
    RETURNS: tuple(int, str, str) -- (returncode, stdout, stderr)
    """
    try:
        resultado = subprocess.run(
            ["ssh"] + SSH_OPTS + ["{}@{}".format(ssh_user, ip), comando],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
            check=False,
        )
        return resultado.returncode, resultado.stdout.strip(), resultado.stderr.strip()
    except subprocess.TimeoutExpired:
        return 255, "", "Timeout ({} s) ao executar comando SSH".format(timeout)
    except Exception as e:
        return 255, "", "Excecao SSH: {}".format(e)


def testa_conexao_ssh(ip, ssh_user):
    """
    NAME: testa_conexao_ssh
    DESCRIPTION: Verifica se o host remoto esta acessivel via SSH.
                 Usa timeout reduzido (5 s) para nao bloquear a listagem.
    PARAMETER: ip       - endereco IP do host remoto
               ssh_user - usuario SSH
    RETURNS: bool -- True se acessivel
    """
    rc, _, _ = ssh_run(ip, ssh_user, "true", timeout=5)
    return rc == 0




def _filtra_banner(texto):
    """
    NAME: _filtra_banner
    DESCRIPTION: Remove linhas do banner corporativo do BB.
                 Cobre o banner completo incluindo continuacoes
                 e pedido de senha do sudo.
    PARAMETER: texto - string de saida do comando remoto
    RETURNS: str -- texto sem as linhas do banner
    """
    MARCADORES = (
        "Sistema de Autenticacao", "BBBBBBBB", "UTILIZE CHAVE",
        "SISBB", "Proibido o acesso", "atividades sao monitoradas",
        "ATENCAO", "cadastrada no grupo", "Sistema ACESSO",
        "sudo: um terminal", "sudo: uma senha", "askpass", "*****",
        "root's password", "password:",
        "neste sistema", "competentes.", "Caso necessario",
        "informe a Sigla", "Antes de prosseguir",
        "devidamente", "monitoradas e logadas",
        "acesso nao autorizado", "nao autorizado",
        "=====================",
    )
    linhas_limpas = []
    for lb in texto.splitlines():
        lb_strip = lb.strip()
        if not lb_strip:
            if linhas_limpas and linhas_limpas[-1] != "":
                linhas_limpas.append("")
            continue
        if not any(m in lb for m in MARCADORES):
            linhas_limpas.append(lb_strip)
    while linhas_limpas and linhas_limpas[-1] == "":
        linhas_limpas.pop()
    return "\n".join(linhas_limpas)




def detecta_sudo(ip, ssh_user, sudo_pass=""):
    """
    NAME: detecta_sudo
    DESCRIPTION: Detecta se o sudo no host remoto esta disponivel e
                 funcional. Fluxo:
                   1. Tenta sudo -n true (sem senha).
                      rc=0 -> confirmado sem senha.
                   2. Se falhar e sudo_pass fornecido, tenta com -S.
                      Sucesso -> confirmado com senha.
                   3. Se ambos falharem -> sudo NAO confirmado.
                 Banner corporativo do BB e filtrado antes da avaliacao.

                 IMPORTANTE: retorna TUPLA (prefixo_sudo, confirmado).
                 - prefixo_sudo: string a prefixar nos comandos privilegiados
                 - confirmado: bool -- True se o privilegio foi verificado,
                   False se sudo nao esta disponivel ou a senha falhou.
                 Quando confirmado=False o chamador DEVE logar WARNING e
                 decidir se prossegue ou aborta o processamento do host.

    PARAMETER: ip        - endereco IP do host remoto
               ssh_user  - usuario SSH
               sudo_pass - senha do sudo (opcional)
    RETURNS: tuple(str, bool) -- (prefixo_sudo, confirmado)
    """
    # Tentativa 1: sudo sem senha
    rc, _, _ = ssh_run(ip, ssh_user, "sudo -n true 2>/dev/null", timeout=10)
    if rc == 0:
        return "sudo", True

    # Tentativa 2: sudo com senha fornecida
    if sudo_pass:
        rc2, stdout2, _ = ssh_run(
            ip, ssh_user,
            "echo '{}' | sudo -S true 2>/dev/null && echo SUDOOK".format(sudo_pass),
            timeout=10,
        )
        if "SUDOOK" in _filtra_banner(stdout2) or rc2 == 0:
            return "echo '{}' | sudo -S".format(sudo_pass), True

    # Nenhuma tentativa funcionou: sudo nao confirmado.
    # Retorna prefixo "sudo" por compatibilidade com chamadores antigos,
    # mas confirmado=False sinaliza ao chamador que o privilegio falhou.
    return "sudo", False




def scp_arquivo(ip, ssh_user, caminho_local, caminho_remoto):
    """
    NAME: scp_arquivo
    DESCRIPTION: Copia um arquivo local para o host remoto via scp.
                 Usa as mesmas opcoes de controle do SSH_OPTS (sem -q para
                 scp pois nao aceita essa flag da mesma forma; usa -q
                 nativo do scp). Retorna True se bem-sucedido.
    PARAMETER: ip             - endereco IP do host remoto
               ssh_user       - usuario SSH
               caminho_local  - caminho do arquivo de origem (local)
               caminho_remoto - caminho de destino no host remoto
    RETURNS: bool -- True se a copia foi bem-sucedida
    """
    try:
        resultado = subprocess.run(
            [
                "scp", "-q",
                "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
                caminho_local,
                "{}@{}:{}".format(ssh_user, ip, caminho_remoto),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=60,
            check=False,
        )
        return resultado.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def _scp_arquivo_com_erro(ip, ssh_user, caminho_local, caminho_remoto):
    """
    NAME: _scp_arquivo_com_erro
    DESCRIPTION: Variante de scp_arquivo que devolve a mensagem de erro
                 do scp quando a copia falha. Mantida como funcao
                 separada para preservar a assinatura original de
                 scp_arquivo (compatibilidade com chamadores existentes).
                 Captura stderr completo, agrega rc e tempo limite, e
                 traduz timeout/excecao em mensagens claras.
    PARAMETER: ip             - endereco IP do host remoto
               ssh_user       - usuario SSH
               caminho_local  - caminho do arquivo de origem (local)
               caminho_remoto - caminho de destino no host remoto
    RETURNS: tuple(bool, str) -- (sucesso, mensagem_erro). Em sucesso,
             mensagem_erro e string vazia. Em falha, contem o stderr
             do scp ou descricao do erro (timeout, excecao).
    """
    try:
        resultado = subprocess.run(
            [
                "scp", "-q",
                "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
                caminho_local,
                "{}@{}:{}".format(ssh_user, ip, caminho_remoto),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=60,
            check=False,
        )
        if resultado.returncode == 0:
            return True, ""
        # Falha: agrega rc + stderr (mais util ao operador)
        stderr_limpo = (resultado.stderr or "").strip().replace("\n", " | ")
        if not stderr_limpo:
            stderr_limpo = "stderr vazio"
        return False, "rc={} stderr=[{}]".format(
            resultado.returncode, stderr_limpo)
    except subprocess.TimeoutExpired:
        return False, "timeout (60 s) ao copiar via scp"
    except FileNotFoundError:
        return False, "binario scp nao encontrado no PATH local"
    except Exception as e:
        return False, "excecao no scp: {}".format(e)




def garante_amidelnx_remoto(ip, ssh_user, sudo_cmd, caminho_remoto, caminho_local,
                             log_file, log_local, verbose, suprime_tela):
    """
    NAME: garante_amidelnx_remoto
    DESCRIPTION: Verifica se o amidelnx_64 existe no host remoto. Se nao
                 existir e o binario local estiver disponivel, faz scp
                 automatico e ajusta permissao de execucao. Retorna True
                 se o binario estiver pronto para uso no alvo.
    PARAMETER: ip             - endereco IP do host remoto
               ssh_user       - usuario SSH
               sudo_cmd       - prefixo sudo no host remoto
               caminho_remoto - caminho esperado do binario no alvo
               caminho_local  - caminho do binario na maquina local
               log_file       - log remoto
               log_local      - log local consolidado
               verbose        - modo verbose
               suprime_tela   - suprime stdout (modo csv)
    RETURNS: bool -- True se amidelnx_64 esta pronto no alvo
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, log_file, nivel, msg,
                          log_local, verbose, suprime_tela)

    # Verifica presenca no alvo.
    # IMPORTANTE: usa apenas o rc direto de "test -f" (sem && echo ... || echo ...).
    # Versoes anteriores usavam "test -f X && echo found || echo missing", o que
    # mascarava o rc do test: o echo final sempre retornava 0 e o ssh_run
    # devolvia rc=0 mesmo quando o binario estava ausente. Resultado: a funcao
    # retornava True erroneamente e o scp nunca era chamado.
    rc, _, _ = ssh_run(ip, ssh_user, "test -f {}".format(caminho_remoto))
    if rc == 0:
        _log("DEBUG", "amidelnx_64 encontrado em {}".format(caminho_remoto))
        # Garante permissao de execucao
        ssh_run(ip, ssh_user, "chmod +x {}".format(caminho_remoto), timeout=10)
        return True

    _log("WARNING", "amidelnx_64 ausente em {}".format(caminho_remoto))

    # Tenta copia via scp se binario local existir
    if not os.path.isfile(caminho_local):
        _log("WARNING", "Binario local nao encontrado em {}: scp impossivel".format(
            caminho_local))
        return False

    _log("INFO", "Copiando amidelnx_64 para {}@{}:{}".format(
        ssh_user, ip, caminho_remoto))

    # Garante diretorio remoto antes do scp
    dir_remoto = os.path.dirname(caminho_remoto) or "."
    ssh_run(ip, ssh_user, "mkdir -p {}".format(dir_remoto), timeout=10)

    # Usa _scp_arquivo_com_erro para capturar e logar a razao exata
    # quando o scp falhar (Permission denied, No such file, Connection
    # refused, etc.) -- antes a mensagem de erro era descartada.
    sucesso_scp, erro_scp = _scp_arquivo_com_erro(
        ip, ssh_user, caminho_local, caminho_remoto)
    if not sucesso_scp:
        _log("ERROR", "Falha no scp do amidelnx_64 para {}: {}".format(
            ip, erro_scp))
        return False

    # Confirma que o binario chegou de fato no alvo (defesa em profundidade).
    rc_post, _, _ = ssh_run(
        ip, ssh_user, "test -f {}".format(caminho_remoto), timeout=10)
    if rc_post != 0:
        _log("ERROR",
             "scp retornou sucesso mas o binario nao esta presente em {}".format(
                 caminho_remoto))
        return False

    # Ajusta permissao apos copia
    ssh_run(ip, ssh_user, "chmod +x {}".format(caminho_remoto), timeout=10)
    _log("INFO", "amidelnx_64 copiado e pronto em {}".format(caminho_remoto))
    return True

