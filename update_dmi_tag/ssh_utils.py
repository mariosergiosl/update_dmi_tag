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
# VERSION: 2.3.5
# REVISION: 2026-10-02 - v2.3.5 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-10-02 - v2.3.4 - testa_conexao_ssh espera ate
#                        TIMEOUT_TESTE_CONEXAO (padrao 30 s, antes 5 s fixos),
#                        ajustavel por define_timeout_teste_conexao (opcao
#                        --ssh-timeout). Defeito de campo 2026-10-01/02: SLED
#                        12 levavam de 7 a 11 s para concluir o login por
#                        chave e eram dados como sem chave; a senha era
#                        aceita, a chave gravada a cada execucao e o host
#                        terminava INACESSIVEL. ssh_run e o scp somam o
#                        mesmo valor ao tempo de cada comando (folga de
#                        login): com 10 a 15 s, comandos em hosts que levam
#                        7 a 11 s so para logar eram cortados (conferencia
#                        do scp, deteccao do sudo, arquivo de configuracao).
# REVISION: 2026-09-28 - v2.3.3 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-09-28 - v2.3.2 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-09-24 - v2.3.1 - habilita_ssh_rsa_legado: com cliente
#                        OpenSSH 8.8 ou mais novo, aceita tambem a
#                        assinatura ssh-rsa (SHA-1), a unica que servidores
#                        anteriores ao 7.2 conhecem (SLE 11 SP3 e SP4);
#                        versao_servidor_ssh le o banner do sshd para
#                        diagnostico. scp passa a usar as mesmas opcoes
#                        extras do ssh.
# REVISION: 2026-09-23 - v2.3.0 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-22 - v2.2.9 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.8 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.7 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.6 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.5 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.4 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.3 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.2 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.1 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-14 - v2.2.0 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# CREATED: 2026-06-12
# REVISION: 2026-07-13 - v2.1.14 - renumeracao do mecanismo de boot EFI
#                        de "Mecanismo 4" para "Mecanismo 3" (elimina o
#                        buraco na numeracao; cascata agora 1, 2, 3). So
#                        exibicao (log/ajuda/docs); identificadores
#                        funcionais (status, flags, labels) inalterados.
# REVISION: 2026-07-09 - v2.1.13 - atualizacao de numero de versao para
#                        v2.1.13 (usuario do SO no log, empacotamento
#                        RPM; ver __main__.py e update_dmi_tag.spec).
# REVISION: 2026-07-09 - v2.1.12 - atualizacao de numero de versao para
#                        v2.1.12 (correcoes no Mecanismo 3, ver
#                        boot_efi.py).
# REVISION: 2026-07-08 - v2.1.11 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem
#                        mudanca funcional neste arquivo (boot_efi.py
#                        passa a reaproveitar ssh_run/testa_porta_ssh/
#                        testa_conexao_ssh/_scp_arquivo_com_erro deste
#                        modulo).
# REVISION: 2026-07-07 - v2.1.10 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem
#                        mudanca funcional neste arquivo.
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
# REVISION: 2026-07-06 - v2.1.9 - adiciona a funcao testa_porta_ssh
#                        para teste rapido de conectividade TCP na porta 22.
#
# =======================================================================

import os
import re
import socket
import subprocess

from .constants import SSH_OPTS
from .logging_utils import gravar_log_remoto

# v2.3.1: opcoes acrescentadas em tempo de execucao ao ssh e ao scp (ver
# habilita_ssh_rsa_legado). Lista compartilhada, alterada so no inicio da
# execucao, antes das threads do --parallel.
SSH_OPTS_EXTRA = []
_OPCAO_SSH_RSA = "PubkeyAcceptedAlgorithms=+ssh-rsa"
# v2.3.6: mesma restricao do OpenSSH 8.8 para a chave do SERVIDOR. Alvo
# cujo sshd so oferece chave de servidor ssh-rsa/ssh-dss terminava
# "no matching host key type found" (3 SLE 11 em 2026-10-14).
_OPCAO_HOSTKEY_RSA = "HostKeyAlgorithms=+ssh-rsa"

# v2.3.4: tempo maximo do teste de conexao por chave (opcao --ssh-timeout).
# Host sem SSH ja e descartado antes pelo teste de porta (2 s) e chave
# recusada responde na hora; o limite so pesa em host lento para concluir
# o login. Alterado so no inicio da execucao, antes das threads.
TIMEOUT_TESTE_CONEXAO = 30
# v2.3.4: login por chave acima deste tempo e registrado como lento.
LIMITE_LOGIN_LENTO = 5


