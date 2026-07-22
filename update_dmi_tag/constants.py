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
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.2.9
# REVISION: 2026-07-22 - v2.2.9 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-20 - v2.2.8 - adiciona MARCADOR_KMP_KERNEL_INCOMPATIVEL
#                        e eh_kmp_incompativel_com_kernel: distingue "Mecanismo
#                        2 falhou por falta de KMP compilado para o kernel
#                        exato do host" (gap de empacotamento, cobre-se
#                        gerando o RPM certo) de incompatibilidade real de
#                        hardware. write_cascade.py usa isso para bloquear
#                        o Mecanismo 3 (reboot) nesse caso especifico, mesmo
#                        com --allow-efi-fallback (nao adianta arriscar um
#                        reboot por uma lacuna que se resolve so com o RPM
#                        certo, ver rpm/README.md).
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
# REVISION: 2026-07-16 - v2.2.3 - adiciona DEFAULT_MODULE_USERSPACE_PACKAGE
#                        e DEFAULT_MODULE_RPM_DIR (pasta rpm/ do projeto)
#                        para a instalacao remota automatica do KMP
#                        amibios_dmi via scp + zypper local, sem depender
#                        de nenhum host alcancar um repositorio externo
#                        (ver environment.py, bios_sysfs.py, rpm/README.md).
# REVISION: 2026-07-16 - v2.2.2 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.1 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-14 - v2.2.0 - eh_incompatibilidade_firmware() e
#                        SINAIS_INCOMPATIBILIDADE_HW: deteccao de
#                        assinaturas conhecidas de incompatibilidade de
#                        firmware (rc=36 "Problem allocating BIOS
#                        buffer", sysfs rejeitou a escrita, "Fail to
#                        initialize SMBIOS"/"DMI Data write failed"),
#                        confirmadas em campo (Dell Precision 5520 e
#                        Latitude 5320, 2026-07-14, ver Docs_Test_boot/).
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
# REVISION: 2026-07-08 - v2.1.11 - adiciona SegurancaEfiBloqueadaError,
#                        RC_SAFETY_ABORT e as constantes DEFAULT_EFI_* do
#                        Mecanismo 3 (boot EFI temporario, experimental --
#                        ver boot_efi.py).
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py (arquivo
#                        unico) na modularizacao em pacote. Conteudo
#                        identico ao bloco de constantes original.
# REVISION: 2026-07-06 - v2.1.9 - incremento de versao para validacoes previas
#                        e teste de socket TCP na porta 22.
# REVISION: 2026-07-07 - v2.1.10 - incremento de versao: corrige falha
#                        silenciosa na restauracao da tag virgem do
#                        --test-write (novo status RESTORE-FALHOU) e ajusta
#                        a tabela da Fase 1 de triagem.
#
# =======================================================================

import os


def _le_config_repo(chave, env_var, arquivo="bb_repo.conf"):
    """
    NAME: _le_config_repo
    DESCRIPTION: Resolve valores de infraestrutura interna (URLs de repo
                 zypper) sem hardcode no codigo versionado. Ordem de
                 precedencia: arquivo local "bb_repo.conf" (formato
                 CHAVE=valor, uma por linha, gitignored, nunca
                 commitado) > variavel de ambiente > vazio. O arquivo
                 fica no diretorio de trabalho atual; ver
                 bb_repo.conf.example (esse sim versionado, so com
                 placeholders) para o formato esperado.
    PARAMETER: chave    - nome da chave esperada no arquivo (ex: "MODULE_REPO_URL")
               env_var   - nome da variavel de ambiente de fallback
               arquivo   - caminho do arquivo de config (default: bb_repo.conf no cwd)
    RETURNS: str, valor encontrado ou string vazia
    """
    if os.path.isfile(arquivo):
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                for linha in f:
                    linha = linha.strip()
                    if not linha or linha.startswith("#") or "=" not in linha:
                        continue
                    k, v = linha.split("=", 1)
                    if k.strip() == chave:
                        return v.strip()
        except OSError:
            pass
    return os.environ.get(env_var, "")


# =======================================================================
# EXCECOES CUSTOMIZADAS
# =======================================================================

class PatrimonioPendenteError(Exception):
    """
    NAME: PatrimonioPendenteError
    DESCRIPTION: Sinaliza que o BEM_NUMERO esta ausente ou vazio no arquivo
                 de configuracao. Isso e um estado PENDENTE normal
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


class SegurancaEfiBloqueadaError(Exception):
    """
    NAME: SegurancaEfiBloqueadaError
    DESCRIPTION: Sinaliza que o Mecanismo 3 (boot EFI temporario, ver
                 boot_efi.py) nao pode ser tentado com seguranca neste
                 host, Secure Boot ativo, disco com criptografia selada
                 em TPM, particao EFI (ESP) sem espaco/gravavel, binario
                 efibootmgr ausente, ou colisao com entrada de boot
                 existente. A mensagem da excecao carrega o motivo
                 especifico. Levantada SEMPRE antes de qualquer escrita em
                 NVRAM ou copia para a ESP, nada e tocado no host se
                 esta excecao for levantada.
    """


# =======================================================================
# CONSTANTES DE CONFIGURACAO E VALORES PADRAO DO PROJETO
# =======================================================================
SCRIPT_VERSION = "2.2.9"

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
# Repo OBS do amidelnx_64 (para instalacao futura via zypper). Nao
# hardcoded no codigo versionado (URL de infraestrutura interna
# corporativa). Ver _le_config_repo acima e bb_repo.conf.example para
# o formato do arquivo de config local (gitignored).
DEFAULT_AMIDE_REPO_URL    = _le_config_repo("AMIDE_REPO_URL", "BB_AMIDE_REPO_URL")

# --- Mecanismo 2: amibios_dmi via sysfs (fallback) ---
DEFAULT_SYSFS_TARGET   = "/sys/firmware/amibios/chassis/asset_tag"
# URL do repo OBS do KMP amibios_dmi. Em uso ativo (instala_modulo_via_zypper,
# ver environment.py), por isso precisa estar configurado (bb_repo.conf
# ou BB_MODULE_REPO_URL) para o Mecanismo 2 instalar o modulo em hosts
# onde ele ainda nao estiver carregado.
DEFAULT_MODULE_REPO_URL = _le_config_repo("MODULE_REPO_URL", "BB_MODULE_REPO_URL")
DEFAULT_MODULE_PACKAGE  = "amibios-dmi-kmp-default"
# Pacote userspace complementar (nao usado pela leitura/escrita via sysfs,
# instalado apenas por completude/paridade com o fork upstream).
DEFAULT_MODULE_USERSPACE_PACKAGE = "amibios-dmi"
# Diretorio local com os RPMs do fork mariosergiosl/amibios_dmi (GPLv2,
# nao e NDA como amidelnx_64/AMIDEEFIx64.EFI), versionados no proprio
# projeto (ver rpm/README.md). Copiados via scp e instalados via zypper
# local quando o modulo nao estiver presente no host remoto -- evita
# depender de cada host alcancar o OBS externo (ver DEFAULT_MODULE_REPO_URL,
# alternativa mais antiga, mantida por compatibilidade).
DEFAULT_MODULE_RPM_DIR  = os.path.join(os.getcwd(), "rpm")

# Caminhos sysfs para distinguir "modulo carregado" de "interface SMI pronta".
# /sys/module/amibios_dmi existe se o modulo foi inserido no kernel.
# /sys/firmware/amibios so existe se, alem disso, o handshake SMI teve sucesso.
SYSMODULE_PATH          = "/sys/module/amibios_dmi"
SYSFS_IFACE_PATH        = "/sys/firmware/amibios"

# --- Mecanismo 3: boot EFI temporario (AMIDEEFIx64.EFI via UEFI Shell) ---
# Experimental, so acionado explicitamente via --allow-efi-fallback (ver
# boot_efi.py e manual_operacao.md). Reboota o host uma unica vez para
# gravar o Chassis Asset Tag em pre-boot, contornando o bloqueio de WSMT
# que impede os Mecanismos 1/2 em alguns modelos (Daten DH3UP, H4U02PER).
DEFAULT_EFI_LOCAL_DIR      = os.path.join(os.getcwd(), "efi_boot", "dmi-atm")
DEFAULT_EFI_AMIDE_FILENAME = "AMIDEEFIx64.EFI"
DEFAULT_EFI_SHELL_FILENAME = "bootx64.efi"
# Subpasta dentro de EFI/ na ESP remota onde os binarios sao copiados.
DEFAULT_EFI_REMOTE_SUBDIR  = "UPDATEDMITAG"
DEFAULT_ESP_MOUNT_POINT    = "/boot/efi"
DEFAULT_EFI_BOOT_LABEL     = "UPDATE_DMI_TAG_TEMP"
# Folga minima de espaco livre exigida na ESP antes de copiar (os dois
# binarios juntos somam ~1.3 MB; a folga cobre o startup.nsh e evita
# operar com a particao praticamente cheia).
DEFAULT_EFI_MIN_FREE_KB    = 10240
# Tempo maximo (segundos) esperando o host reconectar via SSH apos o
# reboot antes de declarar TRAVADO-POS-REBOOT (precisa de intervencao
# fisica). Nao confundir com os timeouts curtos de ssh_run/testa_porta_ssh.
DEFAULT_EFI_REBOOT_TIMEOUT = 300
DEFAULT_EFI_LOG_FILE       = "./update_dmi_tag_efi.log"

# Assinaturas de mensagem de erro que indicam, com boa confianca,
# incompatibilidade de FIRMWARE com a interface AMI SMI/DMI usada pelos
# 3 mecanismos (nao um problema transitorio de rede/sudo/timeout).
# Constatado em campo (Dell Precision 5520, BIOS 1.39.0, 2026-07-14):
# Mecanismo 1 (rc=36, "Problem allocating BIOS buffer"), Mecanismo 2
# ("sysfs rejeitou a escrita", write() aceito pelo kernel mas rejeitado
# pela BIOS) e Mecanismo 3 ("Fail to initialize SMBIOS" / "DMI Data
# write failed", saida nativa do AMIDEEFIx64.EFI rodando em pre-boot,
# sem SO/kernel envolvido) falharam de forma consistente com esse
# padrao. Ver eh_incompatibilidade_firmware, usado por write_cascade.py
# (Mecanismos 1/2) e boot_efi.py (Mecanismo 3) para decidir entre o
# status generico FALHOU/FALHOU-efiboot e o mais especifico
# INCOMPATIVEL-HW/INCOMPATIVEL-efiboot.
SINAIS_INCOMPATIBILIDADE_HW = (
    "problem allocating bios buffer",
    "sysfs rejeitou a escrita",
    "fail to initialize smbios",
    "dmi data write failed",
)


def eh_incompatibilidade_firmware(detalhe):
    """
    NAME: eh_incompatibilidade_firmware
    DESCRIPTION: Verifica se uma mensagem de erro de mecanismo de escrita
                 bate com alguma assinatura conhecida de incompatibilidade
                 de firmware (ver SINAIS_INCOMPATIBILIDADE_HW). Comparacao
                 case-insensitive, por substring.
    PARAMETER: detalhe - str, mensagem de erro/detalhe de um mecanismo
    RETURNS: bool, True se bate com alguma assinatura conhecida
    """
    texto = (detalhe or "").lower()
    return any(sinal in texto for sinal in SINAIS_INCOMPATIBILIDADE_HW)


# Marcador (nao traduzido, comparado por substring exata) usado por
# environment.py (instala_modulo_remoto) para sinalizar que o Mecanismo 2
# falhou porque nenhum RPM de KMP em module_rpm_dir bate com o kernel
# exato do host, e nao por o hardware/firmware ser incompativel. Ver
# eh_kmp_incompativel_com_kernel, usado por write_cascade.py.
MARCADOR_KMP_KERNEL_INCOMPATIVEL = "KMP-KERNEL-MISMATCH"


def eh_kmp_incompativel_com_kernel(detalhe):
    """
    NAME: eh_kmp_incompativel_com_kernel
    DESCRIPTION: Verifica se uma mensagem de erro do Mecanismo 2 indica
                 falta de RPM de KMP compativel com o kernel exato do
                 host (ver MARCADOR_KMP_KERNEL_INCOMPATIVEL), em vez de
                 incompatibilidade real de hardware/firmware.
    PARAMETER: detalhe - str, mensagem de erro/detalhe do Mecanismo 2
    RETURNS: bool, True se a falha foi por falta de KMP para o kernel
    """
    return MARCADOR_KMP_KERNEL_INCOMPATIVEL in (detalhe or "")


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
    RETURNS: str, nome do usuario
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
RC_SAFETY_ABORT         = 7
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
