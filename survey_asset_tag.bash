#!/bin/bash
# =======================================================================
# FILE:        survey_asset_tag.bash
# USAGE:       ./survey_asset_tag.bash --hosts <arquivo> [opcoes]
# DESCRIPTION: Levantamento (survey) remoto de capacidade de gravacao do
#              campo DMI Asset Tag em equipamentos Linux (SLED/SLES) com
#              BIOS AMI. Para cada host na lista, coleta:
#                - Identificacao (hostname, kernel, OS)
#                - Placa-mae (fabricante, modelo)
#                - SMBIOS e BIOS (versoes)
#                - Indicadores de compatibilidade: WSMT, Secure Boot,
#                  Kernel Lockdown, STRICT_DEVMEM
#                - Asset Tag atual (sem alteracao)
#                - BEM_NUMERO do arquivo de configuracao
#              Com base nos indicadores, classifica cada equipamento como
#              PROVAVEL-OK, PROVAVEL-FALHA ou INDETERMINADO antes mesmo
#              de tentar qualquer escrita.
#              Opcionalmente, com a flag --test-write, executa um teste
#              de capacidade de gravacao no modo "rewrite no-op" (regrava
#              o mesmo valor atual) que NAO altera o asset tag, tentando
#              tanto o Mecanismo 1 (amidelnx_64 com scp se necessario)
#              quanto o Mecanismo 2 (amibios_dmi sysfs, se driver presente).
#              Tags virgens (Default String, etc) tem o teste pulado por
#              seguranca.
# OPTIONS:     --hosts <arquivo>         Lista de IPs (um por linha, # comentarios)
#              --user <usuario>          Usuario SSH (padrao: usuario corrente)
#              --ssh-pass <senha>        Senha SSH para bootstrap (precede env e arquivo)
#              --ssh-pass-file <arquivo> Arquivo com senha SSH na 1a linha
#              --sudo-pass <senha>       Senha do sudo nos hosts (se necessario)
#              --amide-local-path <p>    Caminho local do amidelnx_64 (para scp)
#              --amide-remote-path <p>   Caminho remoto do binario nos hosts
#              --log <arquivo>           Arquivo de log (modo append, nunca trunca)
#              --test-write              Habilita teste de gravacao rewrite no-op
#              --help                    Esta ajuda
#              --version                 Versao do script
# REQUIREMENTS:
#              Linux com bash 4+, ssh, scp, ssh-keygen, ssh-copy-id, python3
#              (para o bootstrap SSH com senha via pty). O python3 e o mesmo
#              ja exigido pelo update_dmi_tag.py.
# BUGS:        Nenhum conhecido nesta versao.
# NOTES:       Variavel de ambiente SSH_PASS tem precedencia sobre
#              --ssh-pass-file mas e sobrescrita por --ssh-pass.
# AUTHOR:      Mario Luz
# COMPANY:     SUSE -- consultor BB
# VERSION:     1.4.0
# CREATED:     2026-06-05
# REVISION:    1.0.0 - 2026-06-05 - versao inicial
#              1.1.0 - 2026-06-05 - removido -t do SSH, resumo em tabela
#              1.2.0 - 2026-06-05 - correcoes de bugs no array e loop
#              1.3.0 - 2026-06-05 - reescrita simplificada, loop com
#                                   descritor dedicado fd3 para evitar
#                                   conflito com stdin SSH
#              1.4.0 - 2026-06-12 - evolucao para survey-only por padrao;
#                                   teste de gravacao opcional via flag
#                                   (--test-write) com estrategia rewrite
#                                   no-op (nao altera asset tag); detec-
#                                   cao de Secure Boot, Kernel Lockdown
#                                   e STRICT_DEVMEM; classificacao predi-
#                                   tiva de compatibilidade pelos indica-
#                                   dores; bootstrap SSH automatico (gera
#                                   chave local, distribui via ssh-copy-id
#                                   alimentando senha por pty atraves de
#                                   python3 inline); argumentos --ssh-pass,
#                                   --ssh-pass-file, env SSH_PASS; log
#                                   em modo append (nunca trunca); fix do
#                                   bug de deteccao do binario remoto.
#
# COMPATIBILITY:
#
# Modelos de placa-mae conhecidos ate a data desta versao:
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
# Modelos OK gravam com sucesso via amidelnx_64. O amibios_dmi so
# funciona na Gigabyte (unica sem WSMT). Modelos FALHA apresentam
# Error 24 ("Problem allocating BIOS buffer") por combinacao de WSMT +
# Secure Boot + kernel lockdown integrity + CONFIG_STRICT_DEVMEM.
# =======================================================================

# Sem set -e: ssh frequentemente retorna != 0 sem ser erro fatal aqui
# (host inacessivel, sudo nao detectado, etc). Usamos pipefail para
# capturar falhas em pipes onde elas importam.
set -o pipefail

# =======================================================================
# CONSTANTES E VARIAVEIS GLOBAIS
# =======================================================================

SCRIPT_NAME="survey_asset_tag.bash"
SCRIPT_VERSION="1.4.0"

# Defaults SSH e SCP (alinhados com update_dmi_tag.py)
SSH_OPTS_BATCH="-q -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no"

# Defaults de paths
DEFAULT_AMIDE_LOCAL="./amidelnx_64"
DEFAULT_AMIDE_REMOTE="~/amidelnx_64"
DEFAULT_SYSFS_TARGET="/sys/firmware/amibios/chassis/asset_tag"

# Variaveis preenchidas por parse_args
HOSTS_FILE=""
SSH_USER="$(id -un)"
SSH_PASS_ARG=""
SSH_PASS_FILE=""
SUDO_PASS=""
AMIDE_LOCAL=""
AMIDE_REMOTE=""
LOG_FILE=""
TEST_WRITE=0

# Senha SSH efetiva (resolvida apos parse_args)
SSH_PASS_EFETIVA=""

# Caminhos das chaves SSH locais
SSH_KEY_RSA="${HOME}/.ssh/id_rsa"
SSH_KEY_ED25519="${HOME}/.ssh/id_ed25519"

