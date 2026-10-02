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
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.5
# REVISION: 2026-10-02 - v2.3.5 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-10-02 - v2.3.4 - a chave distribuida passa a depender do
#                        sshd do alvo, lido pelo banner: ed25519 para
#                        OpenSSH 6.5 ou mais novo (SLE 12 em diante) e para
#                        banner nao lido, RSA para OpenSSH anterior ao 6.5
#                        (SLE 11). Se a reconexao falhar com a primeira
#                        chave, a outra e distribuida e testada, sem
#                        repetir o envio quando a senha foi recusada.
#                        Defeito de campo 2026-10-01: SLED 12 (OpenSSH 7.2)
#                        aceitou a senha e gravou a chave RSA, mas recusou
#                        a conexao por ela; com a 2.3.0 (ed25519) a mesma
#                        conta entrou em 94 SLED 12 SP2 e SP4.
#                        Teste de conexao medido: login por chave acima de
#                        LIMITE_LOGIN_LENTO vira aviso no log, e a falha
#                        final indica quando o teste foi cortado pelo limite
#                        de tempo (--ssh-timeout), causa real do defeito.
# REVISION: 2026-09-28 - v2.3.3 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-09-28 - v2.3.2 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-09-24 - v2.3.1 - bootstrap passa a usar chave RSA, gerada
#                        se o usuario so tiver ed25519: o OpenSSH anterior
#                        ao 6.5 (SLE 11 SP3 tem 6.2) nao conhece ed25519,
#                        aceitava a chave no ssh-copy-id e depois recusava a
#                        conexao. A ed25519 existente continua sendo
#                        oferecida pelo cliente (sem -i), entao alvos onde
#                        ela ja esta autorizada seguem funcionando. Falha
#                        de reconexao registra o banner do servidor.
#                        limpa_temporarios_ssh_copy_id remove as pastas
#                        ~/.ssh/ssh-copy-id.* deixadas pelo ssh-copy-id
#                        interrompido durante a execucao.
# REVISION: 2026-09-23 - v2.3.0 - parametro nivel_falha nas recusas de
#                        acesso (WARNING quando outro perfil ainda sera
#                        tentado); novo prompt de senha apos o envio passa
#                        a ser tratado como recusa imediata (antes esperava
#                        o timeout de 30 s por host, ex. SLE 11 com usuario
#                        inexistente), sem reenviar a senha.
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
# REVISION: 2026-07-17 - v2.2.5 - corrige BUG REAL de corrida entre
#                        threads: prepara_autenticacao_ssh checava e
#                        gerava a chave SSH local (recurso compartilhado
#                        entre todos os hosts) sem nenhum lock. Com
#                        --parallel > 1 e nenhuma chave local previa,
#                        duas threads podiam checar "chave ausente" ao
#                        mesmo tempo; uma gerava a chave, a outra
#                        chamava ssh-keygen sobre o arquivo que acabara
#                        de aparecer e falhava (stdin e DEVNULL, sem
#                        confirmacao interativa de sobrescrita), levando
#                        o host dessa segunda thread a INACESSIVEL sem
#                        motivo real. Corrigido com threading.Lock
#                        (_lock_chave_ssh_local) ao redor da checagem+
#                        geracao. Constatado e corrigido em teste real
#                        (--parallel 3, 3 hosts, ambiente sem chave SSH
#                        local previa, 2026-07-17).
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
#                        mudanca funcional neste arquivo.
# REVISION: 2026-07-07 - v2.1.10 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem
#                        mudanca funcional neste arquivo.
# REVISION: 2026-07-07 - v2.1.9 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem
#                        mudanca funcional neste arquivo.
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
#
# =======================================================================

import os
import re
import shutil
import subprocess
import threading
import time

from .constants import DEFAULT_SSH_KEY_RSA, DEFAULT_SSH_KEY_ED25519
from .logging_utils import gravar_log
from . import ssh_utils
from .ssh_utils import testa_conexao_ssh, versao_openssh, versao_servidor_ssh

# Protege a checagem+geracao da chave SSH local (recurso compartilhado
# entre todos os hosts) contra corrida entre threads do --parallel: sem
# isso, duas threads podem checar "chave ausente" ao mesmo tempo e uma
# delas falha no ssh-keygen porque a outra ja criou o arquivo entre a
# checagem e a geracao (ssh-keygen nao sobrescreve sem confirmacao
# interativa, que nao existe aqui, stdin e DEVNULL). Constatado em teste
# real (--parallel 3, 3 hosts, ambiente sem nenhuma chave SSH local
# previa, 2026-07-17).
_lock_chave_ssh_local = threading.Lock()


