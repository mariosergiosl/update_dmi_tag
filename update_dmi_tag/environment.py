# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: environment.py
#
# DESCRIPTION: Coleta de metadados de hardware/kernel/SO (local e
#              remoto) e auditoria de dependencias RPM/modulo de kernel.
#              coletar_dados_ambiente (local) e coletar_dados_ambiente_
#              remoto (via SSH) retornam um dicionario com kernel, placa,
#              BIOS, SMBIOS, WSMT, asset tag atual e status UEFI.
#              verifica_pacote_rpm, loga_versao_modulo e
#              instala_modulo_via_zypper tratam da auditoria e instalacao
#              opcional do modulo amibios_dmi (Mecanismo 2). 
#              modulo_esta_carregado e interface_esta_pronta distinguem
#              "modulo inserido no kernel" de "interface SMI respondendo".
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.1
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.0 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
# REVISION: 2026-06-15 - v2.1.3 - cascata de fallback para SMBIOS Ver e
#                        Tag atual em coletar_dados_ambiente_remoto:
#                        SMBIOS tenta dmidecode (grep mais especifico
#                        "SMBIOS.*present"), depois dmidecode -t 0 e
#                        por fim indicativo via bios_version. Tag atual
#                        tenta dmidecode -s chassis-asset-tag e faz
#                        fallback para sysfs chassis_asset_tag (sem
#                        sudo, compativel com Legacy BIOS como
#                        Gigabyte H81M e PERTOSA GA-H81M).
# REVISION: 2026-06-15 - v2.1.1 - adiciona captura de MACs de todas as
#                        interfaces de rede ativas (excluindo lo e
#                        interfaces virtuais) via /sys/class/net. Log
#                        INFO "MAC : ..." adicionado ao bloco de
#                        auditoria de ambiente. Coluna MAC adicionada
#                        no final da tabela detalhada de resumo.
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
#
# =======================================================================

import os
import subprocess

from .constants import SYSMODULE_PATH, SYSFS_IFACE_PATH
from .logging_utils import gravar_log, gravar_log_remoto
from .ssh_utils import ssh_run, _filtra_banner


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


def _le_mac_local():
    """
    NAME: _le_mac_local
    DESCRIPTION: Le os enderecos MAC de todas as interfaces de rede
                 ativas no host local, excluindo interfaces de loopback
                 e virtuais (docker, veth, br-, virbr, vlan). Le
                 diretamente de /sys/class/net/<iface>/address (sem sudo,
                 sem dependencias externas). Ignora MACs zerados
                 (00:00:00:00:00:00) e valores ausentes/invalidos.
    PARAMETER: nenhum
    RETURNS: str -- MACs separados por virgula, ex: "aa:bb:cc:dd:ee:ff,11:22:33:44:55:66"
             ou "DESCONHECIDO" se nenhuma interface valida for encontrada.
    """
    prefixos_excluir = ("lo", "docker", "veth", "br-", "virbr", "vlan",
                        "dummy", "tunl", "gre", "bond")
    macs = []
    try:
        ifaces = sorted(os.listdir("/sys/class/net"))
        for iface in ifaces:
            if any(iface.startswith(p) for p in prefixos_excluir):
                continue
            addr_path = "/sys/class/net/{}/address".format(iface)
            if not os.path.isfile(addr_path):
                continue
            try:
                with open(addr_path, "r") as f:
                    mac = f.read().strip().lower()
            except Exception:
                continue
            if not mac or mac == "00:00:00:00:00:00":
                continue
            # Valida formato basico: 5 dois-pontos em 17 chars
            if len(mac) == 17 and mac.count(":") == 5:
                macs.append("{} ({})".format(mac, iface))
    except Exception:
        pass
    return ", ".join(macs) if macs else "DESCONHECIDO"


