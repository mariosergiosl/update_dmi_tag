# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: constants.py
#
# DESCRIPTION: Constantes de configuracao, valores padrao do projeto,
#              codigos de saida e excecoes customizadas, compartilhadas
#              por todos os demais modulos do pacote update_dmi_tag.
#              Modulo sem efeitos colaterais (apenas definicoes), exceto
#              _detecta_usuario_sessao que e chamada uma vez no import
#              para popular DEFAULT_SSH_USER.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.7
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py (arquivo
#                        unico) na modularizacao em pacote. Conteudo
#                        identico ao bloco de constantes original.
#
# =======================================================================

import os


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

SCRIPT_VERSION = "2.1.2"

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
# Caminho local do binario (para scp). Default: diretorio atual de
# trabalho (cwd) no momento da execucao do shim update_dmi_tag.py.
# Na versao em pacote isso e resolvido em __main__.py, nao aqui, pois
# __file__ deste modulo fica dentro do pacote, nao junto do binario.
DEFAULT_AMIDE_LOCAL_PATH  = os.path.join(os.getcwd(), "amidelnx_64")
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
    """
    NAME: _detecta_usuario_sessao
    DESCRIPTION: Retorna o usuario da sessao atual para uso como default
                 de SSH e como identificador em nomes de backup do
                 BBconfig.conf. Tenta USER, depois LOGNAME, depois
                 os.getlogin(); em ultimo caso retorna "root".
    PARAMETER: nenhum
    RETURNS: str -- nome do usuario
    """
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
# =======================================================================
