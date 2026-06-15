# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: ssh_bootstrap.py
#
# DESCRIPTION: Bootstrap de autenticacao SSH por chave publica, executado
#              antes do fluxo principal de cada host. Localiza ou gera
#              chave SSH local (ed25519), resolve a senha SSH efetiva
#              (precedencia --ssh-pass > SSH_PASS env > --ssh-pass-file)
#              e, se necessario, distribui a chave via ssh-copy-id
#              alimentando a senha por pty.
#
#              O uso de pty fica isolado em _ssh_copy_id_com_senha,
#              UNICA funcao do pacote que importa o modulo pty. Apos o
#              bootstrap, o fluxo principal usa ssh_run/scp_arquivo com
#              BatchMode=yes (ver ssh_utils.py).
#
#              Depende de ssh_utils.testa_conexao_ssh para o caminho
#              feliz (chave ja autorizada).
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
import time

from .constants import DEFAULT_SSH_KEY_RSA, DEFAULT_SSH_KEY_ED25519
from .logging_utils import gravar_log
from .ssh_utils import testa_conexao_ssh


def _localiza_chave_ssh_local():
    """
    NAME: _localiza_chave_ssh_local
    DESCRIPTION: Procura uma chave privada SSH no home do usuario.
                 Verifica id_rsa primeiro (compatibilidade legada) e
                 id_ed25519 em seguida (padrao moderno). Retorna o par
                 (privada, publica) do primeiro arquivo encontrado, ou
                 None nos dois se nenhuma existir.
    PARAMETER: nenhum
    RETURNS: tuple(str, str) -- (caminho_privada, caminho_publica)
             ou (None, None) se nenhuma chave existir.
    """
    candidatas = (
        (DEFAULT_SSH_KEY_RSA,     DEFAULT_SSH_KEY_RSA + ".pub"),
        (DEFAULT_SSH_KEY_ED25519, DEFAULT_SSH_KEY_ED25519 + ".pub"),
    )
    for priv, pub in candidatas:
        if os.path.isfile(priv) and os.path.isfile(pub):
            return priv, pub
    return None, None