# Separador interno dos campos do array de resumo
FS=$'\x1c'
declare -a SUMMARY=()

# Strings que indicam tag virgem (teste de escrita pulado por seguranca)
TAG_VIRGEM_PATTERNS="^(Default String|To be filled by O.E.M.|To Be Filled By O.E.M.|Asset-1234567890|Chassis Asset Tag|)$"


# =======================================================================
# UTILITARIOS DE LOG
# =======================================================================

# NAME:        log
# DESCRIPTION: Imprime mensagem no stdout e gravar em LOG_FILE se
#              configurado. Sempre em modo append (LOG_FILE nunca e
#              truncado). Acrescenta timestamp ISO 8601 a cada linha.
# PARAMETER:   $1 - mensagem
log() {
    local ts msg
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    msg="$ts - $1"
    echo "$msg"
    [ -n "$LOG_FILE" ] && echo "$msg" >> "$LOG_FILE"
}

# NAME:        log_raw
# DESCRIPTION: Imprime linha "crua" (sem timestamp) -- usado para tabelas
#              ASCII e separadores visuais.
# PARAMETER:   $1 - linha
log_raw() {
    echo "$1"
    [ -n "$LOG_FILE" ] && echo "$1" >> "$LOG_FILE"
}


# =======================================================================
# AJUDA E PARSE DE ARGUMENTOS
# =======================================================================

# NAME:        usage
# DESCRIPTION: Exibe a ajuda do script.
# PARAMETER:   nenhum
usage() {
    cat <<EOF
Uso: $SCRIPT_NAME --hosts <arquivo> [opcoes]

Argumentos obrigatorios:
  --hosts <arquivo>          Arquivo com lista de IPs (um por linha)

Autenticacao SSH (precedencia: arg > env SSH_PASS > arquivo):
  --user <usuario>           Usuario SSH (padrao: usuario corrente)
  --ssh-pass <senha>         Senha SSH para o bootstrap (ssh-copy-id)
  --ssh-pass-file <arquivo>  Arquivo texto com a senha na 1a linha
  --sudo-pass <senha>        Senha do sudo nos hosts remotos

Paths:
  --amide-local-path <p>     Binario amidelnx_64 local  (padrao: $DEFAULT_AMIDE_LOCAL)
  --amide-remote-path <p>    Caminho remoto do binario  (padrao: $DEFAULT_AMIDE_REMOTE)
  --log <arquivo>            Arquivo de log (modo APPEND, nunca trunca)

Comportamento:
  --test-write               Habilita teste de gravacao "rewrite no-op"
                             (regrava o mesmo valor atual, nao altera nada)
  --help                     Esta ajuda
  --version                  Versao do script

Exemplos:

  # Survey rapido apenas com indicadores (sem qualquer gravacao):
  $SCRIPT_NAME --hosts hosts.txt --ssh-pass-file .ssh_pass

  # Survey + teste de capacidade de gravacao (sem alterar valores):
  $SCRIPT_NAME --hosts hosts.txt --ssh-pass-file .ssh_pass --sudo-pass SENHA --test-write

Variavel de ambiente:
  SSH_PASS                   Alternativa a --ssh-pass / --ssh-pass-file

EOF
}

# NAME:        parse_args
# DESCRIPTION: Faz o parse dos argumentos de linha de comando e popula
#              as variaveis globais. Valida obrigatorios e existencia
#              de arquivos. Sai com codigo 1 em caso de erro.
# PARAMETER:   $@ - argumentos
parse_args() {
    [ $# -eq 0 ] && { usage; exit 0; }
    while [ $# -gt 0 ]; do
        case "$1" in
            --hosts)             HOSTS_FILE="$2";      shift 2 ;;
            --user)              SSH_USER="$2";        shift 2 ;;
            --ssh-pass)          SSH_PASS_ARG="$2";    shift 2 ;;
            --ssh-pass-file)     SSH_PASS_FILE="$2";   shift 2 ;;
            --sudo-pass)         SUDO_PASS="$2";       shift 2 ;;
            --amide-local-path)  AMIDE_LOCAL="$2";     shift 2 ;;
            --amide-remote-path) AMIDE_REMOTE="$2";    shift 2 ;;
            --log)               LOG_FILE="$2";        shift 2 ;;
            --test-write)        TEST_WRITE=1;         shift   ;;
            --help)              usage; exit 0 ;;
            --version)           echo "$SCRIPT_NAME version $SCRIPT_VERSION"; exit 0 ;;
            *) echo "ERRO: opcao desconhecida: $1"; usage; exit 1 ;;
        esac
    done

    [ -z "$HOSTS_FILE" ] && { echo "ERRO: --hosts e obrigatorio."; usage; exit 1; }
    [ ! -f "$HOSTS_FILE" ] && { echo "ERRO: arquivo nao encontrado: $HOSTS_FILE"; exit 1; }

    # Defaults se vazios
    [ -z "$AMIDE_LOCAL" ]  && AMIDE_LOCAL="$DEFAULT_AMIDE_LOCAL"
    [ -z "$AMIDE_REMOTE" ] && AMIDE_REMOTE="$DEFAULT_AMIDE_REMOTE"

    # Resolve a senha SSH efetiva pela ordem: arg > env > arquivo
    if [ -n "$SSH_PASS_ARG" ]; then
        SSH_PASS_EFETIVA="$SSH_PASS_ARG"
    elif [ -n "${SSH_PASS:-}" ]; then
        SSH_PASS_EFETIVA="$SSH_PASS"
    elif [ -n "$SSH_PASS_FILE" ]; then
        if [ -f "$SSH_PASS_FILE" ]; then
            SSH_PASS_EFETIVA=$(head -n 1 "$SSH_PASS_FILE" | tr -d '\r\n')
        else
            echo "ERRO: arquivo de senha SSH nao encontrado: $SSH_PASS_FILE" >&2
            exit 1
        fi
    fi
}


