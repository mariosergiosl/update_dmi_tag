#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: update_dmi_tag.py
#
# USAGE: update_dmi_tag.py [opcoes]
#        update_dmi_tag.py --hosts <arquivo> [opcoes]
#
# DESCRIPTION: Utilitario para ler um valor patrimonial de 13 ou 14 digitos
#              de um arquivo de configuracao local ou remoto, realizar a
#              validacao de Modulo 11 (Banco do Brasil) e gravar o campo
#              DMI Asset Tag na BIOS AMI. Suporta dois mecanismos de
#              escrita em cascata:
#                1. amidelnx_64 (binario AMI, tenta primeiro)
#                2. amibios_dmi via sysfs (fallback)
#              Suporta execucao standalone (local) e remota (lista de IPs
#              via SSH). Oferece Dry-Run de seguranca por padrao.
#
# OPTIONS: ver ajuda em "--help"
#
# REQUIREMENTS: python3 (stdlib apenas, 3.6+)
#               amidelnx_64 e/ou modulo de kernel amibios_dmi
#               ssh, scp (para modo remoto)
#
# BUGS: ---
#
# NOTES: Codificacao US-ASCII nos comentarios e codigo-fonte.
#        Acentos apenas em documentos externos (.md, .docx).
#
# AUTHOR: Mario Luz
#
# VERSION: 2.1.0
#
# CREATED: 2026-05-29
# REVISION: 2026-06-01 - Auditoria de versoes (RPM, modulo, script), distincao
#                        entre modulo carregado e interface SMI pronta, e
#                        instalacao opcional do KMP via zypper somente em -w.
#           2026-06-02 - Versao SMBIOS no log; validacao do patrimonio antes
#                        de instalar/gravar; BEM_NUMERO ausente ou vazio
#                        tratado como estado pendente (rc=10).
#           2026-06-05 - v2.0.0: cascata amidelnx_64 + amibios_dmi; modo
#                        remoto via SSH com lista de hosts; log duplo
#                        (remoto + local consolidado); tabela de resumo;
#                        flag --production para reinstall-enable e reboot;
#                        scp automatico do amidelnx_64; deteccao de WSMT,
#                        sudo, placa, kernel, OS em modo remoto.
#           2026-06-11 - v2.0.2: tres fixes operacionais:
#                        (1) garante_amidelnx_remoto detectava o binario
#                            de forma incorreta (rc do test mascarado pelo
#                            echo final), fazendo o scp nunca ser chamado
#                            quando o binario estava ausente. Corrigido
#                            para usar o rc direto do test -f.
#                        (2) scp_arquivo passou a ter funcao companion
#                            _scp_arquivo_com_erro que devolve o stderr
#                            do scp, eliminando falhas silenciosas. A
#                            funcao original permanece intacta para
#                            compatibilidade.
#                        (3) Modo remoto: reinstall-enable e reboot
#                            (--production) so executam quando a gravacao
#                            da tag retornou OK. Antes, executavam mesmo
#                            apos FALHOU-todos, podendo reiniciar hosts
#                            sem que a tag tivesse sido atualizada.
#           2026-06-12 - v2.0.3: dois fixes operacionais:
#                        (1) le_arquivo_hosts passou a ignorar linhas
#                            iniciando com '#' (comentarios inteiros) e
#                            tambem comentarios em fim de linha
#                            ("192.168.1.10 # equip-01"). Antes, linhas
#                            de comentario do arquivo de hosts eram
#                            tratadas como IPs invalidos e apareciam
#                            como INACESSIVEL na tabela de resumo.
#                        (2) Log local consolidado (--log-local) deixou
#                            de ser truncado a cada execucao. Agora abre
#                            em modo append, preservando o historico de
#                            todas as rodadas em um unico arquivo. Cada
#                            nova execucao e separada por linha em
#                            branco do bloco anterior.
#           2026-06-12 - v2.1.0: duas funcionalidades novas e melhoria
#                        de relatorio:
#                        (1) Sincronizacao do BBconfig.conf apos
#                            gravacao bem-sucedida na BIOS (somente com
#                            --write). Se o BEM_NUMERO em uso diferir do
#                            valor no BBconfig.conf remoto/local, o
#                            script faz backup do arquivo original
#                            (timestamp + usuario SSH no nome), marca o
#                            backup como imutavel (chattr +i, melhor
#                            esforco), atualiza BEM_NUMERO no arquivo
#                            original via sed -i, e confirma o novo
#                            valor com grep. Nome do backup e logado e
#                            aparece na tabela de resumo. Implementado
#                            tanto para modo remoto (sincroniza_bbcon-
#                            fig_remoto) quanto standalone (sincroni-
#                            za_bbconfig_local).
#                        (2) Tabela de resumo (monta_tabela_resumo)
#                            reescrita: tabela detalhada agora inclui
#                            colunas BIOS (distingue H4U02PER de H4U03
#                            etc, antes confundidos sob "Daten Tecnolo-
#                            gia Ltda DH..."), BBconfig (status da
#                            sincronizacao) e Backup (nome do arquivo
#                            gerado). Nome do fabricante "Daten
#                            Tecnologia Ltda" normalizado para "Daten"
#                            para liberar espaco. Apos a tabela
#                            detalhada, novo SUMARIO AGREGADO agrupa por
#                            (BIOS, flag -w, Resultado) com contagem e
#                            descricao em linguagem natural do que cada
#                            status significa.
#
# =======================================================================
#
# COMPATIBILITY:
#
# Modelos de placa-mae testados ate a data desta versao:
#
# +-------------------------+-------------+--------+----------+--------+
# | Modelo                  | BIOS        | SMBIOS | WSMT     | Status |
# +-------------------------+-------------+--------+----------+--------+
# | Gigabyte GA-H110TN-M    | AMI Aptio V | 3.0.0  | Ausente  | OK     |
# | PERTO SA H310M M.2      | AMI Aptio V | 3.1.1  | Presente | OK     |
# | ASUS PRIME H610M-E D4   | AMI Aptio V | 3.4.0  | Presente | OK     |
# | Daten DH4UP             | AMI Aptio V | ---    | Presente | OK     |
# | Daten DH3UP             | AMI Aptio V | 3.1.1  | Presente | FALHA  |
# | Daten H4U02PER          | AMI Aptio V | 3.2.0  | Presente | FALHA  |
# +-------------------------+-------------+--------+----------+--------+
#
# Modelos com Status OK gravam com sucesso via amidelnx_64 (Mecanismo 1).
# O amibios_dmi (Mecanismo 2) so funciona na Gigabyte GA-H110TN-M (unica
# sem WSMT). Nos demais, falha com SMI error 0x84 (handler bloqueado
# pela WSMT) e o script usa automaticamente o Mecanismo 1.
#
# Modelos Daten DH3UP e H4U02PER apresentam Error 24 ("Problem allocating
# BIOS buffer") no amidelnx_64. Causa raiz: WSMT + CONFIG_STRICT_DEVMEM +
# kernel lockdown integrity (Secure Boot ativo) bloqueiam alocacao de
# buffer fisico necessaria para o handler SMI. Sem solucao no script
# atual; em avaliacao via AMIDEEFIx64.EFI por UEFI Shell pre-boot.
#
# =======================================================================

"""
Utilitario de atualizacao do campo DMI Asset Tag na BIOS AMI.
Cascata: amidelnx_64 (primeiro) -> amibios_dmi sysfs (fallback).
Modos: standalone (local) e remoto (lista de IPs via SSH).
Codificacao: US-ASCII (sem acentos nos comentarios ou codigo-fonte).
"""

import argparse
import os
import subprocess
import sys
import time


# =======================================================================
# EXCECOES CUSTOMIZADAS
# =======================================================================

class PatrimonioPendenteError(Exception):
    """
    NAME: PatrimonioPendenteError
    DESCRIPTION: Sinaliza que o BEM_NUMERO esta ausente ou vazio no arquivo
                 de configuracao. Em producao isso e um estado PENDENTE
                 (numero populado depois via DBUS), nao uma falha.
                 O fluxo encerra com WARNING e rc=10, sem instalar modulo
                 nem gravar na BIOS.
    """


class MecanismoIndisponivelError(Exception):
    """
    NAME: MecanismoIndisponivelError
    DESCRIPTION: Sinaliza que um mecanismo de escrita especifico nao esta
                 disponivel no host alvo (binario ausente, modulo nao
                 carregavel, etc.). Permite que a cascata tente o proximo.
    """


class TodosMecanismosFalharam(Exception):
    """
    NAME: TodosMecanismosFalharam
    DESCRIPTION: Sinaliza que todos os mecanismos de escrita da cascata
                 foram tentados e nenhum obteve sucesso. Encerra com rc=6.
    """



# =======================================================================
# CONSTANTES DE CONFIGURACAO E VALORES PADRAO DO PROJETO
# =======================================================================

SCRIPT_VERSION = "2.1.0"

# --- Arquivo de configuracao corporativo ---
DEFAULT_CONFIG_FILE    = "/etc/BBconfig.conf"
DEFAULT_VAR_NAME       = "BEM_NUMERO"

# --- Log standalone (gravado no proprio host) ---
DEFAULT_LOG_FILE       = "/var/log/update_dmi_tag.log"

# --- Log local consolidado (modo remoto, gravado onde o script roda) ---
DEFAULT_LOCAL_LOG_FILE = "./update_dmi_tag_remoto.log"

# --- Mecanismo 1: amidelnx_64 (binario AMI, tenta primeiro) ---
# Caminho padrao no host REMOTO onde o binario e esperado/copiado.
# Usa ~ (home do usuario SSH), expandido pelo shell remoto.
# Sobrescrevivel via --amide-remote-path.
DEFAULT_AMIDE_REMOTE_PATH = "~/amidelnx_64"
# Caminho local do binario (para scp). Default: mesmo diretorio do script.
DEFAULT_AMIDE_LOCAL_PATH  = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "amidelnx_64"
)
# Pacote OBS do amidelnx_64 (para instalacao futura via zypper).
DEFAULT_AMIDE_PACKAGE     = "amidelnx64"
# Repo OBS do amidelnx_64 (para instalacao futura via zypper).
DEFAULT_AMIDE_REPO_URL    = (
    "https://pkgserver.desenv.bb.com.br/repo/"
    "home:/c1103788:/branches:/home:/c1103788/SLE_15_SP7/"
)

# --- Mecanismo 2: amibios_dmi via sysfs (fallback) ---
DEFAULT_SYSFS_TARGET   = "/sys/firmware/amibios/chassis/asset_tag"
DEFAULT_MODULE_REPO_URL = (
    "https://pkgserver.desenv.bb.com.br/repo/"
    "home:/c1103788:/branches:/home:/c1103788/SLE_15_SP7/"
)
DEFAULT_MODULE_PACKAGE  = "amibios-dmi-kmp-default"

# Caminhos sysfs para distinguir "modulo carregado" de "interface SMI pronta".
# /sys/module/amibios_dmi existe se o modulo foi inserido no kernel.
# /sys/firmware/amibios so existe se, alem disso, o handshake SMI teve sucesso.
SYSMODULE_PATH          = "/sys/module/amibios_dmi"
SYSFS_IFACE_PATH        = "/sys/firmware/amibios"

# --- SSH ---
# Usuario SSH: detectado da sessao atual (USER ou LOGNAME), sem hardcode.
def _detecta_usuario_sessao() -> str:
    """Retorna o usuario da sessao atual para uso como default de SSH."""
    for var in ("USER", "LOGNAME"):
        val = os.environ.get(var, "").strip()
        if val:
            return val
    try:
        return os.getlogin()
    except Exception:
        return "root"

DEFAULT_SSH_USER        = _detecta_usuario_sessao()
SSH_OPTS                = [
    "-q",
    "-o", "ConnectTimeout=10",
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=no",
]

# --- Chaves SSH locais para bootstrap de autenticacao ---
# Caminhos padrao das chaves SSH do usuario que executa o script.
# Sao verificadas em ordem (RSA primeiro por compatibilidade legada,
# ed25519 como padrao moderno). Se nenhuma existir, o script gera
# id_ed25519 automaticamente via ssh-keygen sem passphrase.
DEFAULT_SSH_KEY_RSA     = os.path.expanduser("~/.ssh/id_rsa")
DEFAULT_SSH_KEY_ED25519 = os.path.expanduser("~/.ssh/id_ed25519")

# --- Codigos de saida mapeados ---
RC_OK                   = 0
RC_WRITE_INTEGRITY_FAIL = 2
RC_FILE_NOT_FOUND       = 3
RC_PERMISSION_ERROR     = 4
RC_VALIDATION_ERROR     = 5
RC_ALL_MECHANISMS_FAILED = 6
RC_PATRIMONIO_PENDENTE  = 10
RC_UNKNOWN_ERROR        = 99



# =======================================================================
# UTILITARIOS DE LOG
# =======================================================================

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


# =======================================================================
# BOOTSTRAP DE AUTENTICACAO SSH
#
# Este bloco lida com o setup de autenticacao por chave publica ANTES do
# fluxo principal de execucao SSH. As funcoes aqui sao chamadas no inicio
# do processamento de cada host pela orquestradora prepara_autenticacao_ssh.
#
# Apos o bootstrap, o fluxo principal usa ssh_run e scp_arquivo normais
# com BatchMode=yes intacto. O uso de pty fica isolado em uma unica
# funcao: _ssh_copy_id_com_senha. Nenhuma outra parte do script importa
# ou usa pty.
# =======================================================================

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