def _gera_chave_ssh_local(caminho_log_local, verbose):
    """
    NAME: _gera_chave_ssh_local
    DESCRIPTION: Gera uma chave ed25519 sem passphrase no home do usuario
                 atual, de forma totalmente nao-interativa. Cria o
                 diretorio ~/.ssh com permissoes 0700 se necessario.
                 Usa ssh-keygen do sistema (parte do openssh-clients).
    PARAMETER: caminho_log_local - log local consolidado para registro
               verbose           - se True, imprime no stdout
    RETURNS: tuple(str, str) -- (caminho_privada, caminho_publica) em sucesso,
             ou (None, None) em caso de falha.
    """
    diretorio_ssh = os.path.expanduser("~/.ssh")
    caminho_priv  = DEFAULT_SSH_KEY_ED25519
    caminho_pub   = DEFAULT_SSH_KEY_ED25519 + ".pub"

    try:
        if not os.path.isdir(diretorio_ssh):
            os.makedirs(diretorio_ssh, mode=0o700, exist_ok=True)
    except Exception as e:
        gravar_log(caminho_log_local, "ERROR",
                   "Bootstrap SSH: falha ao criar ~/.ssh: {}".format(e),
                   verbose, False)
        return None, None

    try:
        resultado = subprocess.run(
            [
                "ssh-keygen",
                "-q",
                "-t", "ed25519",
                "-N", "",
                "-f", caminho_priv,
                "-C", "update_dmi_tag bootstrap",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=15,
            check=False,
        )
        if resultado.returncode != 0:
            gravar_log(caminho_log_local, "ERROR",
                       "Bootstrap SSH: ssh-keygen falhou (rc={}): {}".format(
                           resultado.returncode,
                           (resultado.stderr or "").strip()),
                       verbose, False)
            return None, None
    except subprocess.TimeoutExpired:
        gravar_log(caminho_log_local, "ERROR",
                   "Bootstrap SSH: ssh-keygen timeout (15 s)",
                   verbose, False)
        return None, None
    except FileNotFoundError:
        gravar_log(caminho_log_local, "ERROR",
                   "Bootstrap SSH: ssh-keygen nao encontrado no PATH",
                   verbose, False)
        return None, None
    except Exception as e:
        gravar_log(caminho_log_local, "ERROR",
                   "Bootstrap SSH: excecao ao gerar chave: {}".format(e),
                   verbose, False)
        return None, None

    gravar_log(caminho_log_local, "INFO",
               "Bootstrap SSH: chave ed25519 gerada em {}".format(caminho_priv),
               verbose, False)
    return caminho_priv, caminho_pub


def _resolve_ssh_pass(args):
    """
    NAME: _resolve_ssh_pass
    DESCRIPTION: Resolve a senha SSH a ser usada pelo bootstrap, na
                 seguinte ordem de precedencia:
                   1. --ssh-pass (argumento de linha de comando)
                   2. SSH_PASS (variavel de ambiente)
                   3. --ssh-pass-file (arquivo com a senha na 1a linha)
                 Retorna string vazia se nenhuma das tres estiver
                 disponivel. Erros de leitura de arquivo sao silenciosos
                 (apenas retorna vazio); nao trava o fluxo.
    PARAMETER: args - namespace do argparse (deve ter ssh_pass e
                      ssh_pass_file, mesmo que vazios)
    RETURNS: str -- senha SSH efetiva, ou string vazia.
    """
    if getattr(args, "ssh_pass", ""):
        return args.ssh_pass

    senha_env = os.environ.get("SSH_PASS", "")
    if senha_env:
        return senha_env

    caminho_arq = getattr(args, "ssh_pass_file", "")
    if caminho_arq:
        try:
            with open(caminho_arq, "r", encoding="utf-8") as f:
                linha = f.readline()
                return linha.rstrip("\r\n")
        except Exception:
            return ""

    return ""




def _ssh_copy_id_com_senha(ip, ssh_user, senha, caminho_chave_pub,
                            caminho_log_local, verbose):
    """
    NAME: _ssh_copy_id_com_senha
    DESCRIPTION: Distribui a chave publica para o host remoto via
                 ssh-copy-id, alimentando a senha SSH atraves de um
                 pseudo-terminal (pty). Esta e a UNICA funcao do script
                 que importa e utiliza o modulo pty. Toda a complexidade
                 de I/O nao-bloqueante fica confinada aqui.

                 O ssh-copy-id e invocado com timeout de conexao curto
                 e StrictHostKeyChecking=no para automatizar o "yes" na
                 primeira conexao. BatchMode NAO e usado aqui (ssh-copy-id
                 precisa de prompt interativo para receber a senha).

                 Timeout global da operacao: 30 segundos.
    PARAMETER: ip                  - endereco IP do host remoto
               ssh_user            - usuario SSH
               senha               - senha SSH em texto puro
               caminho_chave_pub   - caminho da chave publica local
               caminho_log_local   - log local consolidado
               verbose             - se True, imprime no stdout
    RETURNS: bool -- True se ssh-copy-id retornou rc=0, False caso
             contrario (timeout, autenticacao falhou, binario ausente,
             etc.). Em falha, registra ERROR identificando a etapa.
    """
    # Import isolado: pty so e importado quando esta funcao e chamada.
    # Nenhum outro lugar do script depende deste modulo.
    import pty
    import select
    import errno

    if not senha:
        gravar_log(caminho_log_local, "ERROR",
                   "[{}] Bootstrap SSH: nenhuma senha SSH disponivel "
                   "(--ssh-pass, SSH_PASS env ou --ssh-pass-file)".format(ip),
                   verbose, False)
        return False

    if not os.path.isfile(caminho_chave_pub):
        gravar_log(caminho_log_local, "ERROR",
                   "[{}] Bootstrap SSH: chave publica nao encontrada: {}".format(
                       ip, caminho_chave_pub),
                   verbose, False)
        return False

    argv = [
        "ssh-copy-id",
        "-i", caminho_chave_pub,
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=no",
        "-o", "PreferredAuthentications=password,keyboard-interactive",
        "-o", "PubkeyAuthentication=no",
        "{}@{}".format(ssh_user, ip),
    ]

    try:
        pid, fd = pty.fork()
    except OSError as e:
        gravar_log(caminho_log_local, "ERROR",
                   "[{}] Bootstrap SSH: pty.fork falhou: {}".format(ip, e),
                   verbose, False)
        return False

    if pid == 0:
        # Processo filho: substitui pelo ssh-copy-id.
        # Erros aqui matam o filho com codigo nao-zero; o pai detecta.
        try:
            os.execvp("ssh-copy-id", argv)
        except FileNotFoundError:
            os._exit(127)
        except Exception:
            os._exit(126)

    # Processo pai: le do pty, injeta senha quando ver o prompt,
    # respeita timeout global de 30 segundos.
    timeout_total   = 30.0
    inicio          = time.time()
    buffer_saida    = ""
    senha_enviada   = False
    saida_completa  = []

    try:
        while True:
            decorrido = time.time() - inicio
            if decorrido >= timeout_total:
                gravar_log(caminho_log_local, "ERROR",
                           "[{}] Bootstrap SSH: ssh-copy-id timeout "
                           "({:.0f} s)".format(ip, timeout_total),
                           verbose, False)
                try:
                    os.kill(pid, 9)
                except Exception:
                    pass
                try:
                    os.close(fd)
                except Exception:
                    pass
                try:
                    os.waitpid(pid, 0)
                except Exception:
                    pass
                return False

            restante = timeout_total - decorrido
            try:
                pronto, _, _ = select.select([fd], [], [], min(1.0, restante))
            except (OSError, select.error) as e:
                # EINTR ou fd ja fechado; continua tentando
                if getattr(e, "errno", None) == errno.EINTR:
                    continue
                break

            if not pronto:
                # Sem dados ainda; verifica se o filho ja saiu
                pid_terminado, _ = os.waitpid(pid, os.WNOHANG)
                if pid_terminado != 0:
                    # Reanexa o pid; o waitpid final pega o status real
                    # (usa loop com WNOHANG mais abaixo)
                    pass
                continue

            try:
                pedaco = os.read(fd, 4096)
            except OSError:
                # PTY fechou (EIO no Linux quando filho termina)
                break

            if not pedaco:
                break

            try:
                texto = pedaco.decode("utf-8", errors="replace")
            except Exception:
                texto = ""

            saida_completa.append(texto)
            buffer_saida += texto

            # Detecta prompt de senha (case-insensitive, varias variacoes)
            buffer_lower = buffer_saida.lower()
            if (not senha_enviada) and (
                "password:" in buffer_lower
                or "password for" in buffer_lower
                or "'s password" in buffer_lower
            ):
                try:
                    os.write(fd, (senha + "\n").encode("utf-8"))
                    senha_enviada = True
                    buffer_saida = ""  # zera para nao reagir duas vezes
                except OSError as e:
                    gravar_log(caminho_log_local, "ERROR",
                               "[{}] Bootstrap SSH: falha ao injetar "
                               "senha no pty: {}".format(ip, e),
                               verbose, False)
                    break

            # Detecta indicadores claros de falha de autenticacao
            if (
                "permission denied" in buffer_lower
                or "too many authentication failures" in buffer_lower
                or "no supported authentication methods" in buffer_lower
            ):
                gravar_log(caminho_log_local, "ERROR",
                           "[{}] Bootstrap SSH: ssh-copy-id autenticacao "
                           "rejeitada (senha incorreta ou SSH bloqueado)".format(ip),
                           verbose, False)
                try:
                    os.kill(pid, 9)
                except Exception:
                    pass
                try:
                    os.close(fd)
                except Exception:
                    pass
                try:
                    os.waitpid(pid, 0)
                except Exception:
                    pass
                return False
    finally:
        try:
            os.close(fd)
        except Exception:
            pass

    # Coleta o status final do filho
    try:
        _, status = os.waitpid(pid, 0)
    except Exception as e:
        gravar_log(caminho_log_local, "ERROR",
                   "[{}] Bootstrap SSH: waitpid falhou: {}".format(ip, e),
                   verbose, False)
        return False

    if os.WIFEXITED(status):
        rc = os.WEXITSTATUS(status)
    elif os.WIFSIGNALED(status):
        rc = 128 + os.WTERMSIG(status)
    else:
        rc = -1

    if rc == 0:
        return True

    if rc == 127:
        gravar_log(caminho_log_local, "ERROR",
                   "[{}] Bootstrap SSH: binario ssh-copy-id nao encontrado "
                   "no PATH local".format(ip),
                   verbose, False)
    else:
        # Captura os ultimos 200 caracteres da saida para log de falha
        cauda = ("".join(saida_completa))[-200:].replace("\n", " | ").strip()
        gravar_log(caminho_log_local, "ERROR",
                   "[{}] Bootstrap SSH: ssh-copy-id encerrou com rc={} "
                   "(cauda: {})".format(ip, rc, cauda or "vazio"),
                   verbose, False)
    return False


def prepara_autenticacao_ssh(ip, ssh_user, ssh_pass,
                              caminho_log_local, verbose):
    """
    NAME: prepara_autenticacao_ssh
    DESCRIPTION: Orquestra o bootstrap de autenticacao SSH para um host.
                 Fluxo em ordem:
                   1. Localiza chave SSH local (RSA ou ed25519).
                   2. Se nenhuma existir, gera id_ed25519 sem passphrase.
                   3. Tenta conexao via chave (testa_conexao_ssh).
                      Caminho feliz: retorna True sem mais nenhuma acao.
                   4. Se a chave nao esta distribuida e ha senha SSH
                      disponivel, chama _ssh_copy_id_com_senha (unica
                      funcao com pty) para distribuir a chave.
                   5. Apos copy-id, testa a conexao novamente.
                 Esta funcao NAO modifica SSH_OPTS nem o comportamento
                 das funcoes ssh_run / scp_arquivo / testa_conexao_ssh.
                 Apenas garante que o handshake por chave esteja pronto
                 antes do fluxo principal usa-las.

                 Caminho feliz (chave ja distribuida) e silencioso, sem
                 log. Logs somente quando ha intervencao (geracao,
                 copy-id) ou falha.
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               ssh_pass          - senha SSH efetiva (pode ser vazia)
               caminho_log_local - log local consolidado
               verbose           - se True, imprime no stdout
    RETURNS: bool -- True se o host esta acessivel via chave apos o
             bootstrap. False indica falha definitiva (caller marca
             como INACESSIVEL).
    """
    # 1. Localiza chave existente
    chave_priv, chave_pub = _localiza_chave_ssh_local()

    # 2. Gera se nenhuma existir
    if chave_priv is None:
        chave_priv, chave_pub = _gera_chave_ssh_local(
            caminho_log_local, verbose)
        if chave_priv is None:
            gravar_log(caminho_log_local, "ERROR",
                       "[{}] Bootstrap SSH: nao foi possivel obter uma "
                       "chave SSH local".format(ip),
                       verbose, False)
            return False

    # 3. Caminho feliz: chave ja distribuida (BatchMode=yes funciona)
    if testa_conexao_ssh(ip, ssh_user):
        return True

    # 4. Falhou: tenta distribuir a chave via ssh-copy-id
    if not ssh_pass:
        gravar_log(caminho_log_local, "ERROR",
                   "[{}] Bootstrap SSH: chave nao autorizada e nenhuma "
                   "senha SSH fornecida (use --ssh-pass, SSH_PASS env ou "
                   "--ssh-pass-file)".format(ip),
                   verbose, False)
        return False

    gravar_log(caminho_log_local, "INFO",
               "[{}] Bootstrap SSH: distribuindo chave publica via "
               "ssh-copy-id".format(ip),
               verbose, False)

    sucesso_copy = _ssh_copy_id_com_senha(
        ip, ssh_user, ssh_pass, chave_pub,
        caminho_log_local, verbose,
    )
    if not sucesso_copy:
        # _ssh_copy_id_com_senha ja registrou o ERROR especifico da etapa
        return False

    # 5. Reconfere via chave apos copy-id
    if testa_conexao_ssh(ip, ssh_user):
        gravar_log(caminho_log_local, "INFO",
                   "[{}] Bootstrap SSH: chave distribuida e conexao por "
                   "chave validada".format(ip),
                   verbose, False)
        return True

    gravar_log(caminho_log_local, "ERROR",
               "[{}] Bootstrap SSH: ssh-copy-id reportou sucesso mas a "
               "reconexao por chave ainda falha".format(ip),
               verbose, False)
    return False