# =======================================================================
# BOOTSTRAP DE AUTENTICACAO SSH
#
# Equivalente bash do bloco do update_dmi_tag.py v2.0.1. Localiza ou
# gera chave SSH local, e distribui via ssh-copy-id alimentando a
# senha por pty atraves de um trecho Python inline (mesmo codigo
# auditado da funcao _ssh_copy_id_com_senha do script Python).
# =======================================================================

# NAME:        _localiza_chave_ssh_local
# DESCRIPTION: Procura uma chave SSH no home do usuario. Verifica
#              id_rsa primeiro (compatibilidade), depois id_ed25519
#              (padrao moderno). Exporta os caminhos via variaveis
#              globais SSH_KEY_PRIV e SSH_KEY_PUB. Retorna 0 se
#              encontrou, 1 se nao.
# PARAMETER:   nenhum
_localiza_chave_ssh_local() {
    SSH_KEY_PRIV=""
    SSH_KEY_PUB=""
    if [ -f "$SSH_KEY_RSA" ] && [ -f "${SSH_KEY_RSA}.pub" ]; then
        SSH_KEY_PRIV="$SSH_KEY_RSA"
        SSH_KEY_PUB="${SSH_KEY_RSA}.pub"
        return 0
    fi
    if [ -f "$SSH_KEY_ED25519" ] && [ -f "${SSH_KEY_ED25519}.pub" ]; then
        SSH_KEY_PRIV="$SSH_KEY_ED25519"
        SSH_KEY_PUB="${SSH_KEY_ED25519}.pub"
        return 0
    fi
    return 1
}

# NAME:        _gera_chave_ssh_local
# DESCRIPTION: Gera uma chave ed25519 sem passphrase via ssh-keygen,
#              de forma nao-interativa. Cria ~/.ssh com permissoes
#              0700 se necessario. Em sucesso, popula SSH_KEY_PRIV e
#              SSH_KEY_PUB.
# PARAMETER:   nenhum
_gera_chave_ssh_local() {
    local dir_ssh="${HOME}/.ssh"
    if [ ! -d "$dir_ssh" ]; then
        mkdir -p "$dir_ssh" && chmod 700 "$dir_ssh" || {
            log "ERROR - Bootstrap SSH: falha ao criar $dir_ssh"
            return 1
        }
    fi

    ssh-keygen -q -t ed25519 -N "" -f "$SSH_KEY_ED25519" \
        -C "survey_asset_tag bootstrap" < /dev/null > /dev/null 2>&1
    if [ $? -ne 0 ] || [ ! -f "$SSH_KEY_ED25519" ]; then
        log "ERROR - Bootstrap SSH: ssh-keygen falhou ao gerar $SSH_KEY_ED25519"
        return 1
    fi

    SSH_KEY_PRIV="$SSH_KEY_ED25519"
    SSH_KEY_PUB="${SSH_KEY_ED25519}.pub"
    log "INFO - Bootstrap SSH: chave ed25519 gerada em $SSH_KEY_PRIV"
    return 0
}

# NAME:        _ssh_copy_id_com_senha
# DESCRIPTION: Distribui a chave publica para um host via ssh-copy-id,
#              alimentando a senha SSH atraves de um pseudo-terminal.
#              A logica de pty e implementada em python3 inline (mesmo
#              algoritmo do _ssh_copy_id_com_senha do update_dmi_tag.py
#              v2.0.1). A senha vai via stdin do python3, nunca como
#              argumento (evita exposicao em ps).
# PARAMETER:   $1 - IP do host remoto
#              $2 - usuario SSH
#              $3 - senha SSH (em texto puro)
#              $4 - caminho da chave publica local
# RETURNS:     0 em sucesso, 1 em falha. Erros sao logados via log().
_ssh_copy_id_com_senha() {
    local ip="$1" user="$2" senha="$3" pub="$4"

    if [ -z "$senha" ]; then
        log "ERROR - [$ip] Bootstrap SSH: nenhuma senha SSH disponivel (--ssh-pass, SSH_PASS env ou --ssh-pass-file)"
        return 1
    fi
    if [ ! -f "$pub" ]; then
        log "ERROR - [$ip] Bootstrap SSH: chave publica nao encontrada: $pub"
        return 1
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        log "ERROR - [$ip] Bootstrap SSH: python3 nao encontrado no PATH (necessario para distribuir chave via pty)"
        return 1
    fi

    # Senha vai via stdin do python3 (nao via argv) para nao aparecer em ps.
    # IP, user e chave publica vao via argv (nao sao sensiveis).
    # Saida de stderr do python3 e capturada para diagnostico.
    local py_stderr py_rc
    py_stderr=$(printf '%s' "$senha" | python3 - "$ip" "$user" "$pub" 2>&1 <<'PYEOF'
import sys, os, pty, select, time, errno

ip          = sys.argv[1]
user        = sys.argv[2]
caminho_pub = sys.argv[3]
senha       = sys.stdin.read()

argv = [
    "ssh-copy-id",
    "-i", caminho_pub,
    "-o", "ConnectTimeout=10",
    "-o", "StrictHostKeyChecking=no",
    "-o", "PreferredAuthentications=password,keyboard-interactive",
    "-o", "PubkeyAuthentication=no",
    "{}@{}".format(user, ip),
]

try:
    pid, fd = pty.fork()
except OSError as e:
    sys.stderr.write("pty.fork falhou: {}\n".format(e))
    sys.exit(2)

if pid == 0:
    try:
        os.execvp("ssh-copy-id", argv)
    except FileNotFoundError:
        os._exit(127)
    except Exception:
        os._exit(126)

timeout_total = 30.0
inicio        = time.time()
buffer_saida  = ""
senha_enviada = False
saida_total   = []

try:
    while True:
        decorrido = time.time() - inicio
        if decorrido >= timeout_total:
            sys.stderr.write("ssh-copy-id timeout ({:.0f} s)\n".format(timeout_total))
            try: os.kill(pid, 9)
            except Exception: pass
            try: os.close(fd)
            except Exception: pass
            try: os.waitpid(pid, 0)
            except Exception: pass
            sys.exit(3)

        restante = timeout_total - decorrido
        try:
            pronto, _, _ = select.select([fd], [], [], min(1.0, restante))
        except (OSError, select.error) as e:
            if getattr(e, "errno", None) == errno.EINTR:
                continue
            break

        if not pronto:
            continue

        try:
            pedaco = os.read(fd, 4096)
        except OSError:
            break
        if not pedaco:
            break

        try:
            texto = pedaco.decode("utf-8", errors="replace")
        except Exception:
            texto = ""

        saida_total.append(texto)
        buffer_saida += texto
        b_lower = buffer_saida.lower()

        if (not senha_enviada) and (
            "password:" in b_lower
            or "password for" in b_lower
            or "'s password" in b_lower
        ):
            try:
                os.write(fd, (senha + "\n").encode("utf-8"))
                senha_enviada = True
                buffer_saida = ""
            except OSError as e:
                sys.stderr.write("falha ao injetar senha no pty: {}\n".format(e))
                break

        if (
            "permission denied" in b_lower
            or "too many authentication failures" in b_lower
            or "no supported authentication methods" in b_lower
        ):
            sys.stderr.write("autenticacao rejeitada (senha incorreta ou SSH bloqueado)\n")
            try: os.kill(pid, 9)
            except Exception: pass
            try: os.close(fd)
            except Exception: pass
            try: os.waitpid(pid, 0)
            except Exception: pass
            sys.exit(4)
finally:
    try: os.close(fd)
    except Exception: pass

try:
    _, status = os.waitpid(pid, 0)
except Exception as e:
    sys.stderr.write("waitpid falhou: {}\n".format(e))
    sys.exit(5)

if os.WIFEXITED(status):
    rc = os.WEXITSTATUS(status)
elif os.WIFSIGNALED(status):
    rc = 128 + os.WTERMSIG(status)
else:
    rc = -1

if rc == 0:
    sys.exit(0)
if rc == 127:
    sys.stderr.write("binario ssh-copy-id nao encontrado no PATH local\n")
else:
    cauda = ("".join(saida_total))[-200:].replace("\n", " | ").strip()
    sys.stderr.write("ssh-copy-id encerrou com rc={} (cauda: {})\n".format(rc, cauda or "vazio"))
sys.exit(6)
PYEOF
)
    py_rc=$?

    if [ $py_rc -eq 0 ]; then
        return 0
    fi

    log "ERROR - [$ip] Bootstrap SSH: ssh-copy-id falhou (rc=$py_rc): ${py_stderr}"
    return 1
}