# =======================================================================
# UTILITARIOS SSH
# =======================================================================

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
    DESCRIPTION: Detecta se o sudo no host remoto requer senha ou nao.
                 Tenta primeiro sudo -n (sem senha). Se funcionar retorna
                 "sudo". Se falhar e sudo_pass for fornecido, verifica se
                 a senha funciona com sudo -S. Banner corporativo do BB
                 e filtrado antes da avaliacao. Fallback: sudo sem senha.
    PARAMETER: ip        - endereco IP do host remoto
               ssh_user  - usuario SSH
               sudo_pass - senha do sudo (opcional)
    RETURNS: str -- prefixo sudo a usar nos comandos remotos
    """
    rc, _, _ = ssh_run(ip, ssh_user, "sudo -n true 2>/dev/null", timeout=10)
    if rc == 0:
        return "sudo"
    if sudo_pass:
        rc2, stdout2, _ = ssh_run(
            ip, ssh_user,
            "echo '{}' | sudo -S true 2>/dev/null && echo SUDOOK".format(sudo_pass),
            timeout=10,
        )
        if 'SUDOOK' in _filtra_banner(stdout2) or rc2 == 0:
            return "echo '{}' | sudo -S".format(sudo_pass)
    return "sudo"


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


# =======================================================================
# AUDITORIA DE AMBIENTE E HARDWARE
# =======================================================================

def _le_sysfs(caminho):
    """
    NAME: _le_sysfs
    DESCRIPTION: Leitura segura de um arquivo sysfs local. Retorna o
                 conteudo em strip() ou "DESCONHECIDO" em caso de falha.
    PARAMETER: caminho - caminho do arquivo sysfs
    RETURNS: str
    """
    try:
        with open(caminho, "r") as f:
            return f.read().strip()
    except Exception:
        return "DESCONHECIDO"


def _le_smbios_local():
    """
    NAME: _le_smbios_local
    DESCRIPTION: Determina a versao SMBIOS lendo o entry point diretamente
                 do kernel, sem dmidecode. Suporta ancora de 64 bits
                 (_SM3_, SMBIOS 3.x) e de 32 bits (_SM_, SMBIOS 2.x).
    PARAMETER: nenhum
    RETURNS: str -- versao no formato "X.Y.Z" ou "DESCONHECIDO"
    """
    try:
        with open("/sys/firmware/dmi/tables/smbios_entry_point", "rb") as f:
            ep = f.read()
        if ep[:5] == b"_SM3_":
            return "{}.{}.{}".format(ep[7], ep[8], ep[9])
        if ep[:4] == b"_SM_":
            return "{}.{}".format(ep[6], ep[7])
    except Exception:
        pass
    return "DESCONHECIDO"


def _detecta_wsmt_local():
    """
    NAME: _detecta_wsmt_local
    DESCRIPTION: Verifica presenca de WSMT no dmesg local.
    PARAMETER: nenhum
    RETURNS: tuple(bool, str) -- (wsmt_presente, linha_dmesg_ou_vazio)
    """
    try:
        resultado = subprocess.run(
            ["dmesg"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=10,
        )
        for linha in resultado.stdout.splitlines():
            if "wsmt" in linha.lower():
                return True, linha.strip()
    except Exception:
        pass
    return False, ""


def coletar_dados_ambiente(caminho_log, verbose, suprime_tela, caminho_log_local=""):
    """
    NAME: coletar_dados_ambiente
    DESCRIPTION: Coleta e registra metadados estruturados do hardware e
                 kernel Linux do host LOCAL. Le sysfs nativamente sem
                 depender de subprocessos externos. Registra: kernel,
                 fabricante e modelo da placa-mae, versao da BIOS,
                 versao SMBIOS e presenca de WSMT.
    PARAMETER: caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional, modo remoto)
    RETURNS: dict -- dicionario com os dados coletados
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    dados = {}

    dados["kernel"]          = _le_sysfs("/proc/sys/kernel/osrelease")
    dados["board_vendor"]    = _le_sysfs("/sys/class/dmi/id/board_vendor")
    dados["board_name"]      = _le_sysfs("/sys/class/dmi/id/board_name")
    dados["bios_vendor"]     = _le_sysfs("/sys/class/dmi/id/bios_vendor")
    dados["bios_version"]    = _le_sysfs("/sys/class/dmi/id/bios_version")
    dados["smbios_version"]  = _le_smbios_local()
    dados["hostname"]        = _le_sysfs("/proc/sys/kernel/hostname")

    wsmt_presente, wsmt_linha = _detecta_wsmt_local()
    dados["wsmt"]            = "Presente" if wsmt_presente else "Ausente"
    dados["wsmt_detalhe"]    = wsmt_linha

    # Leitura do OS release para nome legivel
    dados["os_pretty"] = "DESCONHECIDO"
    try:
        with open("/etc/os-release", "r") as f:
            for linha in f:
                if linha.startswith("PRETTY_NAME="):
                    dados["os_pretty"] = linha.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        pass

    _log("INFO", "--- AUDITORIA DE AMBIENTE E HARDWARE ---")
    _log("INFO", "Kernel OS  : {}".format(dados["kernel"]))
    _log("INFO", "OS         : {}".format(dados["os_pretty"]))
    _log("INFO", "Hostname   : {}".format(dados["hostname"]))
    _log("INFO", "Placa-Mae  : {} {}".format(dados["board_vendor"], dados["board_name"]))
    _log("INFO", "BIOS Info  : {} {}".format(dados["bios_vendor"], dados["bios_version"]))
    _log("INFO", "SMBIOS Ver : {}".format(dados["smbios_version"]))
    _log("INFO", "WSMT       : {}".format(dados["wsmt"]))
    if wsmt_presente and wsmt_linha:
        _log("DEBUG", "WSMT detalhe: {}".format(wsmt_linha))
    _log("INFO", "-----------------------------------------")

    return dados


def coletar_dados_ambiente_remoto(ip, ssh_user, sudo_cmd, caminho_log,
                                  caminho_log_local, verbose, suprime_tela):
    """
    NAME: coletar_dados_ambiente_remoto
    DESCRIPTION: Coleta metadados de hardware e kernel de um host REMOTO
                 via SSH. Usa dmidecode com sudo para SMBIOS e asset tag.
                 Filtra o banner corporativo do BB de toda saida sudo.
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               sudo_cmd          - prefixo sudo no host remoto
               caminho_log       - log remoto
               caminho_log_local - log consolidado local
               verbose           - modo verbose
               suprime_tela      - suprime stdout
    RETURNS: dict -- dicionario com os dados coletados
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    def _ssh(cmd, timeout=10):
        _, stdout, stderr = ssh_run(ip, ssh_user, cmd, timeout=timeout)
        # Filtra banner do BB que pode vir no stdout quando stderr e redirecionado
        limpo = _filtra_banner(stdout or "")
        return limpo if limpo else "DESCONHECIDO"

    def _ssh_sudo(cmd, timeout=15):
        """Executa com sudo, filtra banner BB e ruido do dmidecode."""
        _, stdout, stderr = ssh_run(
            ip, ssh_user,
            "{} {} 2>/dev/null".format(sudo_cmd, cmd),
            timeout=timeout,
        )
        limpo = _filtra_banner((stdout or "") + "\n" + (stderr or ""))
        RUIDO = ("Getting SMBIOS data", "# dmidecode",)
        linhas_uteis = [l.strip() for l in limpo.splitlines()
                        if l.strip() and not any(r in l for r in RUIDO)]
        return "\n".join(linhas_uteis) if linhas_uteis else "DESCONHECIDO"

    dados = {}

    dados["kernel"]       = _ssh("cat /proc/sys/kernel/osrelease")
    dados["hostname"]     = _ssh("hostname")
    dados["board_vendor"] = _ssh("cat /sys/class/dmi/id/board_vendor")
    dados["board_name"]   = _ssh("cat /sys/class/dmi/id/board_name")
    dados["bios_vendor"]  = _ssh("cat /sys/class/dmi/id/bios_vendor")
    dados["bios_version"] = _ssh("cat /sys/class/dmi/id/bios_version")

    dados["os_pretty"] = _ssh(
        "grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | sed s/\\\"//g"
    )

    import re as _re
    smbios_raw = _ssh_sudo("dmidecode 2>/dev/null | grep -i SMBIOS | head -3")
    m = _re.search(r"(\d+\.\d+\.?\d*)", smbios_raw)
    dados["smbios_version"] = m.group(1) if m else "DESCONHECIDO"

    # WSMT via dmesg com sudo
    wsmt_raw = _ssh_sudo("dmesg | grep -i wsmt | head -3")
    if wsmt_raw and wsmt_raw != "DESCONHECIDO":
        dados["wsmt"]         = "Presente"
        dados["wsmt_detalhe"] = wsmt_raw
    else:
        dados["wsmt"]         = "Ausente"
        dados["wsmt_detalhe"] = ""

    # Asset tag atual via dmidecode com sudo
    dados["tag_atual"] = _ssh_sudo("dmidecode -s chassis-asset-tag")

    # UEFI
    efi_check = _ssh("ls /sys/firmware/efi/efivars/ 2>/dev/null | head -1")
    dados["uefi"] = "Confirmado" if (efi_check and efi_check != "DESCONHECIDO") else "Nao detectado"

    _log("INFO", "--- AUDITORIA DE AMBIENTE E HARDWARE ---")
    _log("INFO", "Kernel OS  : {}".format(dados["kernel"]))
    _log("INFO", "OS         : {}".format(dados["os_pretty"]))
    _log("INFO", "Hostname   : {}".format(dados["hostname"]))
    _log("INFO", "Placa-Mae  : {} {}".format(dados["board_vendor"], dados["board_name"]))
    _log("INFO", "BIOS Info  : {} {}".format(dados["bios_vendor"], dados["bios_version"]))
    _log("INFO", "SMBIOS Ver : {}".format(dados["smbios_version"]))
    _log("INFO", "WSMT       : {}".format(dados["wsmt"]))
    if dados["wsmt_detalhe"]:
        for _wl in dados["wsmt_detalhe"].splitlines():
            _wl = _wl.strip()
            if _wl and "ACPI" in _wl:
                _log("DEBUG", "WSMT: {}".format(_wl))
    _log("INFO", "UEFI       : {}".format(dados["uefi"]))
    _log("INFO", "Tag atual  : {}".format(dados["tag_atual"]))
    _log("INFO", "-----------------------------------------")

    return dados



def verifica_pacote_rpm(nome_pacote, caminho_log, verbose, suprime_tela,
                        caminho_log_local=""):
    """
    NAME: verifica_pacote_rpm
    DESCRIPTION: Verifica a instalacao de um pacote RPM via rpm -q.
                 Loga o NVR completo se instalado, ou ausencia se nao.
                 Retorna True se instalado, False caso contrario.
    PARAMETER: nome_pacote       - nome do pacote RPM a verificar
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: bool
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    try:
        resultado = subprocess.run(
            ["rpm", "-q", nome_pacote],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        instalado = resultado.returncode == 0
        if instalado:
            nvr = resultado.stdout.strip() or nome_pacote
            _log("DEBUG", "Dependencia RPM ativa: {}".format(nvr))
        else:
            _log("DEBUG", "Dependencia RPM ausente: {}".format(nome_pacote))
        return instalado
    except FileNotFoundError:
        _log("DEBUG", "Comando rpm indisponivel para testar {}".format(nome_pacote))
        return False


def loga_versao_modulo(caminho_log, verbose, suprime_tela, caminho_log_local=""):
    """
    NAME: loga_versao_modulo
    DESCRIPTION: Registra em log a identificacao do modulo amibios_dmi via
                 modinfo. Os campos version, srcversion e vermagic identificam
                 o build e o kernel-alvo, util para auditoria de compatibilidade.
    PARAMETER: caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: None
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    for campo in ("version", "srcversion", "vermagic"):
        try:
            resultado = subprocess.run(
                ["modinfo", "-F", campo, "amibios_dmi"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False,
            )
            valor = resultado.stdout.strip()
            if valor:
                _log("DEBUG", "Modulo amibios_dmi {}: {}".format(campo, valor))
        except FileNotFoundError:
            _log("DEBUG", "Comando modinfo indisponivel para auditoria do modulo")
            return


def instala_modulo_via_zypper(repo_url, pacote, caminho_log, verbose,
                               suprime_tela, caminho_log_local=""):
    """
    NAME: instala_modulo_via_zypper
    DESCRIPTION: Tenta instalar um pacote KMP via zypper usando repositorio
                 transitorio (--plus-repo), modo nao-interativo e sem
                 verificacao de GPG. O zypper resolve a variante KMP correta
                 para o kernel em execucao. Retorna True somente se rc=0.
    PARAMETER: repo_url          - URL raiz do repositorio zypper
               pacote            - nome do pacote a instalar
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: bool
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    comando = [
        "zypper", "--non-interactive", "--no-gpg-checks",
        "--plus-repo", repo_url,
        "install", pacote,
    ]
    _log("INFO", "Tentando instalar '{}' via zypper (repo: {})...".format(
        pacote, repo_url))
    try:
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=300,
        )
    except FileNotFoundError:
        _log("ERROR", "Comando zypper indisponivel; instalacao abortada.")
        return False
    except subprocess.TimeoutExpired:
        _log("ERROR", "Timeout (300s) ao instalar '{}' via zypper.".format(pacote))
        return False

    if resultado.returncode == 0:
        _log("INFO", "Pacote '{}' instalado com sucesso via zypper.".format(pacote))
        return True

    _log("ERROR", "Falha ao instalar '{}' (zypper rc={}): {}".format(
        pacote, resultado.returncode, resultado.stderr.strip()))
    return False