def versao_openssh(texto):
    """
    NAME: versao_openssh
    DESCRIPTION: Extrai a versao (maior, menor) de um texto no formato do
                 OpenSSH, como a saida de 'ssh -V' ('OpenSSH_9.6p1, ...')
                 ou o banner do servidor ('SSH-2.0-OpenSSH_6.2').
    PARAMETER: texto - texto a analisar
    RETURNS: tuple(int, int) ou None se nao for OpenSSH
    """
    m = re.search(r"OpenSSH_(\d+)\.(\d+)", texto or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def habilita_ssh_rsa_legado():
    """
    NAME: habilita_ssh_rsa_legado
    DESCRIPTION: O cliente OpenSSH 8.8 ou mais novo recusa por padrao a
                 assinatura ssh-rsa (SHA-1), e servidores anteriores ao
                 OpenSSH 7.2 so conhecem essa (SLE 11 SP3 tem 6.2, SP4 tem
                 6.6). Sem ela a chave RSA nao autentica nesses alvos.
                 Acrescenta PubkeyAcceptedAlgorithms=+ssh-rsa as opcoes do
                 ssh e do scp; o '+' so amplia a lista, e servidores
                 modernos continuam negociando rsa-sha2. Idempotente.
                 v2.3.6: acrescenta tambem HostKeyAlgorithms=+ssh-rsa,
                 para o sshd que so oferece chave de servidor ssh-rsa
                 (sem ela: "no matching host key type found"). As duas
                 opcoes ficam em SSH_OPTS_EXTRA, que o ssh-copy-id do
                 bootstrap tambem recebe.
                 Chamada uma vez, no inicio do modo remoto.
    PARAMETER: nenhum
    RETURNS: str, versao do cliente e a decisao, para o log
    """
    try:
        r = subprocess.run(["ssh", "-V"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True,
                           timeout=10, check=False)
        texto = (r.stderr or r.stdout or "").strip()
    except Exception as e:
        return "cliente ssh nao identificado ({}); ssh-rsa inalterado".format(e)
    versao = versao_openssh(texto)
    if versao is None or versao < (8, 8):
        return "{}; ssh-rsa ja aceito pelo cliente".format(texto or "?")
    for opcao in (_OPCAO_SSH_RSA, _OPCAO_HOSTKEY_RSA):
        if opcao not in SSH_OPTS_EXTRA:
            SSH_OPTS_EXTRA.extend(["-o", opcao])
            SSH_OPTS.extend(["-o", opcao])
    return "{}; ssh-rsa habilitado para alvos com OpenSSH antigo".format(texto)


def versao_servidor_ssh(ip, porta=22, timeout=3.0):
    """
    NAME: versao_servidor_ssh
    DESCRIPTION: Le o banner que o sshd envia ao abrir a conexao, sem
                 autenticar (ex.: 'SSH-2.0-OpenSSH_6.2'). Usado so para
                 diagnostico no log.
    PARAMETER: ip      - endereco IP do host
               porta   - porta TCP (padrao: 22)
               timeout - tempo limite em segundos
    RETURNS: str, banner sem quebra de linha, ou "" se nao lido
    """
    try:
        with socket.create_connection((ip, porta), timeout=timeout) as s:
            s.settimeout(timeout)
            dados = s.recv(256).decode("ascii", "replace")
        return dados.splitlines()[0].strip() if dados else ""
    except Exception:
        return ""


def ssh_run(ip, ssh_user, comando, timeout=30, folga_login=True):
    """
    NAME: ssh_run
    DESCRIPTION: Executa um comando no host remoto via SSH sem TTY.
                 Retorna tupla (returncode, stdout, stderr).
                 Nunca lanca excecao: erros de conexao retornam rc=255.
                 v2.3.4: soma TIMEOUT_TESTE_CONEXAO (folga de login) ao
                 timeout do comando, porque cada chamada abre um login novo.
    PARAMETER: ip          - endereco IP do host remoto
               ssh_user    - usuario SSH
               comando     - string de comando a executar no shell remoto
               timeout     - tempo do comando em segundos (padrao: 30)
               folga_login - False so no teste de conexao, cujo timeout ja
                             e o proprio tempo de login
    RETURNS: tuple(int, str, str), (returncode, stdout, stderr)
    """
    if folga_login:
        timeout = timeout + TIMEOUT_TESTE_CONEXAO
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


def define_timeout_teste_conexao(segundos):
    """
    NAME: define_timeout_teste_conexao
    DESCRIPTION: v2.3.4. Ajusta TIMEOUT_TESTE_CONEXAO (opcao --ssh-timeout).
                 Chamada uma vez, no inicio do modo remoto.
    PARAMETER: segundos - inteiro maior que zero
    RETURNS: str, texto para o cabecalho do log
    """
    global TIMEOUT_TESTE_CONEXAO
    TIMEOUT_TESTE_CONEXAO = int(segundos)
    return "teste de conexao ate {} s".format(TIMEOUT_TESTE_CONEXAO)


def testa_conexao_ssh(ip, ssh_user, timeout=None):
    """
    NAME: testa_conexao_ssh
    DESCRIPTION: Verifica se o host remoto esta acessivel via SSH.
                 v2.3.4: espera ate TIMEOUT_TESTE_CONEXAO (padrao 30 s,
                 opcao --ssh-timeout); com 5 s fixos, hosts lentos para
                 concluir o login eram dados como sem chave.
    PARAMETER: ip       - endereco IP do host remoto
               ssh_user - usuario SSH
               timeout  - segundos; None usa TIMEOUT_TESTE_CONEXAO
    RETURNS: bool, True se acessivel
    """
    if timeout is None:
        timeout = TIMEOUT_TESTE_CONEXAO
    rc, _, _ = ssh_run(ip, ssh_user, "true", timeout=timeout,
                       folga_login=False)
    return rc == 0


def testa_porta_ssh(ip, porta=22, timeout=2.0):
    """
    NAME: testa_porta_ssh
    DESCRIPTION: Testa se o host remoto esta ativo e respondendo na porta SSH (TCP 22)
                 utilizando um socket rapido. Evita timeouts de 5s+ do comando ssh.
    PARAMETER: ip      - endereco IP do host
               porta   - porta TCP (padrao: 22)
               timeout - tempo limite em segundos (padrao: 2.0)
    RETURNS: bool, True se conexao estabelecida, False caso contrario
    """
    try:
        with socket.create_connection((ip, porta), timeout=timeout):
            return True
    except (socket.timeout, OSError):
        return False




def _filtra_banner(texto):
    """
    NAME: _filtra_banner
    DESCRIPTION: Remove linhas do banner corporativo de login SSH/sudo.
                 Cobre o banner completo incluindo continuacoes
                 e pedido de senha do sudo.
    PARAMETER: texto - string de saida do comando remoto
    RETURNS: str, texto sem as linhas do banner
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
                 Banner corporativo de login e filtrado antes da avaliacao.

                 IMPORTANTE: retorna TUPLA (prefixo_sudo, confirmado).
                 - prefixo_sudo: string a prefixar nos comandos privilegiados
                 - confirmado: bool, True se o privilegio foi verificado,
                   False se sudo nao esta disponivel ou a senha falhou.
                 Quando confirmado=False o chamador DEVE logar WARNING e
                 decidir se prossegue ou aborta o processamento do host.

    PARAMETER: ip        - endereco IP do host remoto
               ssh_user  - usuario SSH
               sudo_pass - senha do sudo (opcional)
    RETURNS: tuple(str, bool), (prefixo_sudo, confirmado)
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
    RETURNS: bool, True se a copia foi bem-sucedida
    """
    try:
        resultado = subprocess.run(
            [
                "scp", "-q",
                "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
            ] + SSH_OPTS_EXTRA + [
                caminho_local,
                "{}@{}:{}".format(ssh_user, ip, caminho_remoto),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=60 + TIMEOUT_TESTE_CONEXAO,
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
    RETURNS: tuple(bool, str), (sucesso, mensagem_erro). Em sucesso,
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
            ] + SSH_OPTS_EXTRA + [
                caminho_local,
                "{}@{}:{}".format(ssh_user, ip, caminho_remoto),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=60 + TIMEOUT_TESTE_CONEXAO,
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
        return False, "timeout ({} s) ao copiar via scp".format(
            60 + TIMEOUT_TESTE_CONEXAO)
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
    RETURNS: bool, True se amidelnx_64 esta pronto no alvo
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
    # refused, etc.), antes a mensagem de erro era descartada.
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