# NAME:        prepara_autenticacao_ssh
# DESCRIPTION: Orquestra o bootstrap de autenticacao SSH para um host.
#              Fluxo:
#                1. Localiza chave SSH local (RSA ou ed25519).
#                2. Se nenhuma existe, gera id_ed25519.
#                3. Testa conexao por chave (BatchMode=yes). Caminho
#                   feliz: retorna 0 silenciosamente.
#                4. Se falhar e ha senha disponivel, executa
#                   _ssh_copy_id_com_senha.
#                5. Reconfere conexao por chave apos copy-id.
# PARAMETER:   $1 - IP do host
# RETURNS:     0 se host esta acessivel por chave, 1 caso contrario.
prepara_autenticacao_ssh() {
    local ip="$1"

    # 1. Localiza ou gera chave
    if ! _localiza_chave_ssh_local; then
        _gera_chave_ssh_local || return 1
    fi

    # 2. Caminho feliz: chave ja distribuida
    if ssh $SSH_OPTS_BATCH "${SSH_USER}@${ip}" "true" 2>/dev/null; then
        return 0
    fi

    # 3. Sem senha disponivel: nao da pra fazer copy-id
    if [ -z "$SSH_PASS_EFETIVA" ]; then
        log "ERROR - [$ip] Bootstrap SSH: chave nao autorizada e nenhuma senha SSH fornecida"
        return 1
    fi

    log "INFO - [$ip] Bootstrap SSH: distribuindo chave publica via ssh-copy-id"

    if ! _ssh_copy_id_com_senha "$ip" "$SSH_USER" "$SSH_PASS_EFETIVA" "$SSH_KEY_PUB"; then
        return 1
    fi

    # 4. Reconfere via chave
    if ssh $SSH_OPTS_BATCH "${SSH_USER}@${ip}" "true" 2>/dev/null; then
        log "INFO - [$ip] Bootstrap SSH: chave distribuida e conexao validada"
        return 0
    fi

    log "ERROR - [$ip] Bootstrap SSH: ssh-copy-id reportou sucesso mas a reconexao por chave ainda falha"
    return 1
}


# =======================================================================
# UTILITARIOS SSH / SCP
# =======================================================================

# NAME:        ssh_run
# DESCRIPTION: Executa um comando no host remoto via SSH (BatchMode=yes).
#              Captura stdout, ignora stderr. Retorna a saida no stdout
#              da funcao e o rc no $?. Nao usa TTY.
# PARAMETER:   $1 - IP
#              $2 - comando shell
ssh_run() {
    ssh $SSH_OPTS_BATCH "${SSH_USER}@${1}" "$2" 2>/dev/null
}

# NAME:        ssh_run_with_rc
# DESCRIPTION: Variante de ssh_run que tambem retorna stderr e o rc
#              real do comando remoto (e nao do ssh). Util quando o
#              rc do comando importa para logica de erro.
# PARAMETER:   $1 - IP
#              $2 - comando shell
#              $3 - variavel de saida (nameref)
# RETURNS:     rc do comando remoto via $? do ssh
ssh_run_capture() {
    ssh $SSH_OPTS_BATCH "${SSH_USER}@${1}" "$2" 2>&1
}