def modulo_esta_carregado():
    """
    NAME: modulo_esta_carregado
    DESCRIPTION: Indica se o modulo amibios_dmi esta efetivamente inserido
                 no kernel. Diferente de a interface SMI estar pronta.
    PARAMETER: nenhum
    RETURNS: bool
    """
    return os.path.exists(SYSMODULE_PATH)


def interface_esta_pronta():
    """
    NAME: interface_esta_pronta
    DESCRIPTION: Indica se a interface sysfs da BIOS AMI foi exposta.
                 So existe quando o modulo carregou E o handshake SMI
                 (smi_info) funcionou com sucesso.
    PARAMETER: nenhum
    RETURNS: bool
    """
    return os.path.exists(SYSFS_IFACE_PATH)


# =======================================================================
# VALIDACAO E LEITURA DE CONFIGURACAO
# =======================================================================

def calcula_dv_modulo11(base_num):
    """
    NAME: calcula_dv_modulo11
    DESCRIPTION: Calcula o digito verificador usando o algoritmo de Modulo 11
                 do Banco do Brasil. Multiplicadores da direita para a
                 esquerda: 2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5, 6.
                 Se o resultado for 10 ou 11, retorna "0".
    PARAMETER: base_num - string numerica de 13 digitos
    RETURNS: str -- digito verificador ("0" a "9")
    """
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(d) * p for d, p in zip(base_num, pesos))
    resto = soma % 11
    dv = 11 - resto
    if dv in (10, 11):
        return "0"
    return str(dv)