def _le_mac_remoto(ip, ssh_user, fn_ssh):
    """
    NAME: _le_mac_remoto
    DESCRIPTION: Le os enderecos MAC de todas as interfaces de rede
                 ativas no host remoto via SSH, sem sudo. Usa leitura
                 direta de /sys/class/net/<iface>/address (disponivel
                 em qualquer SLES/SLED moderno, sem depender do ip ou
                 ifconfig). Exclui loopback e interfaces virtuais
                 (docker, veth, br-, virbr, vlan, dummy, tunl). Ignora
                 MACs zerados (00:00:00:00:00:00).
    PARAMETER: ip       - endereco IP do host remoto (para log externo)
               ssh_user - usuario SSH (para log externo)
               fn_ssh   - funcao callable(cmd) -> str que executa o
                          comando no host remoto e retorna stdout limpo
                          (equivalente ao _ssh() local de
                          coletar_dados_ambiente_remoto)
    RETURNS: str -- MACs separados por virgula, ex: "aa:bb:cc:dd:ee:ff (eth0)"
             ou "DESCONHECIDO" se nenhuma interface valida for encontrada.
    """
    # Coleta lista de interfaces e MACs em um unico comando ssh para
    # minimizar roundtrips. Formato de saida: "<iface>:<mac>" por linha.
    cmd = (
        "for iface in $(ls /sys/class/net/ 2>/dev/null | sort); do "
        "  case $iface in lo|docker*|veth*|br-*|virbr*|vlan*|dummy*|tunl*|gre*|bond*) continue;; esac; "
        "  addr=/sys/class/net/$iface/address; "
        "  [ -f $addr ] && mac=$(cat $addr 2>/dev/null) || continue; "
        "  [ -z \"$mac\" ] || [ \"$mac\" = \"00:00:00:00:00:00\" ] && continue; "
        "  echo \"${iface}:${mac}\"; "
        "done"
    )
    saida = fn_ssh(cmd)
    if not saida or saida == "DESCONHECIDO":
        return "DESCONHECIDO"
    macs = []
    for linha in saida.splitlines():
        linha = linha.strip()
        if not linha or ":" not in linha:
            continue
        partes = linha.split(":", 1)
        if len(partes) != 2:
            continue
        iface = partes[0].strip()
        mac   = partes[1].strip().lower()
        if not mac or mac == "00:00:00:00:00:00":
            continue
        # Valida formato basico: 5 dois-pontos em 17 chars
        if len(mac) == 17 and mac.count(":") == 5:
            macs.append("{} ({})".format(mac, iface))
    return ", ".join(macs) if macs else "DESCONHECIDO"


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

    dados["mac"] = _le_mac_local()
    _log("INFO", "MAC        : {}".format(dados["mac"]))

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

    # SMBIOS version -- cascata de 3 tentativas para compatibilidade
    # com equipamentos antigos (Legacy BIOS, pre-UEFI):
    #   1. dmidecode completo filtrando linhas de ruido (funciona nos Daten)
    #   2. dmidecode -t 0 (type 0 = BIOS info, menos verboso, evita ruido)
    #   3. /sys/class/dmi/id/bios_version como indicativo de versao BIOS
    #      (nao e exatamente a versao SMBIOS mas e o melhor fallback
    #      disponivel em equipamentos sem suporte a dmidecode moderno)
    dados["smbios_version"] = "DESCONHECIDO"

    # Tentativa 1: dmidecode completo (ruido ja filtrado por _ssh_sudo)
    smbios_raw = _ssh_sudo("dmidecode 2>/dev/null | grep -i 'SMBIOS.*present' | head -3")
    m = _re.search(r"(\d+\.\d+\.?\d*)", smbios_raw) if smbios_raw != "DESCONHECIDO" else None
    if m:
        dados["smbios_version"] = m.group(1)
    else:
        # Tentativa 2: dmidecode type 0 (BIOS), mais especifico
        smbios_t0 = _ssh_sudo("dmidecode -t 0 2>/dev/null | grep -i 'SMBIOS' | head -3")
        m2 = _re.search(r"(\d+\.\d+\.?\d*)", smbios_t0) if smbios_t0 != "DESCONHECIDO" else None
        if m2:
            dados["smbios_version"] = m2.group(1)
            _log("DEBUG", "SMBIOS Ver (via dmidecode -t 0): {}".format(dados["smbios_version"]))
        else:
            # Tentativa 3: sysfs -- /sys/firmware/dmi/tables/DMI nao e legivel
            # diretamente, mas /sys/class/dmi/id/ tem bios_version como indicativo
            smbios_sys = _ssh("cat /sys/class/dmi/id/product_version 2>/dev/null")
            if smbios_sys and smbios_sys != "DESCONHECIDO" and smbios_sys.strip() not in ("", "None", "To Be Filled By O.E.M."):
                dados["smbios_version"] = "N/D (BIOS: {})".format(dados.get("bios_version", "?"))
                _log("DEBUG", "SMBIOS Ver: dmidecode sem retorno util; usando indicativo de BIOS.")
            else:
                _log("DEBUG", "SMBIOS Ver: nao foi possivel determinar por nenhum metodo.")

    # WSMT via dmesg com sudo
    wsmt_raw = _ssh_sudo("dmesg | grep -i wsmt | head -3")
    if wsmt_raw and wsmt_raw != "DESCONHECIDO":
        dados["wsmt"]         = "Presente"
        dados["wsmt_detalhe"] = wsmt_raw
    else:
        dados["wsmt"]         = "Ausente"
        dados["wsmt_detalhe"] = ""

    # Asset tag atual -- cascata de 2 tentativas:
    #   1. dmidecode -s chassis-asset-tag com sudo (precisa de privilegio,
    #      funciona em todos os modelos com dmidecode moderno)
    #   2. /sys/class/dmi/id/chassis_asset_tag via sysfs (sem sudo,
    #      funciona em equipamentos Legacy BIOS sem suporte a dmidecode
    #      moderno -- ex: Gigabyte H81M, PERTOSA GA-H81M)
    tag_dmidecode = _ssh_sudo("dmidecode -s chassis-asset-tag")
    if tag_dmidecode and tag_dmidecode != "DESCONHECIDO":
        dados["tag_atual"] = tag_dmidecode
    else:
        tag_sysfs = _ssh("cat /sys/class/dmi/id/chassis_asset_tag 2>/dev/null")
        if tag_sysfs and tag_sysfs != "DESCONHECIDO" and tag_sysfs.strip() not in ("", "None", "Not Specified", "To Be Filled By O.E.M."):
            dados["tag_atual"] = tag_sysfs.strip()
            _log("DEBUG", "Tag atual (via sysfs chassis_asset_tag): {}".format(dados["tag_atual"]))
        else:
            dados["tag_atual"] = "DESCONHECIDO"
            _log("DEBUG", "Tag atual: nao foi possivel determinar via dmidecode nem sysfs.")

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

    dados["mac"] = _le_mac_remoto(ip, ssh_user, _ssh)
    _log("INFO", "MAC        : {}".format(dados["mac"]))

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