# NAME:        scp_arquivo
# DESCRIPTION: Copia um arquivo local para um host remoto via scp com
#              BatchMode. Retorna 0 em sucesso, 1 em falha. A mensagem
#              de erro do scp e logada.
# PARAMETER:   $1 - IP
#              $2 - caminho local
#              $3 - caminho remoto
scp_arquivo() {
    local ip="$1" local_path="$2" remote_path="$3"
    local err_msg

    err_msg=$(scp $SSH_OPTS_BATCH "$local_path" "${SSH_USER}@${ip}:${remote_path}" 2>&1)
    if [ $? -eq 0 ]; then
        return 0
    fi
    log "ERROR - [$ip] scp falhou: $(echo "$err_msg" | tr '\n' ' | ' | head -c 200)"
    return 1
}

# NAME:        get_sudo
# DESCRIPTION: Detecta como executar sudo no host remoto. Tenta sudo
#              sem senha primeiro; se falhar e --sudo-pass for fornecido,
#              monta o pipe com a senha. Retorna o prefixo no stdout.
# PARAMETER:   $1 - IP
get_sudo() {
    local ip="$1" r
    r=$(ssh_run "$ip" "sudo -n true 2>/dev/null && echo OK || echo FAIL")
    if [ "$r" = "OK" ]; then
        echo "sudo"
    elif [ -n "$SUDO_PASS" ]; then
        printf "echo '%s' | sudo -S" "$SUDO_PASS"
    else
        echo "sudo"
    fi
}


# =======================================================================
# DETECTORES DE INDICADORES DE COMPATIBILIDADE
# =======================================================================

# NAME:        detecta_wsmt
# DESCRIPTION: Detecta se a tabela ACPI WSMT esta presente. Verifica
#              via dmesg (precisa de sudo se restricted_dmesg=1).
# PARAMETER:   $1 - IP
#              $2 - sudo_cmd
# RETURNS:     "Presente" ou "Ausente" no stdout
detecta_wsmt() {
    local ip="$1" sudo_cmd="$2" r
    r=$(ssh_run "$ip" "$sudo_cmd dmesg 2>/dev/null | grep -i wsmt | head -1")
    if [ -z "$r" ]; then
        echo "Ausente"
    else
        echo "Presente"
    fi
}

# NAME:        detecta_secure_boot
# DESCRIPTION: Detecta o estado do Secure Boot via mokutil ou via
#              variavel EFI SecureBoot. Indispensavel para predicao
#              de compatibilidade dos modelos Daten.
# PARAMETER:   $1 - IP
#              $2 - sudo_cmd
# RETURNS:     "ON", "OFF" ou "N/D" no stdout
detecta_secure_boot() {
    local ip="$1" sudo_cmd="$2" r

    # Tenta mokutil primeiro (mais confiavel)
    r=$(ssh_run "$ip" "command -v mokutil >/dev/null 2>&1 && $sudo_cmd mokutil --sb-state 2>/dev/null")
    if echo "$r" | grep -qi "SecureBoot enabled"; then
        echo "ON"
        return
    fi
    if echo "$r" | grep -qi "SecureBoot disabled"; then
        echo "OFF"
        return
    fi

    # Fallback: ler variavel EFI direto
    r=$(ssh_run "$ip" "$sudo_cmd od -An -t u1 /sys/firmware/efi/efivars/SecureBoot-* 2>/dev/null | tr -s ' ' | awk '{print \$NF}' | tail -1")
    case "$r" in
        1) echo "ON" ;;
        0) echo "OFF" ;;
        *) echo "N/D" ;;
    esac
}

# NAME:        detecta_lockdown
# DESCRIPTION: Detecta o modo de kernel lockdown atual.
#              "none" -> aberto; "integrity" ou "confidentiality" ->
#              bloqueia ioremap e modulos nao assinados.
# PARAMETER:   $1 - IP
# RETURNS:     "none", "integrity", "confidentiality" ou "N/D"
detecta_lockdown() {
    local ip="$1" r
    r=$(ssh_run "$ip" "cat /sys/kernel/security/lockdown 2>/dev/null")
    # Saida tipica: "none [integrity] confidentiality" -- o valor entre [] e o ativo
    if [ -z "$r" ]; then
        echo "N/D"
        return
    fi
    echo "$r" | grep -oE '\[[^]]+\]' | tr -d '[]'
}

# NAME:        detecta_strict_devmem
# DESCRIPTION: Detecta se CONFIG_STRICT_DEVMEM esta habilitado no
#              kernel ativo. Procura em varios caminhos: /boot/config-*,
#              /proc/config.gz, /lib/modules/*/build/.config.
# PARAMETER:   $1 - IP
# RETURNS:     "Y", "N" ou "N/D"
detecta_strict_devmem() {
    local ip="$1" r
    r=$(ssh_run "$ip" '
        kver=$(uname -r)
        for cfg in /boot/config-$kver /boot/config /proc/config.gz; do
            if [ -f "$cfg" ]; then
                if [ "${cfg##*.}" = "gz" ]; then
                    zcat "$cfg" 2>/dev/null | grep "^CONFIG_STRICT_DEVMEM=" | head -1
                else
                    grep "^CONFIG_STRICT_DEVMEM=" "$cfg" 2>/dev/null | head -1
                fi
                break
            fi
        done
    ')
    case "$r" in
        *=y) echo "Y" ;;
        *"is not set"*) echo "N" ;;
        *) echo "N/D" ;;
    esac
}


# =======================================================================
# CLASSIFICACAO PREDITIVA
# =======================================================================

# NAME:        classifica_compatibilidade
# DESCRIPTION: Baseada nos indicadores coletados, retorna a classifi-
#              cacao preditiva de compatibilidade:
#                - PROVAVEL-OK     : WSMT Ausente OU (WSMT presente
#                                    sem Secure Boot e sem lockdown)
#                - PROVAVEL-FALHA  : WSMT presente + Secure Boot ON +
#                                    lockdown integrity (perfil dos
#                                    Daten DH3UP/H4U02PER)
#                - INDETERMINADO   : qualquer outra combinacao ou
#                                    indicadores N/D
# PARAMETER:   $1 - wsmt        (Presente/Ausente)
#              $2 - secure_boot (ON/OFF/N/D)
#              $3 - lockdown    (none/integrity/confidentiality/N/D)
# RETURNS:     classificacao no stdout
classifica_compatibilidade() {
    local wsmt="$1" sb="$2" lock="$3"

    if [ "$wsmt" = "Ausente" ]; then
        echo "PROVAVEL-OK"
        return
    fi

    # WSMT presente daqui em diante
    if [ "$sb" = "ON" ] && [ "$lock" = "integrity" ]; then
        echo "PROVAVEL-FALHA"
        return
    fi
    if [ "$sb" = "ON" ] && [ "$lock" = "confidentiality" ]; then
        echo "PROVAVEL-FALHA"
        return
    fi

    if [ "$sb" = "OFF" ] && [ "$lock" = "none" ]; then
        echo "PROVAVEL-OK"
        return
    fi

    echo "INDETERMINADO"
}