def _localiza_chave_ssh_local():
    """
    NAME: _localiza_chave_ssh_local
    DESCRIPTION: Procura uma chave privada SSH no home do usuario.
                 Verifica id_rsa primeiro (compatibilidade legada) e
                 id_ed25519 em seguida (padrao moderno). Retorna o par
                 (privada, publica) do primeiro arquivo encontrado, ou
                 None nos dois se nenhuma existir.
    PARAMETER: nenhum
    RETURNS: tuple(str, str), (caminho_privada, caminho_publica)
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


def _gera_chave_ssh_local(caminho_log_local, verbose, tipo="ed25519"):
    """
    NAME: _gera_chave_ssh_local
    DESCRIPTION: Gera uma chave sem passphrase no home do usuario atual,
                 de forma totalmente nao-interativa. Cria o diretorio
                 ~/.ssh com permissoes 0700 se necessario. Usa ssh-keygen
                 do sistema (parte do openssh-clients).
    PARAMETER: caminho_log_local - log local consolidado para registro
               verbose           - se True, imprime no stdout
               tipo              - "ed25519" (padrao) ou "rsa" (v2.3.1,
                                   4096 bits)
    RETURNS: tuple(str, str), (caminho_privada, caminho_publica) em sucesso,
             ou (None, None) em caso de falha.
    """
    diretorio_ssh = os.path.expanduser("~/.ssh")
    base          = DEFAULT_SSH_KEY_RSA if tipo == "rsa" else DEFAULT_SSH_KEY_ED25519
    caminho_priv  = base
    caminho_pub   = base + ".pub"
    tipo_args     = ["-t", "rsa", "-b", "4096"] if tipo == "rsa" else ["-t", "ed25519"]

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
            ] + tipo_args + [
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
               "Bootstrap SSH: chave {} gerada em {}".format(tipo, caminho_priv),
               verbose, False)
    return caminho_priv, caminho_pub


# v2.3.4: primeira versao do OpenSSH que conhece ed25519.
_VERSAO_MIN_ED25519 = (6, 5)


def _testa_e_mede(ip, ssh_user, caminho_log_local, verbose):
    """
    NAME: _testa_e_mede
    DESCRIPTION: v2.3.4. testa_conexao_ssh com medicao de tempo. Login
                 aceito acima de LIMITE_LOGIN_LENTO vira aviso no log.
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               caminho_log_local - log local consolidado
               verbose           - se True, imprime no stdout
    RETURNS: tuple(bool, bool), (conectou, cortado pelo limite de tempo)
    """
    inicio = time.time()
    ok = testa_conexao_ssh(ip, ssh_user)
    decorrido = time.time() - inicio
    limite = ssh_utils.TIMEOUT_TESTE_CONEXAO
    if ok and decorrido > ssh_utils.LIMITE_LOGIN_LENTO:
        gravar_log(caminho_log_local, "WARNING",
                   "[{}] Bootstrap SSH: login por chave lento ({:.1f} s; "
                   "limite do teste {} s, opcao --ssh-timeout)".format(
                       ip, decorrido, limite),
                   verbose, False)
    return ok, (not ok and decorrido >= limite - 0.5)


def _tipos_de_chave(banner):
    """
    NAME: _tipos_de_chave
    DESCRIPTION: v2.3.4. Ordem dos tipos de chave a distribuir, pelo
                 banner do sshd do alvo. OpenSSH anterior ao 6.5 (SLE 11)
                 nao conhece ed25519: so RSA. Nos demais, e quando o
                 banner nao foi lido, ed25519 primeiro e RSA em seguida.
    PARAMETER: banner - banner do sshd (ex.: 'SSH-2.0-OpenSSH_7.2') ou ""
    RETURNS: tuple(str), tipos na ordem de tentativa
    """
    versao = versao_openssh(banner)
    if versao is not None and versao < _VERSAO_MIN_ED25519:
        return ("rsa",)
    return ("ed25519", "rsa")


def _obtem_chave_do_tipo(tipo, caminho_log_local, verbose):
    """
    NAME: _obtem_chave_do_tipo
    DESCRIPTION: v2.3.4. Devolve o par de chaves do tipo pedido,
                 gerando-o se nao existir. Chamada sob
                 _lock_chave_ssh_local.
    PARAMETER: tipo              - "ed25519" ou "rsa"
               caminho_log_local - log local consolidado
               verbose           - se True, imprime no stdout
    RETURNS: tuple(str, str), (privada, publica) ou (None, None)
    """
    base = DEFAULT_SSH_KEY_RSA if tipo == "rsa" else DEFAULT_SSH_KEY_ED25519
    if os.path.isfile(base) and os.path.isfile(base + ".pub"):
        return base, base + ".pub"
    return _gera_chave_ssh_local(caminho_log_local, verbose, tipo=tipo)


_RE_TEMP_SSH_COPY_ID = re.compile(r"^ssh-copy-id\.[A-Za-z0-9]{10}$")


def limpa_temporarios_ssh_copy_id(desde):
    """
    NAME: limpa_temporarios_ssh_copy_id
    DESCRIPTION: v2.3.1. O ssh-copy-id cria ~/.ssh/ssh-copy-id.XXXXXXXXXX
                 e so a remove ao terminar normalmente; interrompido (ex.:
                 recusa de senha), a pasta fica. Remove as pastas com esse
                 padrao de nome modificadas a partir de 'desde' (inicio da
                 execucao). Pastas mais antigas, de outras execucoes, nao
                 sao tocadas. Chamar so depois de todos os hosts, nunca
                 durante o --parallel.
    PARAMETER: desde - epoch (float) do inicio da execucao
    RETURNS: int, quantidade de pastas removidas
    """
    diretorio_ssh = os.path.dirname(DEFAULT_SSH_KEY_RSA)
    removidas = 0
    try:
        nomes = os.listdir(diretorio_ssh)
    except Exception:
        return 0
    for nome in nomes:
        caminho = os.path.join(diretorio_ssh, nome)
        try:
            if (_RE_TEMP_SSH_COPY_ID.match(nome) and os.path.isdir(caminho)
                    and not os.path.islink(caminho)
                    and os.path.getmtime(caminho) >= desde):
                shutil.rmtree(caminho)
                removidas += 1
        except Exception:
            continue
    return removidas


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
    RETURNS: str, senha SSH efetiva, ou string vazia.
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
                            caminho_log_local, verbose, nivel_falha="ERROR"):
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
               nivel_falha         - nivel de log das recusas de acesso
                                     (v2.3.0; WARNING quando outro perfil
                                     ainda sera tentado)
    RETURNS: bool, True se ssh-copy-id retornou rc=0, False caso
             contrario (timeout, autenticacao falhou, binario ausente,
             etc.). Em falha, registra ERROR identificando a etapa.
    """
    # Import isolado: pty so e importado quando esta funcao e chamada.
    # Nenhum outro lugar do script depende deste modulo.
    import pty
    import select
    import errno

    if not senha:
        gravar_log(caminho_log_local, nivel_falha,
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
                gravar_log(caminho_log_local, nivel_falha,
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
            pediu_senha = (
                "password:" in buffer_lower
                or "password for" in buffer_lower
                or "'s password" in buffer_lower
            )
            # v2.3.0: prompt de senha DEPOIS de ja ter enviado a senha e
            # recusa (o sshd pede de novo em vez de fechar, comum com
            # keyboard-interactive, ex. SLE 11 com usuario inexistente).
            # Antes a funcao esperava o timeout de 30 s a cada host assim;
            # agora encerra na hora, sem reenviar a senha.
            if senha_enviada and pediu_senha:
                gravar_log(caminho_log_local, nivel_falha,
                           "[{}] Bootstrap SSH: senha recusada para '{}' "
                           "(o servidor pediu a senha de novo)".format(
                               ip, ssh_user),
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
            if (not senha_enviada) and pediu_senha:
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
                gravar_log(caminho_log_local, nivel_falha,
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
        gravar_log(caminho_log_local, nivel_falha,
                   "[{}] Bootstrap SSH: ssh-copy-id encerrou com rc={} "
                   "(cauda: {})".format(ip, rc, cauda or "vazio"),
                   verbose, False)
    return False


def prepara_autenticacao_ssh(ip, ssh_user, ssh_pass,
                              caminho_log_local, verbose, nivel_falha="ERROR"):
    """
    NAME: prepara_autenticacao_ssh
    DESCRIPTION: Orquestra o bootstrap de autenticacao SSH para um host.
                 Fluxo em ordem:
                   1. Tenta conexao via chave (testa_conexao_ssh).
                      Caminho feliz: retorna True sem mais nenhuma acao.
                   2. Sem chave autorizada e sem senha SSH, desiste.
                   3. v2.3.4: le o banner do sshd e escolhe a ordem dos
                      tipos de chave (_tipos_de_chave): ed25519 e depois
                      RSA; so RSA para OpenSSH anterior ao 6.5 (SLE 11).
                      A chave de cada tipo e gerada se nao existir.
                   4. Chama _ssh_copy_id_com_senha (unica funcao com
                      pty) para distribuir a chave. Senha recusada
                      encerra, sem tentar a chave seguinte.
                   5. Apos copy-id, testa a conexao novamente; se falhar,
                      volta ao passo 4 com o tipo seguinte.
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
               nivel_falha       - nivel de log das recusas de acesso
                                   (v2.3.0; WARNING quando outro perfil
                                   ainda sera tentado)
    RETURNS: bool, True se o host esta acessivel via chave apos o
             bootstrap. False indica falha definitiva (caller marca
             como INACESSIVEL).
    """
    # 1. Caminho feliz: alguma chave do usuario ja esta autorizada
    # (BatchMode=yes, sem -i: o cliente oferece todas as chaves padrao).
    ok, _ = _testa_e_mede(ip, ssh_user, caminho_log_local, verbose)
    if ok:
        return True

    # 2. Sem chave autorizada, so a senha permite distribuir uma.
    if not ssh_pass:
        gravar_log(caminho_log_local, nivel_falha,
                   "[{}] Bootstrap SSH: chave nao autorizada e nenhuma "
                   "senha SSH fornecida (use --ssh-pass, SSH_PASS env ou "
                   "--ssh-pass-file)".format(ip),
                   verbose, False)
        return False

    # 3. v2.3.4: o tipo de chave depende do sshd do alvo (banner).
    banner = versao_servidor_ssh(ip)
    distribuidas = []
    cortado = False
    for tipo in _tipos_de_chave(banner):
        # Protegido por lock porque a chave e um recurso compartilhado
        # entre todos os hosts/threads (ver _lock_chave_ssh_local acima):
        # sem isso, com --parallel > 1 e nenhuma chave previa, duas
        # threads podem tentar gerar a mesma chave ao mesmo tempo e uma
        # falha por corrida.
        with _lock_chave_ssh_local:
            chave_priv, chave_pub = _obtem_chave_do_tipo(
                tipo, caminho_log_local, verbose)
        if chave_priv is None:
            continue

        # 4. Distribui a chave via ssh-copy-id
        gravar_log(caminho_log_local, "INFO",
                   "[{}] Bootstrap SSH: distribuindo chave publica {} via "
                   "ssh-copy-id".format(ip, os.path.basename(chave_pub)),
                   verbose, False)
        sucesso_copy = _ssh_copy_id_com_senha(
            ip, ssh_user, ssh_pass, chave_pub,
            caminho_log_local, verbose, nivel_falha,
        )
        if not sucesso_copy:
            # _ssh_copy_id_com_senha ja registrou o ERROR especifico da
            # etapa. Senha recusada nao e reenviada com outra chave.
            return False

        # 5. Reconfere via chave apos copy-id
        ok, cortou = _testa_e_mede(ip, ssh_user, caminho_log_local, verbose)
        cortado = cortado or cortou
        if ok:
            gravar_log(caminho_log_local, "INFO",
                       "[{}] Bootstrap SSH: chave {} distribuida e conexao "
                       "por chave validada".format(
                           ip, os.path.basename(chave_pub)),
                       verbose, False)
            return True
        distribuidas.append(os.path.basename(chave_pub))

    if not distribuidas:
        gravar_log(caminho_log_local, "ERROR",
                   "[{}] Bootstrap SSH: nao foi possivel obter uma "
                   "chave SSH local".format(ip),
                   verbose, False)
        return False

    gravar_log(caminho_log_local, nivel_falha,
               "[{}] Bootstrap SSH: ssh-copy-id reportou sucesso mas a "
               "reconexao por chave ainda falha (chave {}, servidor {}{})".format(
                   ip, " e ".join(distribuidas),
                   banner or "banner nao lido",
                   "; teste cortado pelo limite de {} s, aumentar "
                   "--ssh-timeout".format(ssh_utils.TIMEOUT_TESTE_CONEXAO)
                   if cortado else ""),
               verbose, False)
    return False