def valida_via_patrimonial_cli(base_num, caminho_log, verbose, suprime_tela,
                                caminho_log_local=""):
    """
    NAME: valida_via_patrimonial_cli
    DESCRIPTION: Validacao redundante via utilitario CLI oficial patrimonial.
                 Retorna o valor de 14 digitos resultante ou string vazia
                 em caso de falha ou indisponibilidade do comando.
    PARAMETER: base_num          - string numerica de 13 digitos
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: str -- 14 digitos ou string vazia
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    try:
        resultado = subprocess.run(
            ["patrimonial", "--non-strict", base_num],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        if resultado.returncode == 0:
            saida = resultado.stdout.strip()
            numeros = "".join(filter(str.isdigit, saida))
            _log("DEBUG", "Validacao redundante CLI patrimonial: {}".format(numeros))
            return numeros
    except FileNotFoundError:
        _log("DEBUG", "Comando CLI patrimonial nao esta no PATH")
    return ""


def le_valor_configuracao(caminho_config, nome_var, caminho_log, verbose,
                           suprime_tela, caminho_log_local=""):
    """
    NAME: le_valor_configuracao
    DESCRIPTION: Parsing manual e leve do arquivo de configuracao chave=valor.
                 Nao utiliza a biblioteca re para otimizacao de memoria e
                 portabilidade (Python 3.6+ stdlib puro). Ignora linhas
                 vazias e comentarios (# e ;). Remove aspas delimitadoras.
                 Levanta PatrimonioPendenteError se a variavel nao for
                 encontrada (estado pendente, nao falha de erro).
    PARAMETER: caminho_config    - caminho do arquivo de configuracao
               nome_var          - nome da variavel a extrair
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: str -- valor extraido
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    _log("DEBUG", "Iniciando leitura de {}...".format(caminho_config))

    if not os.path.exists(caminho_config):
        _log("ERROR", "Configuracao ausente: {}".format(caminho_config))
        raise FileNotFoundError(
            "Arquivo de configuracao nao encontrado: {}".format(caminho_config))

    with open(caminho_config, "r", encoding="utf-8", errors="ignore") as f:
        for linha in f:
            linha_limpa = linha.strip()
            if not linha_limpa or linha_limpa.startswith(("#", ";")):
                continue
            if "=" in linha_limpa:
                partes = linha_limpa.split("=", 1)
                chave = partes[0].strip()
                if chave == nome_var:
                    valor = partes[1].strip().strip("'\"")
                    _log("INFO", "Variavel '{}' extraida: {}".format(nome_var, valor))
                    return valor

    # Variavel ausente e estado pendente em producao (DBUS popula depois).
    raise PatrimonioPendenteError(
        "Variavel '{}' ausente em {}: provisionamento pendente, nada a gravar.".format(
            nome_var, caminho_config))


def le_valor_configuracao_remoto(ip, ssh_user, caminho_config, nome_var,
                                  caminho_log, caminho_log_local,
                                  verbose, suprime_tela, sudo_cmd=""):
    """
    NAME: le_valor_configuracao_remoto
    DESCRIPTION: Le o valor de uma variavel do arquivo de configuracao em
                 um host remoto via SSH. Sempre loga o que encontrou no
                 arquivo remoto, independentemente de o valor ser sobrescrito
                 pelo BEM_NUMERO da lista de hosts. Retorna string vazia se
                 a variavel nao for encontrada (estado pendente remoto).
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               caminho_config    - caminho do arquivo de configuracao remoto
               nome_var          - nome da variavel a extrair
               caminho_log       - log remoto
               caminho_log_local - log consolidado local
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               sudo_cmd          - prefixo sudo (opcional, para arquivos restritos)
    RETURNS: str -- valor encontrado no arquivo remoto ou string vazia
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    cmd = "grep '^{}=' {} 2>/dev/null | cut -d= -f2 | tr -d '\"'".format(
        nome_var, caminho_config)
    _, stdout, _ = ssh_run(ip, ssh_user, cmd, timeout=10)
    valor_remoto = stdout.strip()

    if valor_remoto:
        _log("INFO", "BBconfig remoto '{}': {}".format(nome_var, valor_remoto))
    else:
        _log("WARNING", "BBconfig remoto: '{}' ausente em {} (pendente)".format(
            nome_var, caminho_config))

    return valor_remoto


# =======================================================================
# SINCRONIZACAO DO ARQUIVO DE CONFIGURACAO (BBconfig.conf)
#
# Apos a gravacao bem-sucedida da tag na BIOS (resultado_escrita
# comecando com "OK") e somente com --write, sincroniza o valor de
# BEM_NUMERO no arquivo de configuracao se ele divergir do valor usado
# para a gravacao. Faz backup do arquivo original antes de editar,
# marca o backup como imutavel (chattr +i, melhor esforco) e confirma
# o novo valor com grep. Em falha na edicao, tenta rollback a partir
# do backup.
# =======================================================================

def _nome_backup_bbconfig(caminho_config, identificador):
    """
    NAME: _nome_backup_bbconfig
    DESCRIPTION: Monta o nome do arquivo de backup do arquivo de
                 configuracao, no formato:
                   <caminho_config>.<YYYY-MM-DD_HHMMSS>_<identificador>.bak
                 O identificador (geralmente o usuario SSH ou usuario
                 local) permite auditar quem gerou o backup e quando.
    PARAMETER: caminho_config - caminho do arquivo original
               identificador  - usuario a incluir no nome (sem espacos)
    RETURNS: str -- caminho completo do arquivo de backup
    """
    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    ident = "".join(c for c in identificador if c.isalnum() or c in "._-") or "unknown"
    return "{}.{}_{}.bak".format(caminho_config, timestamp, ident)


def sincroniza_bbconfig_remoto(ip, ssh_user, sudo_cmd, caminho_config, nome_var,
                                bem_conf, bem_usado,
                                caminho_log, caminho_log_local,
                                verbose, suprime_tela):
    """
    NAME: sincroniza_bbconfig_remoto
    DESCRIPTION: Sincroniza BEM_NUMERO no arquivo de configuracao remoto
                 quando o valor usado para gravar a tag (bem_usado)
                 difere do valor atualmente presente no arquivo
                 (bem_conf). Fluxo:
                   1. Se bem_conf == bem_usado: nada a fazer (IGUAL).
                   2. Verifica existencia do arquivo remoto.
                   3. Gera nome de backup com timestamp + ssh_user.
                   4. sudo cp -p <config> <backup>
                   5. sudo chattr +i <backup> (melhor esforco; falha
                      nao impede a sincronizacao, apenas gera WARNING).
                   6. sudo sed -i 's/^VAR=.*/VAR="novo"/' <config>
                   7. Confirma com grep que o novo valor esta presente.
                   8. Em falha do passo 6/7, tenta rollback: chattr -i
                      no backup + cp do backup de volta ao original.
                 Todas as etapas sao logadas com prefixo [IP]. O nome
                 do backup gerado e sempre logado quando criado, mesmo
                 se passos posteriores falharem (para permitir limpeza
                 manual).
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH (tambem usado no nome
                                    do backup)
               sudo_cmd          - prefixo sudo no host remoto
               caminho_config    - caminho do arquivo de configuracao
               nome_var          - nome da variavel (ex: BEM_NUMERO)
               bem_conf          - valor atual no arquivo ("PENDENTE"
                                    se ausente)
               bem_usado         - valor usado para gravar a tag
               caminho_log       - log remoto
               caminho_log_local - log consolidado local
               verbose           - modo verbose
               suprime_tela      - suprime stdout
    RETURNS: dict -- {"sincronizado": bool, "backup": str ou None,
                       "motivo": str}
             motivo e um codigo curto: "IGUAL", "OK", "SEM-ARQUIVO",
             "FALHOU-backup", "FALHOU-chattr-ok-mesmo-assim",
             "FALHOU-sed-rollback-ok", "FALHOU-sed-rollback-falhou",
             "FALHOU-confirmacao".
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    # 1. Ja sincronizado -- nada a fazer
    if bem_conf and bem_conf == bem_usado:
        _log("DEBUG", "BBconfig.conf ja sincronizado ({}={}).".format(
            nome_var, bem_usado))
        return {"sincronizado": True, "backup": None, "motivo": "IGUAL"}

    # 2. Verifica existencia do arquivo remoto
    rc_test, _, _ = ssh_run(
        ip, ssh_user, "{} test -f {}".format(sudo_cmd, caminho_config),
        timeout=10)
    if rc_test != 0:
        _log("WARNING",
             "BBconfig.conf nao encontrado em {}: sincronizacao pulada.".format(
                 caminho_config))
        return {"sincronizado": False, "backup": None, "motivo": "SEM-ARQUIVO"}

    # 3. Nome do backup
    backup_path = _nome_backup_bbconfig(caminho_config, ssh_user)

    # 4. Backup (cp -p preserva permissoes e timestamps)
    rc_cp, _, err_cp = ssh_run(
        ip, ssh_user,
        "{} cp -p {} {}".format(sudo_cmd, caminho_config, backup_path),
        timeout=15)
    if rc_cp != 0:
        _log("ERROR",
             "Falha ao criar backup de {} em {}: {}".format(
                 caminho_config, backup_path, (err_cp or "").strip()))
        return {"sincronizado": False, "backup": None, "motivo": "FALHOU-backup"}

    _log("INFO", "Backup de {} criado: {}".format(caminho_config, backup_path))

    # 5. Imutabilidade do backup (melhor esforco)
    rc_chattr, _, err_chattr = ssh_run(
        ip, ssh_user,
        "{} chattr +i {}".format(sudo_cmd, backup_path),
        timeout=10)
    chattr_ok = (rc_chattr == 0)
    if not chattr_ok:
        _log("WARNING",
             "chattr +i falhou em {} (sistema de arquivos pode nao suportar): {}".format(
                 backup_path, (err_chattr or "").strip()))

    # 6. Edita o arquivo original via sed -i
    # Usa aspas simples no shell remoto; nome_var e bem_usado sao
    # numericos/identificadores sem caracteres especiais de sed.
    sed_expr = "s/^{0}=.*/{0}=\"{1}\"/".format(nome_var, bem_usado)
    rc_sed, _, err_sed = ssh_run(
        ip, ssh_user,
        "{} sed -i '{}' {}".format(sudo_cmd, sed_expr, caminho_config),
        timeout=15)

    if rc_sed != 0:
        _log("ERROR",
             "sed -i falhou em {}: {}. Tentando rollback a partir do backup.".format(
                 caminho_config, (err_sed or "").strip()))
        return _rollback_bbconfig(
            ip, ssh_user, sudo_cmd, caminho_config, backup_path,
            chattr_ok, "FALHOU-sed", _log)

    # 7. Confirma o novo valor
    cmd_confirma = "grep '^{}=' {} 2>/dev/null | cut -d= -f2 | tr -d '\"'".format(
        nome_var, caminho_config)
    _, stdout_confirma, _ = ssh_run(ip, ssh_user, cmd_confirma, timeout=10)
    valor_confirmado = stdout_confirma.strip()

    if valor_confirmado != bem_usado:
        _log("ERROR",
             "Confirmacao pos-sed falhou: esperado '{}', encontrado '{}'. "
             "Tentando rollback.".format(bem_usado, valor_confirmado))
        return _rollback_bbconfig(
            ip, ssh_user, sudo_cmd, caminho_config, backup_path,
            chattr_ok, "FALHOU-confirmacao", _log)

    _log("INFO",
         "BBconfig.conf atualizado: {}={} -> {}={}. Backup: {}".format(
             nome_var, bem_conf or "PENDENTE", nome_var, bem_usado, backup_path))

    return {"sincronizado": True, "backup": backup_path, "motivo": "OK"}


def _rollback_bbconfig(ip, ssh_user, sudo_cmd, caminho_config, backup_path,
                       chattr_ok, motivo_base, _log):
    """
    NAME: _rollback_bbconfig
    DESCRIPTION: Restaura o arquivo de configuracao remoto a partir do
                 backup apos falha na edicao. Remove a imutabilidade do
                 backup (se havia sido aplicada) antes de copiar de
                 volta, e a reaplica em seguida para preservar o
                 backup intacto para auditoria posterior.
    PARAMETER: ip, ssh_user, sudo_cmd, caminho_config, backup_path -
               mesmos significados de sincroniza_bbconfig_remoto
               chattr_ok    - se o chattr +i do backup havia funcionado
               motivo_base  - prefixo do motivo de falha original
               _log         - funcao de log fechada sobre o contexto
    RETURNS: dict -- {"sincronizado": False, "backup": backup_path,
                       "motivo": "<motivo_base>-rollback-ok"
                                  ou "<motivo_base>-rollback-falhou"}
    """
    if chattr_ok:
        ssh_run(ip, ssh_user, "{} chattr -i {}".format(sudo_cmd, backup_path),
                timeout=10)

    rc_restore, _, err_restore = ssh_run(
        ip, ssh_user,
        "{} cp -p {} {}".format(sudo_cmd, backup_path, caminho_config),
        timeout=15)

    # Reaplica imutabilidade no backup para preservar evidencia
    if chattr_ok:
        ssh_run(ip, ssh_user, "{} chattr +i {}".format(sudo_cmd, backup_path),
                timeout=10)

    if rc_restore == 0:
        _log("WARNING",
             "Rollback de {} a partir do backup {} concluido.".format(
                 caminho_config, backup_path))
        return {"sincronizado": False, "backup": backup_path,
                "motivo": "{}-rollback-ok".format(motivo_base)}

    _log("ERROR",
         "Rollback de {} FALHOU: {}. Arquivo pode estar em estado "
         "inconsistente. Backup preservado em {}.".format(
             caminho_config, (err_restore or "").strip(), backup_path))
    return {"sincronizado": False, "backup": backup_path,
            "motivo": "{}-rollback-falhou".format(motivo_base)}


def sincroniza_bbconfig_local(caminho_config, nome_var, bem_conf, bem_usado,
                               caminho_log, verbose, suprime_tela,
                               caminho_log_local=""):
    """
    NAME: sincroniza_bbconfig_local
    DESCRIPTION: Equivalente local (modo standalone) de
                 sincroniza_bbconfig_remoto. Mesma logica de backup com
                 timestamp + usuario local, chattr +i no backup, sed -i
                 no original e confirmacao via grep, com rollback em
                 falha. Todos os comandos sao executados localmente via
                 subprocess com sudo.
    PARAMETER: caminho_config    - caminho do arquivo de configuracao
               nome_var          - nome da variavel (ex: BEM_NUMERO)
               bem_conf          - valor atual no arquivo
               bem_usado         - valor usado para gravar a tag
               caminho_log       - log principal (standalone)
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: dict -- mesmo formato de sincroniza_bbconfig_remoto
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    if bem_conf and bem_conf == bem_usado:
        _log("DEBUG", "BBconfig.conf ja sincronizado ({}={}).".format(
            nome_var, bem_usado))
        return {"sincronizado": True, "backup": None, "motivo": "IGUAL"}

    if not os.path.isfile(caminho_config):
        _log("WARNING",
             "BBconfig.conf nao encontrado em {}: sincronizacao pulada.".format(
                 caminho_config))
        return {"sincronizado": False, "backup": None, "motivo": "SEM-ARQUIVO"}

    identificador = _detecta_usuario_sessao()
    backup_path = _nome_backup_bbconfig(caminho_config, identificador)

    def _run(cmd_lista, timeout=15):
        try:
            r = subprocess.run(cmd_lista, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=timeout,
                                check=False)
            return r.returncode, r.stdout, r.stderr
        except Exception as e:
            return 1, "", str(e)

    rc_cp, _, err_cp = _run(["sudo", "cp", "-p", caminho_config, backup_path])
    if rc_cp != 0:
        _log("ERROR", "Falha ao criar backup de {} em {}: {}".format(
            caminho_config, backup_path, (err_cp or "").strip()))
        return {"sincronizado": False, "backup": None, "motivo": "FALHOU-backup"}

    _log("INFO", "Backup de {} criado: {}".format(caminho_config, backup_path))

    rc_chattr, _, err_chattr = _run(["sudo", "chattr", "+i", backup_path], timeout=10)
    chattr_ok = (rc_chattr == 0)
    if not chattr_ok:
        _log("WARNING",
             "chattr +i falhou em {} (sistema de arquivos pode nao suportar): {}".format(
                 backup_path, (err_chattr or "").strip()))

    sed_expr = "s/^{0}=.*/{0}=\"{1}\"/".format(nome_var, bem_usado)
    rc_sed, _, err_sed = _run(["sudo", "sed", "-i", sed_expr, caminho_config])

    def _rollback_local(motivo_base):
        if chattr_ok:
            _run(["sudo", "chattr", "-i", backup_path], timeout=10)
        rc_restore, _, err_restore = _run(["sudo", "cp", "-p", backup_path, caminho_config])
        if chattr_ok:
            _run(["sudo", "chattr", "+i", backup_path], timeout=10)
        if rc_restore == 0:
            _log("WARNING", "Rollback de {} a partir do backup {} concluido.".format(
                caminho_config, backup_path))
            return {"sincronizado": False, "backup": backup_path,
                    "motivo": "{}-rollback-ok".format(motivo_base)}
        _log("ERROR",
             "Rollback de {} FALHOU: {}. Backup preservado em {}.".format(
                 caminho_config, (err_restore or "").strip(), backup_path))
        return {"sincronizado": False, "backup": backup_path,
                "motivo": "{}-rollback-falhou".format(motivo_base)}

    if rc_sed != 0:
        _log("ERROR", "sed -i falhou em {}: {}. Tentando rollback.".format(
            caminho_config, (err_sed or "").strip()))
        return _rollback_local("FALHOU-sed")

    # Confirma
    try:
        with open(caminho_config, "r", encoding="utf-8", errors="ignore") as f:
            valor_confirmado = ""
            for linha in f:
                linha_l = linha.strip()
                if linha_l.startswith("{}=".format(nome_var)):
                    valor_confirmado = linha_l.split("=", 1)[1].strip().strip("'\"")
                    break
    except Exception as e:
        _log("ERROR", "Falha ao reabrir {} para confirmacao: {}. Tentando rollback.".format(
            caminho_config, e))
        return _rollback_local("FALHOU-confirmacao")

    if valor_confirmado != bem_usado:
        _log("ERROR",
             "Confirmacao pos-sed falhou: esperado '{}', encontrado '{}'. "
             "Tentando rollback.".format(bem_usado, valor_confirmado))
        return _rollback_local("FALHOU-confirmacao")

    _log("INFO",
         "BBconfig.conf atualizado: {}={} -> {}={}. Backup: {}".format(
             nome_var, bem_conf or "PENDENTE", nome_var, bem_usado, backup_path))

    return {"sincronizado": True, "backup": backup_path, "motivo": "OK"}


def valida_e_calcula_tag(valor_config, caminho_log, verbose, suprime_tela,
                          caminho_log_local=""):
    """
    NAME: valida_e_calcula_tag
    DESCRIPTION: Valida o formato do valor patrimonial (13 ou 14 digitos),
                 calcula ou verifica o DV de Modulo 11 e retorna a tag
                 final de 14 digitos. Centraliza a logica de validacao
                 usada tanto no modo standalone quanto no remoto.
                 Levanta ValueError para formatos invalidos.
    PARAMETER: valor_config      - valor lido do arquivo de configuracao
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: tuple(str, str) -- (tag_esperada_14d, base_13d)
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    if not (valor_config.isdigit() and len(valor_config) in (13, 14)):
        _log("ERROR", "Formato invalido: '{}' (deve ter 13 ou 14 digitos)".format(
            valor_config))
        raise ValueError(
            "Valor lido possui tamanho invalido ({}): {}".format(
                len(valor_config), valor_config))

    if len(valor_config) == 14:
        base_13     = valor_config[:13]
        dv_lido     = valor_config[13]
        dv_calculado = calcula_dv_modulo11(base_13)
        if dv_lido != dv_calculado:
            _log("WARNING",
                 "DV lido ({}) difere do calculado ({}) para base {}!".format(
                     dv_lido, dv_calculado, base_13))
        tag_esperada = valor_config
        _log("INFO", "Valor ja possui 14 digitos. DV verificado: {}".format(
            dv_calculado))
    else:
        base_13      = valor_config
        dv_calculado = calcula_dv_modulo11(base_13)
        tag_esperada = base_13 + dv_calculado
        _log("INFO",
             "Valor possui 13 digitos. DV calculado: {} (Tag: {})".format(
                 dv_calculado, tag_esperada))

    return tag_esperada, base_13


# =======================================================================
# MECANISMO 1: amidelnx_64 (binario AMI, tenta primeiro)
# =======================================================================

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


# =======================================================================
# MECANISMO 2: amibios_dmi via sysfs (fallback)
# =======================================================================

def _carrega_modulo_amibios(caminho_log, verbose, suprime_tela,
                             caminho_log_local=""):
    """
    NAME: _carrega_modulo_amibios
    DESCRIPTION: Tenta carregar o modulo amibios_dmi via modprobe se a
                 interface sysfs ainda nao estiver pronta. Retorna True
                 se a interface ficou disponivel apos a tentativa.
    PARAMETER: caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: bool -- True se interface sysfs esta pronta
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    if interface_esta_pronta():
        return True

    _log("WARNING", "Interface amibios_dmi ausente. Tentando modprobe...")
    try:
        resultado = subprocess.run(
            ["modprobe", "amibios_dmi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=15,
        )
        if interface_esta_pronta():
            _log("INFO", "Modulo amibios_dmi carregado via modprobe.")
            return True
        _log("ERROR",
             "modprobe amibios_dmi nao disponibilizou a interface sysfs: {}".format(
                 resultado.stderr.strip()))
        return False
    except FileNotFoundError:
        _log("ERROR", "Comando modprobe nao encontrado.")
        return False
    except subprocess.TimeoutExpired:
        _log("ERROR", "Timeout ao executar modprobe amibios_dmi.")
        return False


def _descarrega_modulo_amibios(caminho_log, verbose, suprime_tela,
                                caminho_log_local=""):
    """
    NAME: _descarrega_modulo_amibios
    DESCRIPTION: Descarrega o modulo amibios_dmi via modprobe -r.
                 Chamado no bloco finally quando o modulo foi carregado
                 temporariamente pelo script, para preservar integridade
                 do sistema operacional.
    PARAMETER: caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: None
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    _log("INFO", "Descarregando modulo amibios_dmi...")
    try:
        resultado = subprocess.run(
            ["modprobe", "-r", "amibios_dmi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
            timeout=15,
        )
        if not os.path.exists(SYSFS_IFACE_PATH):
            _log("INFO", "Modulo descarregado com sucesso. Sistema integro.")
        else:
            _log("ERROR",
                 "Interface sysfs ainda presente apos modprobe -r: {}".format(
                     resultado.stderr.strip()))
    except Exception as e:
        _log("ERROR", "Falha critica ao descarregar modulo: {}".format(e))


def executa_amibios_local(tag, sysfs_target, kmp_instalado,
                           module_repo_url, module_package,
                           caminho_log, verbose, suprime_tela,
                           dry_run=True, caminho_log_local=""):
    """
    NAME: executa_amibios_local
    DESCRIPTION: Executa o mecanismo amibios_dmi localmente: audita versoes
                 do RPM e do modulo, gerencia o ciclo de vida do modulo
                 (load/unload automatico), le o valor antigo, grava a tag
                 e audita o valor pos-escrita. Em dry_run, nao grava e nao
                 instala o KMP. Levanta MecanismoIndisponivelError se a
                 interface sysfs nao ficar disponivel apos modprobe.
                 O unload do modulo (se carregado pelo script) e garantido
                 no bloco finally mesmo em caso de excecao.
    PARAMETER: tag               - valor de 14 digitos a gravar
               sysfs_target      - caminho do sysfs da asset tag
               kmp_instalado     - bool, resultado de verifica_pacote_rpm
               module_repo_url   - URL do repo zypper do KMP
               module_package    - nome do pacote KMP
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

    modulo_carregado_pelo_script = False

    try:
        # Auditoria de versao do modulo
        loga_versao_modulo(caminho_log, verbose, suprime_tela, caminho_log_local)

        if modulo_esta_carregado():
            _log("DEBUG", "Modulo amibios_dmi presente em /sys/module.")

        # Instalacao do KMP somente em modo real e se nao instalado
        if not interface_esta_pronta():
            if not modulo_esta_carregado() and not kmp_instalado:
                if not dry_run:
                    instala_modulo_via_zypper(
                        module_repo_url, module_package,
                        caminho_log, verbose, suprime_tela, caminho_log_local)
                else:
                    _log("WARNING",
                         "[DRY-RUN] Modulo ausente; instalacao via zypper"
                         " ocorre somente com -w (repo: {}).".format(
                             module_repo_url))

            # Tenta carregar o modulo
            if not _carrega_modulo_amibios(caminho_log, verbose, suprime_tela,
                                            caminho_log_local):
                raise MecanismoIndisponivelError(
                    "Interface sysfs amibios_dmi indisponivel apos modprobe")
            modulo_carregado_pelo_script = True

        # Leitura do valor antigo
        valor_antigo = "DESCONHECIDO"
        if os.path.exists(sysfs_target):
            try:
                with open(sysfs_target, "r") as f:
                    valor_antigo = f.read().strip()
                _log("INFO", "Valor antigo na BIOS (sysfs): '{}'".format(valor_antigo))
            except Exception as e:
                _log("ERROR", "Nao foi possivel ler valor antigo no sysfs: {}".format(e))
        else:
            _log("WARNING", "Caminho sysfs '{}' nao existe.".format(sysfs_target))

        # Otimizacao: evita escrita SMI redundante
        if valor_antigo == tag:
            _log("INFO", "Valor na BIOS ja esta atualizado. Gravacao SMI ignorada.")
            return True

        if dry_run:
            _log("WARNING",
                 "[DRY-RUN] amibios_dmi: valor que seria gravado: '{}'".format(tag))
            _log("WARNING",
                 "[DRY-RUN] Para gravar, passe a flag -w ou --write.")
            return False

        # Gravacao fisica no sysfs
        _log("INFO", "Mecanismo 2: gravando via sysfs amibios_dmi: {}".format(tag))

        if not os.path.exists(sysfs_target):
            raise FileNotFoundError(
                "Caminho sysfs de escrita nao encontrado: {}".format(sysfs_target))
        if not os.access(sysfs_target, os.W_OK):
            raise PermissionError(
                "Sem permissao de escrita no sysfs: {}".format(sysfs_target))

        with open(sysfs_target, "w") as f:
            f.write(tag)
        _log("INFO", "Operacao de escrita concluida.")

        # Auditoria pos-escrita
        try:
            with open(sysfs_target, "r") as f:
                valor_novo = f.read().strip()
            _log("INFO", "Valor auditado pos-escrita: '{}'".format(valor_novo))
        except Exception as e:
            _log("ERROR", "Falha na leitura de auditoria pos-escrita: {}".format(e))
            return False

        if valor_novo == tag:
            _log("INFO", "amibios_dmi: gravacao confirmada e auditada.")
            return True

        _log("ERROR",
             "amibios_dmi: integridade falhou -- esperado '{}', lido '{}'".format(
                 tag, valor_novo))
        return False

    finally:
        # Unload garantido se o modulo foi carregado temporariamente
        if modulo_carregado_pelo_script:
            _descarrega_modulo_amibios(caminho_log, verbose, suprime_tela,
                                       caminho_log_local)


def executa_amibios_remoto(ip, ssh_user, sudo_cmd, tag, sysfs_target,
                            caminho_log, caminho_log_local,
                            verbose, suprime_tela, dry_run=True,
                            module_repo_url="", module_package=""):
    """
    NAME: executa_amibios_remoto
    DESCRIPTION: Executa o mecanismo amibios_dmi em um host remoto via SSH.
                 Verifica se a interface sysfs esta disponivel, tenta modprobe
                 remoto se necessario, le o valor antigo, grava e audita
                 pos-escrita. Em dry_run, apenas loga. Levanta
                 MecanismoIndisponivelError se a interface nao ficar disponivel.
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               sudo_cmd          - prefixo sudo no host remoto
               tag               - valor de 14 digitos a gravar
               sysfs_target      - caminho do sysfs no host remoto
               caminho_log       - log remoto
               caminho_log_local - log consolidado local
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               dry_run           - se True, nao executa a gravacao
               module_repo_url   - repo zypper (para instalacao futura)
               module_package    - pacote KMP (para instalacao futura)
    RETURNS: bool -- True se a gravacao foi bem-sucedida
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    def _ssh(cmd, timeout=10):
        rc, stdout, stderr = ssh_run(ip, ssh_user, cmd, timeout=timeout)
        return rc, stdout, stderr

    modulo_carregado_pelo_script = False

    try:
        # Verifica se a interface sysfs esta disponivel no alvo
        rc_iface, _, _ = _ssh(
            "test -d {} && echo ready || echo absent".format(SYSFS_IFACE_PATH))
        iface_pronta = (rc_iface == 0)

        if not iface_pronta:
            # Verifica se o modulo esta carregado
            rc_mod, stdout_mod, _ = _ssh(
                "test -d {} && echo loaded || echo absent".format(SYSMODULE_PATH))
            modulo_presente = (stdout_mod.strip() == "loaded")

            if not modulo_presente:
                _log("WARNING",
                     "Modulo amibios_dmi ausente no alvo. Tentando modprobe remoto...")
                rc_mp, _, stderr_mp = _ssh(
                    "{} modprobe amibios_dmi 2>&1".format(sudo_cmd), timeout=15)

                # Verifica interface apos modprobe
                rc_check, stdout_check, _ = _ssh(
                    "test -d {} && echo ready || echo absent".format(SYSFS_IFACE_PATH))
                if stdout_check.strip() == "ready":
                    modulo_carregado_pelo_script = True
                    _log("INFO", "Modulo amibios_dmi carregado via modprobe remoto.")
                    iface_pronta = True
                else:
                    _log("ERROR",
                         "Interface sysfs indisponivel apos modprobe: {}".format(
                             stderr_mp.strip()))

        if not iface_pronta:
            raise MecanismoIndisponivelError(
                "Interface sysfs amibios_dmi indisponivel no alvo {}".format(ip))

        # Leitura do valor antigo
        rc_read, valor_antigo, _ = _ssh(
            "cat {} 2>/dev/null || echo DESCONHECIDO".format(sysfs_target))
        valor_antigo = valor_antigo.strip()
        _log("INFO", "Valor antigo na BIOS (sysfs remoto): '{}'".format(valor_antigo))

        # Otimizacao: evita escrita SMI redundante
        if valor_antigo == tag:
            _log("INFO", "Valor na BIOS ja esta atualizado. Gravacao SMI ignorada.")
            return True

        if dry_run:
            _log("WARNING",
                 "[DRY-RUN] amibios_dmi remoto: valor que seria gravado: '{}'".format(tag))
            _log("WARNING",
                 "[DRY-RUN] Para gravar, passe a flag -w ou --write.")
            return False

        # Gravacao fisica via SSH
        _log("INFO",
             "Mecanismo 2: gravando via sysfs amibios_dmi remoto: {}".format(tag))

        cmd_write = (
            "test -w {sysfs} && echo '{tag}' | {sudo} tee {sysfs} > /dev/null"
            " || echo WRITE_ERROR"
        ).format(sysfs=sysfs_target, tag=tag, sudo=sudo_cmd)

        rc_w, stdout_w, stderr_w = _ssh(cmd_write, timeout=15)
        if "WRITE_ERROR" in stdout_w or rc_w != 0:
            _log("ERROR",
                 "amibios_dmi remoto: falha na escrita -- {}".format(
                     stderr_w.strip()))
            return False

        _log("INFO", "Operacao de escrita remota concluida.")

        # Auditoria pos-escrita
        rc_audit, valor_novo, _ = _ssh(
            "cat {} 2>/dev/null || echo AUDIT_FAILED".format(sysfs_target))
        valor_novo = valor_novo.strip()
        _log("INFO", "Valor auditado pos-escrita: '{}'".format(valor_novo))

        if valor_novo == tag:
            _log("INFO", "amibios_dmi remoto: gravacao confirmada e auditada.")
            return True

        _log("ERROR",
             "amibios_dmi remoto: integridade falhou -- esperado '{}', lido '{}'".format(
                 tag, valor_novo))
        return False

    finally:
        # Unload remoto garantido se o modulo foi carregado temporariamente
        if modulo_carregado_pelo_script:
            _log("INFO", "Descarregando modulo amibios_dmi no alvo remoto...")
            _ssh("{} modprobe -r amibios_dmi".format(sudo_cmd), timeout=15)
            rc_check, stdout_check, _ = _ssh(
                "test -d {} && echo present || echo gone".format(SYSFS_IFACE_PATH))
            if stdout_check.strip() == "gone":
                _log("INFO", "Modulo descarregado com sucesso no alvo. Sistema integro.")
            else:
                _log("ERROR", "Interface sysfs ainda presente apos modprobe -r remoto.")


# =======================================================================
# CASCATA DE ESCRITA
# =======================================================================

def tenta_escrever_tag_local(tag, args, kmp_instalado,
                              caminho_log_local=""):
    """
    NAME: tenta_escrever_tag_local
    DESCRIPTION: Cascata de mecanismos local. Retorna string descritiva.
    RETURNS: str -- resultado descritivo
    """
    def _log(nivel, msg):
        gravar_log(args.log_file, nivel, msg, args.verbose, args.csv,
                   caminho_log_local)

    dry_run = not args.write

    _log("INFO", "--- Tentando Mecanismo 1: amidelnx_64 ---")
    try:
        sucesso = executa_amidelnx_local(
            tag, args.amide_local_path, ["sudo"],
            args.log_file, args.verbose, args.csv,
            dry_run=dry_run, caminho_log_local=caminho_log_local,
        )
        if dry_run: return "DRY-RUN"
        if sucesso: return "OK-amidelnx"
        _log("WARNING", "amidelnx_64 nao confirmou gravacao; tentando fallback.")
    except MecanismoIndisponivelError as e:
        _log("WARNING", "amidelnx_64 indisponivel: {}".format(e))

    _log("INFO", "--- Tentando Mecanismo 2: amibios_dmi (sysfs) ---")
    try:
        sucesso = executa_amibios_local(
            tag, args.target, kmp_instalado,
            args.module_repo_url, args.module_package,
            args.log_file, args.verbose, args.csv,
            dry_run=dry_run, caminho_log_local=caminho_log_local,
        )
        if dry_run: return "DRY-RUN"
        if sucesso: return "OK-amibios"
        _log("ERROR", "amibios_dmi tambem nao confirmou gravacao.")
    except MecanismoIndisponivelError as e:
        _log("ERROR", "amibios_dmi indisponivel: {}".format(e))

    if not dry_run:
        raise TodosMecanismosFalharam(
            "Nenhum mecanismo obteve sucesso para tag '{}'.".format(tag))
    return "DRY-RUN"


def tenta_escrever_tag_remoto(ip, ssh_user, sudo_cmd, tag, args,
                               caminho_log_remoto, caminho_log_local):
    """
    NAME: tenta_escrever_tag_remoto
    DESCRIPTION: Cascata de mecanismos remota. Retorna string descritiva.
    RETURNS: str -- resultado descritivo
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel, msg, caminho_log_local, args.verbose, args.csv)

    dry_run = not args.write

    _log("INFO", "--- Tentando Mecanismo 1: amidelnx_64 ---")
    try:
        sucesso = executa_amidelnx_remoto(
            ip, ssh_user, sudo_cmd, tag,
            args.amide_remote_path, args.amide_local_path,
            caminho_log_remoto, caminho_log_local,
            args.verbose, args.csv, dry_run=dry_run,
            amide_repo_url=args.amide_repo_url,
            amide_package=args.amide_package,
        )
        if dry_run: return "DRY-RUN"
        if sucesso: return "OK-amidelnx"
        _log("WARNING", "amidelnx_64 nao confirmou gravacao; tentando fallback.")
    except MecanismoIndisponivelError as e:
        _log("WARNING", "amidelnx_64 indisponivel: {}".format(e))

    _log("INFO", "--- Tentando Mecanismo 2: amibios_dmi (sysfs) ---")
    try:
        sucesso = executa_amibios_remoto(
            ip, ssh_user, sudo_cmd, tag,
            args.target, caminho_log_remoto, caminho_log_local,
            args.verbose, args.csv, dry_run=dry_run,
            module_repo_url=args.module_repo_url,
            module_package=args.module_package,
        )
        if dry_run: return "DRY-RUN"
        if sucesso: return "OK-amibios"
        _log("ERROR", "amibios_dmi tambem nao confirmou gravacao.")
    except MecanismoIndisponivelError as e:
        _log("ERROR", "amibios_dmi indisponivel: {}".format(e))

    if not dry_run:
        _log("ERROR", "Todos os mecanismos falharam para tag '{}' em {}.".format(tag, ip))
    return "FALHOU-todos"


def le_arquivo_hosts(caminho_hosts):
    """
    NAME: le_arquivo_hosts
    DESCRIPTION: Le o arquivo de lista de hosts. Cada linha pode ter:
                   IP
                   IP,BEM_NUMERO
                 Sao ignoradas:
                   - linhas vazias (apenas espacos)
                   - linhas inteiras de comentario (iniciadas com '#')
                   - comentarios em fim de linha
                     (ex: "192.168.1.10 # equip-01" -> processa apenas o IP)
                 Retorna lista de tuplas (ip, bem_numero_ou_vazio).
    PARAMETER: caminho_hosts - caminho do arquivo de hosts
    RETURNS: list of tuple(str, str) -- [(ip, bem_numero), ...]
    """
    if not os.path.isfile(caminho_hosts):
        sys.stderr.write("ERRO: arquivo de hosts nao encontrado: {}\n".format(
            caminho_hosts))
        sys.exit(RC_FILE_NOT_FOUND)

    hosts = []
    with open(caminho_hosts, "r", encoding="utf-8", errors="ignore") as f:
        for linha in f:
            # Remove comentario trailing antes de qualquer outro tratamento.
            # Ex: "192.168.1.10  # equip de teste" -> "192.168.1.10  "
            if "#" in linha:
                linha = linha.split("#", 1)[0]
            linha = linha.strip()
            # Pula vazias (originais ou que viraram vazias apos remover comentario).
            # Isso tambem cobre linhas que comecam com '#' (apos split, ficam vazias).
            if not linha:
                continue
            partes = linha.split(",", 1)
            ip = partes[0].strip()
            bem = partes[1].strip() if len(partes) > 1 else ""
            if ip:
                hosts.append((ip, bem))
    return hosts


def processa_host_remoto(ip, bem_numero_lista, args, caminho_log_local):
    """
    NAME: processa_host_remoto
    DESCRIPTION: Executa o fluxo completo de auditoria e gravacao para
                 um unico host remoto:
                   1. Testa conectividade SSH
                   2. Detecta sudo
                   3. Coleta dados de ambiente (kernel, placa, SMBIOS, WSMT)
                   4. Verifica dependencias RPM
                   5. Le BEM_NUMERO do BBconfig.conf remoto (sempre loga)
                   6. Define BEM_NUMERO a usar (lista tem precedencia)
                   7. Valida e calcula tag de 14 digitos
                   8. Executa cascata de escrita
                   9. Executa acoes --production se solicitado
                 Retorna dicionario com todos os dados para a tabela de resumo.
    PARAMETER: ip               - endereco IP do host remoto
               bem_numero_lista - BEM_NUMERO da linha do arquivo (pode ser vazio)
               args             - namespace do argparse
               caminho_log_local - log consolidado local
    RETURNS: dict -- dados do host para compor a linha do resumo
    """
    caminho_log_remoto = args.log_file
    ssh_user           = args.ssh_user
    sudo_pass          = args.sudo_pass

    # Estrutura de retorno com valores default
    registro = {
        "ip":           ip,
        "hostname":     "N/D",
        "board":        "N/D",
        "bios":         "N/D",
        "smbios":       "N/D",
        "wsmt":         "N/D",
        "tag_antes":    "N/D",
        "bem_conf":     "N/D",
        "bem_usado":    "N/D",
        "tag_depois":   "N/D",
        "mecanismo":    "N/D",
        "resultado":    "INACESSIVEL",
        "bbconfig_sync":   "N/A",
        "bbconfig_backup": "",
    }

    def _log(nivel, msg, sudo_cmd=""):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel, msg, caminho_log_local, args.verbose, args.csv)

    # 1. Testa conectividade SSH
    # Separador visual entre hosts no log local
    gravar_log(
        caminho_log_local, "INFO",
        "# " + "-" * 68,
        args.verbose, args.csv,
    )
    _log("INFO", "====== Iniciando processamento do host {} ======".format(ip))

    # 1.a Bootstrap de autenticacao SSH (gera/distribui chave se necessario).
    # Caminho feliz (chave ja autorizada no host): nao executa nada,
    # apenas retorna True silenciosamente. Em falha, marca INACESSIVEL.
    if not prepara_autenticacao_ssh(
        ip, ssh_user,
        getattr(args, "ssh_pass_efetiva", ""),
        caminho_log_local, args.verbose,
    ):
        _log("ERROR", "Host inacessivel via SSH (bootstrap de autenticacao falhou).")
        return registro

    if not testa_conexao_ssh(ip, ssh_user):
        _log("ERROR", "Host inacessivel via SSH.")
        return registro

    # 2. Detecta sudo
    sudo_cmd = detecta_sudo(ip, ssh_user, sudo_pass)
    _log("INFO", "sudo detectado: {}".format(
        "sem senha" if sudo_cmd == "sudo" else "com senha"), sudo_cmd)

    # 3. Coleta dados de ambiente
    dados_amb = coletar_dados_ambiente_remoto(
        ip, ssh_user, sudo_cmd,
        caminho_log_remoto, caminho_log_local,
        args.verbose, args.csv,
    )
    registro["hostname"]  = dados_amb.get("hostname",    "N/D")
    registro["board"]     = "{} {}".format(
        dados_amb.get("board_vendor", ""), dados_amb.get("board_name", "")).strip()
    registro["bios"]      = dados_amb.get("bios_version", "N/D")
    registro["smbios"]    = dados_amb.get("smbios_version", "N/D")
    registro["wsmt"]      = dados_amb.get("wsmt",          "N/D")
    registro["tag_antes"] = dados_amb.get("tag_atual",     "N/D")

    # 4. Verifica dependencias RPM remotas
    for pkg in ("python3-patrimonial", args.module_package,
                "amibios-dmi-kmp", "amibios-dmi"):
        rc_rpm, stdout_rpm, _ = ssh_run(
            ip, ssh_user,
            "rpm -q {} 2>/dev/null | head -1 || echo AUSENTE".format(pkg))
        # Pega apenas a primeira linha relevante -- rpm em SLES
        # pode retornar mensagem em portugues no stdout
        linhas_rpm = [x.strip() for x in stdout_rpm.splitlines() if x.strip()]
        nvr = linhas_rpm[0] if linhas_rpm else "AUSENTE"
        nivel_rpm = "DEBUG" if "AUSENTE" not in nvr else "DEBUG"
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel_rpm,
                          "RPM {}: {}".format(pkg, nvr),
                          caminho_log_local, args.verbose, args.csv)

    # 5. Le BEM_NUMERO do BBconfig.conf remoto (sempre loga)
    bem_conf = le_valor_configuracao_remoto(
        ip, ssh_user,
        args.config, args.var,
        caminho_log_remoto, caminho_log_local,
        args.verbose, args.csv, sudo_cmd,
    )
    registro["bem_conf"] = bem_conf or "PENDENTE"

    # 6. Define BEM_NUMERO a usar (lista tem precedencia; loga discrepancia)
    if bem_numero_lista:
        if bem_conf and bem_conf != bem_numero_lista:
            gravar_log_remoto(
                ip, ssh_user, sudo_cmd, caminho_log_remoto,
                "WARNING",
                "BEM_NUMERO da lista ({}) difere do BBconfig ({}) -- usando da lista.".format(
                    bem_numero_lista, bem_conf),
                caminho_log_local, args.verbose, args.csv)
        bem_usar = bem_numero_lista
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto,
            "INFO", "BEM_NUMERO em uso (fonte: lista de hosts): {}".format(bem_usar),
            caminho_log_local, args.verbose, args.csv)
    elif bem_conf and bem_conf != "PENDENTE":
        bem_usar = bem_conf
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto,
            "INFO", "BEM_NUMERO em uso (fonte: BBconfig.conf): {}".format(bem_usar),
            caminho_log_local, args.verbose, args.csv)
    else:
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto,
            "WARNING", "BEM_NUMERO ausente em todas as fontes -- host ignorado.",
            caminho_log_local, args.verbose, args.csv)
        registro["resultado"] = "PENDENTE"
        return registro

    registro["bem_usado"] = bem_usar

    # 7. Valida e calcula tag de 14 digitos
    # Suprime log interno (caminho vazio) para evitar linhas sem prefixo [IP].
    # O resultado e logado aqui via gravar_log_remoto com prefixo correto.
    try:
        tag_esperada, base_13 = valida_e_calcula_tag(
            bem_usar, "", False, True)
    except ValueError as e:
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto,
            "ERROR", "Validacao falhou: {}".format(e),
            caminho_log_local, args.verbose, args.csv)
        registro["resultado"] = "INVALIDO"
        return registro

    # Loga resultado da validacao com prefixo [IP]
    if len(bem_usar) == 14:
        dv_calc = calcula_dv_modulo11(bem_usar[:13])
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "INFO",
            "Valor ja possui 14 digitos. DV verificado: {}".format(dv_calc),
            caminho_log_local, args.verbose, args.csv)
    else:
        dv_calc = calcula_dv_modulo11(bem_usar)
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "INFO",
            "Valor possui 13 digitos. DV calculado: {} (Tag: {})".format(
                dv_calc, tag_esperada),
            caminho_log_local, args.verbose, args.csv)

    # Validacao redundante CLI patrimonial -- loga com prefixo [IP]
    tag_cli = valida_via_patrimonial_cli(base_13, "", False, True)
    if tag_cli:
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "DEBUG",
            "CLI patrimonial: {}".format(tag_cli),
            caminho_log_local, args.verbose, args.csv)
        if tag_cli != tag_esperada:
            gravar_log_remoto(
                ip, ssh_user, sudo_cmd, caminho_log_remoto, "WARNING",
                "CLI patrimonial retornou {} vs calculado {}".format(
                    tag_cli, tag_esperada),
                caminho_log_local, args.verbose, args.csv)
    else:
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "DEBUG",
            "CLI patrimonial nao disponivel no PATH local",
            caminho_log_local, args.verbose, args.csv)

    # 8. Cascata de escrita
    resultado_escrita = tenta_escrever_tag_remoto(
        ip, ssh_user, sudo_cmd, tag_esperada, args,
        caminho_log_remoto, caminho_log_local,
    )
    # resultado ja e descritivo (ex: "OK-amidelnx", "FALHOU-todos")
    registro["resultado"] = resultado_escrita

    # Leitura da tag pos-escrita para o resumo
    if str(resultado_escrita).startswith("OK"):
        _, tag_depois, _ = ssh_run(
            ip, ssh_user,
            "{} dmidecode -s chassis-asset-tag 2>/dev/null".format(sudo_cmd),
            timeout=10)
        registro["tag_depois"] = tag_depois.strip() or "N/D"
    else:
        registro["tag_depois"] = registro["tag_antes"]

    # 8.5. Sincroniza BBconfig.conf remoto com o BEM_NUMERO usado na
    # gravacao. So executa com --write e apos gravacao confirmada
    # (resultado_escrita comecando com "OK"). Faz backup imutavel do
    # arquivo original antes de editar; nome do backup vai para o
    # registro e aparece na tabela de resumo.
    if args.write and str(resultado_escrita).startswith("OK"):
        sync_result = sincroniza_bbconfig_remoto(
            ip, ssh_user, sudo_cmd, args.config, args.var,
            bem_conf, bem_usar,
            caminho_log_remoto, caminho_log_local, args.verbose, args.csv)
        registro["bbconfig_sync"] = (
            "OK" if sync_result["sincronizado"] else sync_result["motivo"])
        registro["bbconfig_backup"] = sync_result.get("backup") or ""
    elif str(resultado_escrita).startswith("OK") and not args.write:
        # Defensivo: nao deveria ocorrer (resultado OK implica write),
        # mas mantem o campo coerente caso a logica mude no futuro.
        registro["bbconfig_sync"] = "N/A"
    # Em DRY-RUN, FALHOU-todos, PENDENTE, INVALIDO: mantem default "N/A"

    # 9. Acoes finais --production
    # Guarda critica: reinstall-enable e reboot so devem executar quando
    # a gravacao da tag retornou sucesso. Sem essa guarda, hosts com
    # resultado FALHOU-todos, PENDENTE ou INVALIDO sofreriam reboot sem
    # que a tag tivesse sido atualizada. Modo standalone ja tinha essa
    # guarda no fluxo principal; modo remoto nao tinha ate v2.0.2.
    if args.production:
        if str(resultado_escrita).startswith("OK"):
            _executa_acoes_production(
                ip, ssh_user, sudo_cmd, args,
                caminho_log_remoto, caminho_log_local)
        else:
            gravar_log_remoto(
                ip, ssh_user, sudo_cmd, caminho_log_remoto, "WARNING",
                "[PRODUCTION] reinstall-enable e reboot NAO executados: "
                "resultado da gravacao = {}".format(resultado_escrita),
                caminho_log_local, args.verbose, args.csv)

    gravar_log_remoto(
        ip, ssh_user, sudo_cmd, caminho_log_remoto,
        "INFO",
        "====== Fim do processamento: {} -- {} ======".format(
            ip, resultado_escrita),
        caminho_log_local, args.verbose, args.csv)

    return registro


def _executa_acoes_production(ip, ssh_user, sudo_cmd, args,
                               caminho_log_remoto, caminho_log_local):
    """
    NAME: _executa_acoes_production
    DESCRIPTION: Executa as acoes finais protegidas pela flag --production:
                 reinstall-enable e reboot. Antes de cada acao, verifica
                 se o comando esta disponivel no alvo. Sem --production,
                 apenas loga o que seria feito.
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               sudo_cmd          - prefixo sudo
               args              - namespace do argparse
               caminho_log_remoto - log remoto
               caminho_log_local  - log consolidado local
    RETURNS: None
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel, msg, caminho_log_local, args.verbose, args.csv)

    # reinstall-enable
    rc_which, _, _ = ssh_run(
        ip, ssh_user,
        "which reinstall-enable 2>/dev/null || echo AUSENTE", timeout=10)
    _, which_out, _ = ssh_run(
        ip, ssh_user,
        "which reinstall-enable 2>/dev/null || echo AUSENTE", timeout=10)
    if "AUSENTE" in which_out:
        _log("WARNING", "[PRODUCTION] reinstall-enable nao encontrado no alvo.")
    else:
        _log("INFO", "[PRODUCTION] Executando reinstall-enable...")
        rc_ri, stdout_ri, stderr_ri = ssh_run(
            ip, ssh_user,
            "{} reinstall-enable".format(sudo_cmd), timeout=60)
        if rc_ri == 0:
            _log("INFO", "[PRODUCTION] reinstall-enable concluido.")
        else:
            _log("ERROR", "[PRODUCTION] reinstall-enable falhou (rc={}): {}".format(
                rc_ri, stderr_ri.strip()))

    # reboot
    _log("INFO", "[PRODUCTION] Iniciando reboot do host...")
    ssh_run(ip, ssh_user,
            "{} reboot".format(sudo_cmd), timeout=10)
    _log("INFO", "[PRODUCTION] Comando reboot enviado.")


def _normaliza_fabricante(board):
    """
    NAME: _normaliza_fabricante
    DESCRIPTION: Normaliza nomes de fabricante/placa verbosos para
                 liberar espaco na tabela detalhada, sem perder a
                 informacao relevante (a BIOS Info tem coluna propria).
                 Atualmente normaliza apenas o caso observado:
                   "Daten Tecnologia Ltda DH..." -> "Daten DH..."
                 Demais fabricantes permanecem inalterados.
    PARAMETER: board - string "fabricante modelo" (registro["board"])
    RETURNS: str -- board normalizado
    """
    if not board:
        return board
    prefixo = "Daten Tecnologia Ltda"
    if board.startswith(prefixo):
        return "Daten" + board[len(prefixo):]
    return board


# Mapeamento de resultado/status para descricao em linguagem natural,
# usado no sumario agregado. Chaves sao comparadas por prefixo (ex:
# "FALHOU" cobre "FALHOU-todos"; "INACESSIVEL" e exato).
_DESCRICOES_RESULTADO = (
    ("OK-amidelnx", "Sucesso. Gravacao confirmada via amidelnx_64 (Mecanismo 1)."),
    ("OK-amibios",  "Sucesso. Gravacao confirmada via amibios_dmi/sysfs (Mecanismo 2, fallback)."),
    ("DRY-RUN",     "Leitura realizada com sucesso (Simulacao). Nenhuma gravacao executada."),
    ("FALHOU",      "Bloqueio no firmware: ambos os mecanismos rejeitaram a gravacao."),
    ("PENDENTE",    "BEM_NUMERO ausente no BBconfig.conf. Aguardando provisionamento."),
    ("INVALIDO",    "BEM_NUMERO com formato invalido (esperado 13 ou 14 digitos)."),
    ("INACESSIVEL", "Host nao respondeu via SSH (timeout, desligado, ou bootstrap de chave falhou)."),
)


def _descricao_resultado(resultado):
    """
    NAME: _descricao_resultado
    DESCRIPTION: Traduz o codigo de resultado/status de um host para uma
                 descricao em linguagem natural, usada no sumario
                 agregado. Faz match por prefixo (primeira correspon-
                 dencia na ordem de _DESCRICOES_RESULTADO). Se nenhum
                 prefixo bater, retorna o proprio resultado como
                 descricao (fallback seguro para status desconhecidos
                 introduzidos no futuro).
    PARAMETER: resultado - string de resultado (ex: "OK-amidelnx",
               "FALHOU-todos", "INACESSIVEL")
    RETURNS: str -- descricao em linguagem natural
    """
    resultado = str(resultado or "")
    for prefixo, descricao in _DESCRICOES_RESULTADO:
        if resultado.startswith(prefixo):
            return descricao
    return resultado


def monta_tabela_resumo(registros, caminho_log_local, verbose, suprime_tela,
                        write_ativo=False):
    """
    NAME: monta_tabela_resumo
    DESCRIPTION: Gera duas tabelas no log final:
                   1. TABELA DETALHADA -- uma linha por host, com
                      colunas IP, Hostname, Placa (normalizada), BIOS,
                      SMBIOS, WSMT, Tag Antes, BEM conf, BEM usado,
                      Tag Depois, Resultado, BBconfig (status da
                      sincronizacao do BBconfig.conf) e Backup (nome do
                      arquivo de backup gerado, se houve).
                   2. SUMARIO AGREGADO -- agrupa os registros por
                      (BIOS, flag -w, Resultado), mostrando a contagem
                      de cada combinacao e uma descricao em linguagem
                      natural do que aquele resultado significa
                      (_descricao_resultado). Permite avaliar o
                      resultado de uma execucao em massa rapidamente,
                      sem precisar ler linha a linha.
                 Ambas as tabelas sao escritas no log local (se
                 configurado) e no stdout (se nao suprimido).
    PARAMETER: registros         - lista de dicts retornados por
                                    processa_host_remoto
               caminho_log_local - log consolidado local
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               write_ativo       - bool, valor de args.write desta
                                    execucao (usado na coluna -w do
                                    sumario agregado)
    """
    def _escreve(linha):
        if caminho_log_local:
            try:
                with open(caminho_log_local, "a", encoding="utf-8") as f:
                    f.write(linha + "\n")
            except Exception:
                pass
        if not suprime_tela:
            sys.stdout.write(linha + "\n")

    def _cel(valor, largura):
        s = str(valor if valor not in (None, "") else "N/D")
        return s[:largura].ljust(largura)

    def _cel_raw(valor, largura):
        """Como _cel, mas string vazia permanece vazia (nao vira N/D).
        Usado para colunas onde 'vazio' e um valor valido, como Backup
        (nenhum backup foi gerado)."""
        s = str(valor) if valor is not None else ""
        return s[:largura].ljust(largura)

    # =====================================================================
    # 1. TABELA DETALHADA
    # =====================================================================
    C = {
        "ip":              15,
        "hostname":        13,
        "board":           17,
        "bios":            12,
        "smbios":           7,
        "wsmt":             7,
        "tag_antes":       15,
        "bem_conf":        14,
        "bem_usado":       14,
        "tag_depois":      15,
        "resultado":       13,
        "bbconfig_sync":   17,
        "bbconfig_backup": 50,
    }
    CABECALHOS = [
        "IP", "Hostname", "Placa", "BIOS", "SMBIOS", "WSMT",
        "Tag Antes", "BEM conf", "BEM usado", "Tag Depois",
        "Resultado", "BBconfig", "Backup",
    ]

    div = "+-" + "-+-".join("-" * (v + 2) for v in C.values()) + "-+"
    cab = "| " + " | ".join(_cel(h, w) for h, w in zip(CABECALHOS, C.values())) + " |"

    _escreve("")
    _escreve("=" * len(div))
    _escreve("RESUMO DETALHADO -- {} equipamento(s) processado(s)".format(len(registros)))
    _escreve("=" * len(div))
    _escreve(div)
    _escreve(cab)
    _escreve(div)

    for r in registros:
        linha_valores = dict(r)
        linha_valores["board"] = _normaliza_fabricante(r.get("board", "N/D"))
        partes = []
        for k, w in C.items():
            if k == "bbconfig_backup":
                partes.append(_cel_raw(linha_valores.get(k, ""), w))
            else:
                partes.append(_cel(linha_valores.get(k, "N/D"), w))
        _escreve("| " + " | ".join(partes) + " |")

    _escreve(div)
    _escreve("")

    # =====================================================================
    # 2. SUMARIO AGREGADO
    # =====================================================================
    # Agrupa por (BIOS, flag -w, Resultado). A ordem de insercao do dict
    # e preservada (Python 3.7+), mantendo a ordem em que os grupos
    # aparecem na execucao.
    grupos = {}
    flag_w = "-w" if write_ativo else ""
    for r in registros:
        bios = r.get("bios", "N/D") or "N/D"
        resultado = r.get("resultado", "N/D") or "N/D"
        chave = (bios, flag_w, resultado)
        grupos[chave] = grupos.get(chave, 0) + 1

    CS = {
        "bios":       15,
        "flag_w":      5,
        "resultado":  14,
        "qtd":         5,
        "observacao": 80,
    }
    CABECALHOS_S = ["BIOS", "-w", "Status", "Qtd", "Observacao"]
    div_s = "+-" + "-+-".join("-" * (v + 2) for v in CS.values()) + "-+"
    cab_s = "| " + " | ".join(_cel(h, w) for h, w in zip(CABECALHOS_S, CS.values())) + " |"

    _escreve("=" * len(div_s))
    _escreve("SUMARIO AGREGADO")
    _escreve("=" * len(div_s))
    _escreve(div_s)
    _escreve(cab_s)
    _escreve(div_s)

    for (bios, fw, resultado), qtd in grupos.items():
        observacao = _descricao_resultado(resultado)
        valores = {
            "bios": bios, "flag_w": fw, "resultado": resultado,
            "qtd": qtd, "observacao": observacao,
        }
        partes = [_cel(valores[k], w) for k, w in CS.items()]
        _escreve("| " + " | ".join(partes) + " |")

    _escreve(div_s)
    _escreve("")

    # Contadores globais por prefixo do resultado (mantidos por
    # compatibilidade com versoes anteriores do log)
    ok     = sum(1 for r in registros if str(r.get("resultado","")).startswith("OK"))
    dryrun = sum(1 for r in registros if r.get("resultado") == "DRY-RUN")
    falhou = sum(1 for r in registros if str(r.get("resultado","")).startswith("FALHOU"))
    outros = len(registros) - ok - dryrun - falhou

    _escreve("  OK       : {}".format(ok))
    _escreve("  DRY-RUN  : {}".format(dryrun))
    _escreve("  FALHOU   : {}".format(falhou))
    if outros > 0:
        _escreve("  OUTROS   : {} (PENDENTE/INACESSIVEL/INVALIDO)".format(outros))
    _escreve("")


def checa_superusuario():
    """
    NAME: checa_superusuario
    DESCRIPTION: Verifica se o script esta sendo executado como root.
                 Em modo remoto (--hosts), o root e necessario localmente
                 apenas para operacoes que exijam privilegio (ex: scp para
                 diretorios restritos). A verificacao e mantida para
                 garantir consistencia com o modo standalone.
    PARAMETER: nenhum
    RETURNS: None
    """
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        sys.stderr.write(
            "Erro: Este script deve ser executado como superusuario (root).\n")
        sys.exit(1)


def main():
    """
    NAME: main
    DESCRIPTION: Ponto de entrada principal. Faz o parse dos argumentos,
                 determina o modo de execucao (standalone ou remoto) e
                 delega para o fluxo correspondente.
    PARAMETER: nenhum
    RETURNS: int -- codigo de saida
    """
    parser = argparse.ArgumentParser(
        description=(
            "Utilitario Mario Luz para atualizacao de DMI Asset Tag corporativa. "
            "Cascata: amidelnx_64 (primeiro) -> amibios_dmi sysfs (fallback). "
            "Modos: standalone (local) e remoto (lista de IPs via SSH)."
        )
    )

    # --- Arquivo de hosts (ativa modo remoto) ---
    parser.add_argument(
        "--hosts",
        default="",
        metavar="ARQUIVO",
        help="Arquivo de hosts (IP ou IP,BEM_NUMERO por linha). Ativa modo remoto.",
    )

    # --- SSH ---
    parser.add_argument(
        "--ssh-user",
        default=DEFAULT_SSH_USER,
        help="Usuario SSH para modo remoto (padrao: usuario da sessao atual)",
    )
    parser.add_argument(
        "--sudo-pass",
        default="",
        metavar="SENHA",
        help="Senha do sudo no host remoto (opcional; detecta automaticamente)",
    )
    parser.add_argument(
        "--ssh-pass",
        default="",
        metavar="SENHA",
        help=("Senha SSH para distribuir a chave via ssh-copy-id quando "
              "a autenticacao por chave ainda nao esta configurada. "
              "Tem precedencia sobre SSH_PASS env e --ssh-pass-file. "
              "Nao usada para autenticacao apos a chave estar distribuida."),
    )
    parser.add_argument(
        "--ssh-pass-file",
        default="",
        metavar="ARQUIVO",
        help=("Arquivo texto contendo a senha SSH na primeira linha. "
              "Usado apenas se --ssh-pass nao for fornecido e SSH_PASS "
              "nao estiver definida no ambiente."),
    )

    # --- Configuracao corporativa ---
    parser.add_argument(
        "-c", "--config",
        default=DEFAULT_CONFIG_FILE,
        help="Caminho do BBconfig.conf (padrao: {})".format(DEFAULT_CONFIG_FILE),
    )
    parser.add_argument(
        "-s", "--var",
        default=DEFAULT_VAR_NAME,
        help="Nome da variavel de patrimonio (padrao: {})".format(DEFAULT_VAR_NAME),
    )

    # --- Mecanismo 1: amidelnx_64 ---
    parser.add_argument(
        "--amide-local-path",
        default=DEFAULT_AMIDE_LOCAL_PATH,
        help="Caminho local do amidelnx_64 para scp (padrao: mesmo dir do script)",
    )
    parser.add_argument(
        "--amide-remote-path",
        default=DEFAULT_AMIDE_REMOTE_PATH,
        help="Caminho do amidelnx_64 no host remoto (padrao: {})".format(
            DEFAULT_AMIDE_REMOTE_PATH),
    )
    parser.add_argument(
        "--amide-repo-url",
        default=DEFAULT_AMIDE_REPO_URL,
        help="URL do repo zypper do amidelnx_64 (reservado para uso futuro)",
    )
    parser.add_argument(
        "--amide-package",
        default=DEFAULT_AMIDE_PACKAGE,
        help="Nome do pacote amidelnx_64 no OBS (reservado para uso futuro)",
    )

    # --- Mecanismo 2: amibios_dmi ---
    parser.add_argument(
        "-t", "--target",
        default=DEFAULT_SYSFS_TARGET,
        help="Caminho sysfs da asset tag (padrao: {})".format(DEFAULT_SYSFS_TARGET),
    )
    parser.add_argument(
        "--module-repo-url",
        default=DEFAULT_MODULE_REPO_URL,
        help="URL do repo zypper do KMP amibios_dmi",
    )
    parser.add_argument(
        "--module-package",
        default=DEFAULT_MODULE_PACKAGE,
        help="Nome do pacote KMP a instalar (padrao: {})".format(
            DEFAULT_MODULE_PACKAGE),
    )

    # --- Log ---
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help="Log no host alvo (padrao: {})".format(DEFAULT_LOG_FILE),
    )
    parser.add_argument(
        "--log-local",
        default=DEFAULT_LOCAL_LOG_FILE,
        help="Log local consolidado em modo remoto (padrao: {})".format(
            DEFAULT_LOCAL_LOG_FILE),
    )

    # --- Comportamento ---
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Exibe mensagens de log no terminal",
    )
    parser.add_argument(
        "-w", "--write",
        action="store_true",
        help="Habilita gravacao fisica. Sem esta flag, executa em Dry Run (simulacao).",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="(Modo standalone) Retorna linha CSV no stdout: antigo,config,novo",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Executa acoes finais apos gravacao: reinstall-enable e reboot.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="{} {}".format("update_dmi_tag.py", SCRIPT_VERSION),
    )

    args = parser.parse_args()

    # Resolve a senha SSH efetiva para o bootstrap de autenticacao,
    # aplicando precedencia: --ssh-pass > SSH_PASS env > --ssh-pass-file.
    # Sempre define args.ssh_pass_efetiva (mesmo que vazia) para que o
    # bootstrap possa consulta-la com getattr sem erro.
    args.ssh_pass_efetiva = _resolve_ssh_pass(args)

    # Em modo remoto, se --log-file nao foi passado explicitamente,
    # redireciona para arquivo local (evita Permission denied em /var/log).
    if args.hosts and args.log_file == DEFAULT_LOG_FILE:
        args.log_file = os.path.join(
            os.path.dirname(os.path.abspath(args.log_local)),
            'update_dmi_tag_alvo.log'
        )

    # Validacao: --csv incompativel com --hosts
    if args.csv and args.hosts:
        sys.stderr.write(
            "Erro: --csv nao e suportado em modo remoto (--hosts).\n")
        sys.exit(1)

    # ===================================================================
    # MODO REMOTO
    # ===================================================================
    if args.hosts:
        # Modo remoto: nao requer root local. O sudo e tratado remotamente
        # por detecta_sudo() em cada host alvo.

        # Abre o log local consolidado em modo APPEND para preservar
        # historico de todas as execucoes (antes era aberto em "w" e
        # truncava o arquivo a cada rodada, descartando o historico).
        # Se o arquivo nao existir ainda, e criado. Se ja existir, a
        # linha em branco abaixo serve como separador visual entre o
        # bloco anterior e o cabecalho que sera escrito a seguir.
        try:
            with open(args.log_local, "a", encoding="utf-8") as f:
                f.write("\n")
        except Exception as e:
            sys.stderr.write(
                "Aviso: nao foi possivel abrir log local {} para append: {}\n".format(
                    args.log_local, e))

        def _log_local(nivel, msg):
            gravar_log(args.log_local, nivel, msg, args.verbose, False)

        _log_local("INFO", "=" * 70)
        _log_local("INFO", "update_dmi_tag.py v{} -- MODO REMOTO".format(
            SCRIPT_VERSION))
        _log_local("INFO", "Inicio: {}".format(
            time.strftime("%Y-%m-%d %H:%M:%S")))
        _log_local("INFO", "Hosts : {}".format(args.hosts))
        _log_local("INFO", "User  : {}".format(args.ssh_user))
        _log_local("INFO", "Amide : {}".format(args.amide_local_path))
        _log_local("INFO", "Log   : {}".format(args.log_local))
        _log_local("INFO", "Modo  : {}".format(
            "GRAVACAO REAL" if args.write else "DRY-RUN (simulacao)"))
        if args.production:
            _log_local("WARNING",
                       "PRODUCTION ativado: reinstall-enable e reboot serao executados.")
        _log_local("INFO", "=" * 70)

        hosts = le_arquivo_hosts(args.hosts)
        registros = []

        for ip, bem_lista in hosts:
            registro = processa_host_remoto(
                ip, bem_lista, args, args.log_local)
            registros.append(registro)

        monta_tabela_resumo(registros, args.log_local, args.verbose, args.csv,
                            write_ativo=args.write)

        _log_local("INFO", "=" * 70)
        _log_local("INFO", "FINALE")
        _log_local("INFO", "Fim   : {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
        _log_local("INFO", "Total : {} equipamento(s) processado(s)".format(
            len(registros)))
        _log_local("INFO", "Log   : {}".format(args.log_local))
        _log_local("INFO", "=" * 70)

        # RC do modo remoto: 0 se todos OK ou DRY-RUN, 1 se algum falhou
        # RC do modo remoto: 0 se todos OK ou DRY-RUN, 1 se algum falhou
        falhas = sum(1 for r in registros
                     if not str(r.get("resultado", "")).startswith("OK")
                     and r.get("resultado") not in ("DRY-RUN", "PENDENTE", "INVALIDO"))
        return 0 if falhas == 0 else 1

    # ===================================================================
    # MODO STANDALONE
    # ===================================================================
    checa_superusuario()

    gravar_log(args.log_file, "INFO",
               "--- Iniciando processo de atualizacao de DMI Asset Tag ---",
               args.verbose, args.csv)
    gravar_log(args.log_file, "INFO",
               "update_dmi_tag.py v{} (Python {})".format(
                   SCRIPT_VERSION, sys.version.split()[0]),
               args.verbose, args.csv)
    gravar_log(args.log_file, "INFO",
               "Modo: {}".format(
                   "GRAVACAO REAL" if args.write else "DRY-RUN (simulacao)"),
               args.verbose, args.csv)
    if args.production:
        gravar_log(args.log_file, "WARNING",
                   "PRODUCTION ativado: reinstall-enable e reboot serao executados.",
                   args.verbose, args.csv)

    coletar_dados_ambiente(args.log_file, args.verbose, args.csv)

    valor_antigo    = "ERROR_OR_EMPTY"
    valor_config    = "ERROR_OR_EMPTY"
    valor_novo      = "ERROR_OR_EMPTY"
    retorno         = RC_UNKNOWN_ERROR

    try:
        # Auditoria de dependencias
        verifica_pacote_rpm(
            "python3-patrimonial", args.log_file, args.verbose, args.csv)
        kmp_instalado = verifica_pacote_rpm(
            args.module_package, args.log_file, args.verbose, args.csv)
        verifica_pacote_rpm(
            "amibios-dmi-kmp", args.log_file, args.verbose, args.csv)
        verifica_pacote_rpm(
            "amibios-dmi", args.log_file, args.verbose, args.csv)

        # Leitura e validacao do patrimonio
        valor_config = le_valor_configuracao(
            args.config, args.var, args.log_file, args.verbose, args.csv)

        if not valor_config:
            raise PatrimonioPendenteError(
                "Variavel '{}' vazia em {}: provisionamento pendente.".format(
                    args.var, args.config))

        tag_esperada, base_13 = valida_e_calcula_tag(
            valor_config, args.log_file, args.verbose, args.csv)

        # Validacao redundante via CLI patrimonial
        tag_cli = valida_via_patrimonial_cli(
            base_13, args.log_file, args.verbose, args.csv)
        if tag_cli and tag_cli != tag_esperada:
            gravar_log(args.log_file, "WARNING",
                       "CLI patrimonial retornou {} vs calculado {}".format(
                           tag_cli, tag_esperada),
                       args.verbose, args.csv)

        # Leitura do valor antigo (sysfs local se disponivel)
        if os.path.exists(args.target):
            try:
                with open(args.target, "r") as f:
                    valor_antigo = f.read().strip()
                gravar_log(args.log_file, "INFO",
                           "Valor antigo na BIOS (sysfs): '{}'".format(valor_antigo),
                           args.verbose, args.csv)
            except Exception as e:
                gravar_log(args.log_file, "WARNING",
                           "Nao foi possivel ler valor antigo: {}".format(e),
                           args.verbose, args.csv)

        # Cascata de escrita
        resultado_escrita = tenta_escrever_tag_local(
            tag_esperada, args, kmp_instalado)

        if str(resultado_escrita).startswith("OK"):
            # Leitura do valor novo para CSV e log
            if os.path.exists(args.target):
                try:
                    with open(args.target, "r") as f:
                        valor_novo = f.read().strip()
                except Exception:
                    valor_novo = tag_esperada
            else:
                valor_novo = tag_esperada
            gravar_log(args.log_file, "INFO",
                       "--- Atualizacao concluida: {} ---".format(resultado_escrita),
                       args.verbose, args.csv)
            retorno = RC_OK

            # Sincroniza BBconfig.conf local com a tag de 14 digitos
            # gravada na BIOS, caso o arquivo ainda contenha o valor de
            # 13 digitos (ou qualquer valor diferente do gravado). So
            # executa com --write (implicito aqui, pois resultado_escrita
            # so comeca com "OK" quando args.write esta ativo).
            if args.write:
                sincroniza_bbconfig_local(
                    args.config, args.var, valor_config, tag_esperada,
                    args.log_file, args.verbose, args.csv)
        elif resultado_escrita == "DRY-RUN":
            valor_novo = valor_antigo
            retorno    = RC_OK
        else:
            valor_novo = "WRITE_FAILED"
            retorno    = RC_ALL_MECHANISMS_FAILED

        # Acoes --production (standalone)
        if args.production and retorno == RC_OK and args.write:
            gravar_log(args.log_file, "INFO",
                       "[PRODUCTION] Verificando reinstall-enable...",
                       args.verbose, args.csv)
            try:
                rc_which = subprocess.run(
                    ["which", "reinstall-enable"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=False).returncode
                if rc_which == 0:
                    gravar_log(args.log_file, "INFO",
                               "[PRODUCTION] Executando reinstall-enable...",
                               args.verbose, args.csv)
                    subprocess.run(["reinstall-enable"], check=False, timeout=60)
                    gravar_log(args.log_file, "INFO",
                               "[PRODUCTION] reinstall-enable concluido.",
                               args.verbose, args.csv)
                else:
                    gravar_log(args.log_file, "WARNING",
                               "[PRODUCTION] reinstall-enable nao encontrado.",
                               args.verbose, args.csv)
            except Exception as e:
                gravar_log(args.log_file, "ERROR",
                           "[PRODUCTION] Falha no reinstall-enable: {}".format(e),
                           args.verbose, args.csv)
            gravar_log(args.log_file, "INFO",
                       "[PRODUCTION] Iniciando reboot...",
                       args.verbose, args.csv)
            subprocess.run(["reboot"], check=False)

    except PatrimonioPendenteError as e:
        gravar_log(args.log_file, "WARNING", str(e), args.verbose, args.csv)
        valor_novo = valor_antigo
        retorno    = RC_PATRIMONIO_PENDENTE
    except TodosMecanismosFalharam as e:
        gravar_log(args.log_file, "ERROR", str(e), args.verbose, args.csv)
        valor_novo = "ALL_FAILED"
        retorno    = RC_ALL_MECHANISMS_FAILED
    except FileNotFoundError as e:
        gravar_log(args.log_file, "ERROR",
                   "Arquivo nao encontrado: {}".format(e), args.verbose, args.csv)
        retorno = RC_FILE_NOT_FOUND
    except PermissionError as e:
        gravar_log(args.log_file, "ERROR",
                   "Erro de permissao: {}".format(e), args.verbose, args.csv)
        retorno = RC_PERMISSION_ERROR
    except ValueError as e:
        gravar_log(args.log_file, "ERROR",
                   "Erro de validacao: {}".format(e), args.verbose, args.csv)
        retorno = RC_VALIDATION_ERROR
    except Exception as e:
        gravar_log(args.log_file, "ERROR",
                   "Erro nao mapeado: {}".format(e), args.verbose, args.csv)
        retorno = RC_UNKNOWN_ERROR

    gravar_log(args.log_file, "INFO",
               "--- FINALE (rc={}) ---".format(retorno),
               args.verbose, args.csv)

    # Saida CSV (modo standalone)
    if args.csv:
        sys.stdout.write("{},{},{}\n".format(
            valor_antigo, valor_config, valor_novo))

    return retorno


if __name__ == "__main__":
    sys.exit(main())