# =======================================================================
# TESTES DE CAPACIDADE DE GRAVACAO (REWRITE NO-OP)
#
# Ambos os testes regravam exatamente o valor atual, nao alterando
# nada visivel. Capturam o sucesso ou falha do mecanismo de escrita
# em si (ex.: Error 24 ocorre na alocacao de buffer, antes da escrita,
# entao se manifesta mesmo em rewrite no-op).
# =======================================================================

# NAME:        eh_tag_virgem
# DESCRIPTION: Avalia se o valor recebido representa uma tag virgem
#              (placa nunca gravada), em que o teste de rewrite no-op
#              nao deve ser executado.
# PARAMETER:   $1 - valor atual da tag
# RETURNS:     0 se virgem, 1 caso contrario
eh_tag_virgem() {
    [[ "$1" =~ $TAG_VIRGEM_PATTERNS ]]
}

# NAME:        test_write_mec1
# DESCRIPTION: Testa a capacidade de escrita via amidelnx_64 com
#              estrategia rewrite no-op. Se o binario nao esta no
#              host, faz scp primeiro. Se scp falhar, retorna FALHOU-scp.
# PARAMETER:   $1 - IP
#              $2 - sudo_cmd
#              $3 - tag atual (para regravar identica)
# RETURNS:     resultado no stdout: OK, SEM-SCP, TAG-VIRGEM, ou
#              "FALHOU-rcN-msg" com o erro especifico
test_write_mec1() {
    local ip="$1" sudo_cmd="$2" tag_atual="$3"
    local rc saida amide_rem

    if eh_tag_virgem "$tag_atual"; then
        echo "TAG-VIRGEM"
        return
    fi

    amide_rem="$AMIDE_REMOTE"

    # Garante o binario no host: usa rc direto do test -f (sem echo trick)
    ssh_run "$ip" "test -f $amide_rem"
    if [ $? -ne 0 ]; then
        if [ ! -f "$AMIDE_LOCAL" ]; then
            echo "SEM-SCP-bin-local"
            return
        fi
        if ! scp_arquivo "$ip" "$AMIDE_LOCAL" "$amide_rem"; then
            echo "SEM-SCP-erro"
            return
        fi
        # Conferencia pos-scp
        ssh_run "$ip" "test -f $amide_rem"
        if [ $? -ne 0 ]; then
            echo "SEM-SCP-confirma"
            return
        fi
    fi

    ssh_run "$ip" "chmod +x $amide_rem" >/dev/null 2>&1

    # Rewrite no-op: grava o MESMO valor atual.
    # Saida agregada (stderr + stdout) para capturar mensagens de erro.
    saida=$(ssh_run_capture "$ip" "$sudo_cmd $amide_rem /ca '$tag_atual' 2>&1; echo RC=\$?")
    rc=$(echo "$saida" | grep -oE 'RC=[0-9]+' | tail -1 | cut -d= -f2)
    [ -z "$rc" ] && rc=99

    if [ "$rc" = "0" ] && echo "$saida" | grep -q "Done"; then
        echo "OK"
        return
    fi

    # Tenta extrair o codigo de erro AMIDE
    local err_amide
    err_amide=$(echo "$saida" | grep -oE '^[0-9]+ - Error:.*' | head -1 | cut -c1-50)
    if [ -n "$err_amide" ]; then
        # Sanitiza espacos e separadores para nao quebrar a tabela
        err_amide=$(echo "$err_amide" | tr -d "$FS" | tr -s ' ')
        echo "FALHOU-rc${rc}: $err_amide"
        return
    fi

    echo "FALHOU-rc${rc}"
}

# NAME:        test_write_mec2
# DESCRIPTION: Testa a capacidade de escrita via amibios_dmi (sysfs)
#              com estrategia rewrite no-op. So executa se o sysfs
#              existe (driver instalado). NUNCA tenta instalar o driver.
# PARAMETER:   $1 - IP
#              $2 - sudo_cmd
#              $3 - tag atual (para regravar identica)
# RETURNS:     resultado no stdout: OK, SEM-DRIVER, TAG-VIRGEM, ou
#              "FALHOU-..." com motivo
test_write_mec2() {
    local ip="$1" sudo_cmd="$2" tag_atual="$3"
    local rc saida

    if eh_tag_virgem "$tag_atual"; then
        echo "TAG-VIRGEM"
        return
    fi

    # Verifica se sysfs existe
    ssh_run "$ip" "$sudo_cmd test -f $DEFAULT_SYSFS_TARGET"
    if [ $? -ne 0 ]; then
        echo "SEM-DRIVER"
        return
    fi

    # Rewrite no-op via tee (precisa de root, nao apenas sudo cat)
    saida=$(ssh_run_capture "$ip" "echo -n '$tag_atual' | $sudo_cmd tee $DEFAULT_SYSFS_TARGET 2>&1; echo RC=\$?")
    rc=$(echo "$saida" | grep -oE 'RC=[0-9]+' | tail -1 | cut -d= -f2)
    [ -z "$rc" ] && rc=99

    if [ "$rc" = "0" ]; then
        echo "OK"
        return
    fi

    # Captura motivo: SMI error 0x84 e o caso classico
    local motivo
    motivo=$(echo "$saida" | grep -oE 'SMI error 0x[0-9a-fA-F]+' | head -1)
    if [ -n "$motivo" ]; then
        echo "FALHOU-$motivo"
        return
    fi

    echo "FALHOU-rc${rc}"
}


# =======================================================================
# SURVEY POR HOST
# =======================================================================

# NAME:        survey_host
# DESCRIPTION: Orquestra a coleta completa para um equipamento. Faz
#              o bootstrap SSH, detecta sudo, coleta identificacao,
#              placa, SMBIOS, indicadores (WSMT, Secure Boot, lockdown,
#              STRICT_DEVMEM), tag atual, e -- se TEST_WRITE estiver
#              ativo -- executa os testes rewrite no-op dos dois meca-
#              nismos. Adiciona uma entrada ao array SUMMARY.
# PARAMETER:   $1 - IP
survey_host() {
    local ip="$1"
    local sudo_cmd hostname_val kernel_val os_val
    local board_vendor board_name smbios_ver bios_ver
    local wsmt sb lockdown strict_dm uefi
    local tag_atual bem_numero
    local diagnostico mec1_res mec2_res

    log_raw ""
    log_raw "======================================================================"
    log "INFO - HOST: $ip"
    log_raw "======================================================================"

    # 0. Bootstrap SSH (silencioso no caminho feliz)
    if ! prepara_autenticacao_ssh "$ip"; then
        log "ERROR - Host inacessivel via SSH (bootstrap falhou)"
        SUMMARY+=("N/D${FS}${ip}${FS}N/D${FS}N/D${FS}N/D${FS}N/D${FS}N/D${FS}N/D${FS}N/D${FS}N/D${FS}N/D${FS}N/D${FS}INACESSIVEL")
        return
    fi

    # 1. Sudo
    sudo_cmd=$(get_sudo "$ip")
    log "INFO - sudo prefix: $sudo_cmd"

    # 2. Identificacao
    log_raw "--- Identificacao ---"
    hostname_val=$(ssh_run "$ip" "hostname")
    kernel_val=$(ssh_run "$ip" "uname -r")
    os_val=$(ssh_run "$ip" "grep '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d'=' -f2 | tr -d '\"'")
    log "INFO - Hostname  : $hostname_val"
    log "INFO - Kernel    : $kernel_val"
    log "INFO - OS        : $os_val"

    # 3. Placa-mae
    log_raw "--- Placa-mae ---"
    board_vendor=$(ssh_run "$ip" "cat /sys/class/dmi/id/board_vendor 2>/dev/null")
    board_name=$(ssh_run "$ip" "cat /sys/class/dmi/id/board_name 2>/dev/null")
    [ -z "$board_vendor" ] && board_vendor="N/D"
    [ -z "$board_name" ] && board_name="N/D"
    log "INFO - Fabricante: $board_vendor"
    log "INFO - Modelo    : $board_name"

    # 4. SMBIOS / BIOS
    log_raw "--- SMBIOS / BIOS ---"
    smbios_ver=$(ssh_run "$ip" "$sudo_cmd dmidecode 2>/dev/null | grep -i 'smbios'" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    bios_ver=$(ssh_run "$ip" "$sudo_cmd dmidecode -s bios-version 2>/dev/null")
    [ -z "$smbios_ver" ] && smbios_ver="N/D"
    [ -z "$bios_ver" ] && bios_ver="N/D"
    log "INFO - SMBIOS    : $smbios_ver"
    log "INFO - BIOS ver  : $bios_ver"

    # 5. Indicadores de compatibilidade
    log_raw "--- Indicadores de Compatibilidade ---"
    wsmt=$(detecta_wsmt "$ip" "$sudo_cmd")
    sb=$(detecta_secure_boot "$ip" "$sudo_cmd")
    lockdown=$(detecta_lockdown "$ip")
    strict_dm=$(detecta_strict_devmem "$ip")
    log "INFO - WSMT          : $wsmt"
    log "INFO - Secure Boot   : $sb"
    log "INFO - Kernel Lockdown: $lockdown"
    log "INFO - STRICT_DEVMEM : $strict_dm"

    # 6. Boot UEFI (informativo)
    uefi=$(ssh_run "$ip" "test -d /sys/firmware/efi && echo Confirmado || echo Legacy")
    log "INFO - Boot UEFI    : $uefi"

    # 7. Tag atual (somente leitura)
    log_raw "--- Estado Atual da Tag ---"
    tag_atual=$(ssh_run "$ip" "$sudo_cmd dmidecode -s chassis-asset-tag 2>/dev/null" | head -1)
    [ -z "$tag_atual" ] && tag_atual="N/D"
    log "INFO - Tag atual : $tag_atual"

    bem_numero=$(ssh_run "$ip" "grep '^BEM_NUMERO=' /etc/BBconfig.conf 2>/dev/null | cut -d'\"' -f2")
    [ -z "$bem_numero" ] && bem_numero="(vazio/ausente)"
    log "INFO - BEM_NUMERO: $bem_numero"

    # 8. Classificacao preditiva
    diagnostico=$(classifica_compatibilidade "$wsmt" "$sb" "$lockdown")
    log "INFO - Diagnostico predicativo: $diagnostico"

    # 9. Teste de gravacao (so se --test-write ativo)
    mec1_res="Nao testado"
    mec2_res="Nao testado"
    if [ $TEST_WRITE -eq 1 ]; then
        log_raw "--- Teste de Capacidade de Gravacao (rewrite no-op) ---"
        log "INFO - Mecanismo 1 (amidelnx_64): testando..."
        mec1_res=$(test_write_mec1 "$ip" "$sudo_cmd" "$tag_atual")
        log "INFO - Mec1: $mec1_res"
        log "INFO - Mecanismo 2 (amibios_dmi sysfs): testando..."
        mec2_res=$(test_write_mec2 "$ip" "$sudo_cmd" "$tag_atual")
        log "INFO - Mec2: $mec2_res"
    fi

    # 10. Inscreve no resumo
    SUMMARY+=("$(echo "$hostname_val"  | cut -c1-15)${FS}${ip}${FS}$(echo "$board_vendor" | cut -c1-17)${FS}$(echo "$board_name" | cut -c1-21)${FS}${smbios_ver}${FS}${wsmt}${FS}${sb}${FS}${lockdown}${FS}${strict_dm}${FS}$(echo "$tag_atual" | cut -c1-15)${FS}$(echo "$mec1_res" | cut -c1-20)${FS}$(echo "$mec2_res" | cut -c1-15)${FS}${diagnostico}")

    log_raw "----------------------------------------------------------------------"
}


# =======================================================================
# TABELA DE RESUMO
# =======================================================================

# NAME:        print_summary
# DESCRIPTION: Imprime a tabela de resumo ao final da execucao, com
#              uma linha por host.
# PARAMETER:   nenhum
print_summary() {
    local div hdr fmt

    div="+----+-----------------+---------------+-------------------+----------------------+--------+----------+--------+------------+-----+-----------------+----------------------+-----------------+------------------+"
    hdr="| #  | Hostname        | IP            | Fabricante        | Modelo               | SMBIOS | WSMT     | SecBT  | Lockdown   | Sdm | Tag atual       | Mec1 (amidelnx)      | Mec2 (sysfs)    | Diagnostico      |"
    fmt="| %-3s| %-16s| %-14s| %-18s| %-21s| %-7s| %-9s| %-7s| %-11s| %-4s| %-16s| %-21s| %-16s| %-17s|\n"

    log_raw ""
    log_raw "============================================================================================================================================================================================================================"
    log_raw "RESUMO FINAL -- $(date '+%Y-%m-%d %H:%M:%S')"
    log_raw "============================================================================================================================================================================================================================"
    log_raw "$div"
    log_raw "$hdr"
    log_raw "$div"

    local idx=1 entry linha
    for entry in "${SUMMARY[@]}"; do
        IFS="$FS" read -r f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 f12 f13 <<< "$entry"
        linha=$(printf "$fmt" "$idx" "$f1" "$f2" "$f3" "$f4" "$f5" "$f6" "$f7" "$f8" "$f9" "$f10" "$f11" "$f12" "$f13")
        log_raw "$linha"
        idx=$((idx + 1))
    done

    log_raw "$div"
    log_raw ""

    # Contadores agregados
    local total ok falha indet inacess
    total=${#SUMMARY[@]}
    ok=$(printf '%s\n' "${SUMMARY[@]}" | grep -c "PROVAVEL-OK$" || true)
    falha=$(printf '%s\n' "${SUMMARY[@]}" | grep -c "PROVAVEL-FALHA$" || true)
    indet=$(printf '%s\n' "${SUMMARY[@]}" | grep -c "INDETERMINADO$" || true)
    inacess=$(printf '%s\n' "${SUMMARY[@]}" | grep -c "INACESSIVEL$" || true)

    log_raw "  Total          : $total"
    log_raw "  PROVAVEL-OK    : $ok"
    log_raw "  PROVAVEL-FALHA : $falha"
    log_raw "  INDETERMINADO  : $indet"
    log_raw "  INACESSIVEL    : $inacess"
    log_raw ""
}


# =======================================================================
# MAIN
# =======================================================================

# NAME:        main
# DESCRIPTION: Ponto de entrada. Faz parse de args, abre o log em
#              modo append (nunca trunca), itera pelos hosts (filtrando
#              comentarios inteiros e trailing), chama survey_host
#              para cada e imprime o resumo final.
# PARAMETER:   $@ - argumentos
main() {
    parse_args "$@"

    # Log em modo append. Se o arquivo nao existe, cria. Se ja existe,
    # acrescenta separador visual e continua. NUNCA trunca.
    if [ -n "$LOG_FILE" ]; then
        if [ -f "$LOG_FILE" ]; then
            echo "" >> "$LOG_FILE"
        fi
        # touch garante que o arquivo existe antes do primeiro log
        touch "$LOG_FILE" 2>/dev/null || {
            echo "AVISO: nao foi possivel criar o arquivo de log $LOG_FILE" >&2
            LOG_FILE=""
        }
    fi

    log_raw "======================================================================"
    log "INFO - $SCRIPT_NAME v$SCRIPT_VERSION"
    log "INFO - Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
    log "INFO - Hosts : $HOSTS_FILE"
    log "INFO - User  : $SSH_USER"
    log "INFO - Amide local : $AMIDE_LOCAL"
    log "INFO - Amide remoto: $AMIDE_REMOTE"
    [ -n "$LOG_FILE" ] && log "INFO - Log   : $LOG_FILE (append)"
    if [ $TEST_WRITE -eq 1 ]; then
        log "INFO - Modo  : SURVEY + TEST-WRITE (rewrite no-op, nao altera tag)"
    else
        log "INFO - Modo  : SURVEY-ONLY (sem teste de gravacao)"
    fi
    log_raw "======================================================================"

    local count=0 line ip

    # Descritor fd3 dedicado para o arquivo de hosts (nao conflita com stdin SSH).
    # Filtra: linhas vazias, comentarios inteiros (#...), comentarios trailing
    # (alinhado com a logica de le_arquivo_hosts do update_dmi_tag.py v2.0.3).
    while IFS= read -r line <&3 || [ -n "$line" ]; do
        # Remove CR e comentario trailing (tudo a partir do primeiro #)
        line=$(echo "$line" | tr -d '\r')
        line="${line%%#*}"
        # Trim
        line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [ -z "$line" ] && continue

        ip=$(echo "$line" | awk '{print $1}' | cut -d',' -f1)
        [ -z "$ip" ] && continue

        count=$((count + 1))
        survey_host "$ip"
    done 3< "$HOSTS_FILE"

    print_summary

    log_raw "======================================================================"
    log "INFO - FINALE"
    log "INFO - Fim   : $(date '+%Y-%m-%d %H:%M:%S')"
    log "INFO - Total : $count equipamento(s) processado(s)"
    [ -n "$LOG_FILE" ] && log "INFO - Log   : $LOG_FILE"
    log_raw "======================================================================"
}

main "$@"
