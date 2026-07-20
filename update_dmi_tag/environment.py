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
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.2.8
# REVISION: 2026-07-20 - v2.2.8 - corrige 2 bugs no matching de kernel
#                        (revisao externa dos diffs, mesma sessao):
#                        (1) CRITICO: comparava o osrelease completo
#                        ("versao-build-flavor") contra o nome do
#                        arquivo ("kmp-flavor-versao-build.rpm", flavor
#                        antes da versao), nunca batendo com nenhum
#                        candidato real -- regressao total da instalacao
#                        automatica do KMP. Corrigido removendo o sufixo
#                        "-default" do osrelease antes de comparar.
#                        (2) latente: a comparacao era por substring
#                        ("in"), que cruzaria erroneamente versoes com
#                        prefixo em comum (ex. "5.3.18-22" bateria com
#                        um hipotetico "...-5.3.18-220.rpm"). Trocado
#                        para igualdade exata do nome do arquivo
#                        completo. Cobertura em tests/test_regressao.py,
#                        TestInstalaModuloRemotoKernelMatching (exercita
#                        a funcao real, nao mockada).
# REVISION: 2026-07-20 - v2.2.8 - instala_modulo_remoto passa a casar o
#                        kernel real do host (osrelease via SSH) contra o
#                        nome dos candidatos a KMP antes de escolher, em
#                        vez de pegar "o ultimo em ordem alfabetica" da
#                        pasta. Bug real: com varios KMPs na mesma pasta
#                        (um por SP, ver rpm/README.md), o codigo antigo
#                        podia escolher um KMP de outro kernel e falhar
#                        no zypper/modprobe sem motivo claro no log.
#                        Assinatura de retorno muda de bool para
#                        tuple(bool, str): o detalhe agora marca com
#                        constants.MARCADOR_KMP_KERNEL_INCOMPATIVEL quando
#                        a causa e falta de KMP para o kernel do host, para
#                        write_cascade.py bloquear o Mecanismo 3 nesse
#                        caso (ver bios_sysfs.py e write_cascade.py).
# REVISION: 2026-07-20 - v2.2.8 - _limpa_rpms_copiados passa a logar
#                        WARNING quando o "rm -f" remoto falha (antes o
#                        retorno de ssh_run era descartado em silencio;
#                        RPMs orfaos podiam se acumular num host que
#                        ficasse instavel entre a instalacao e a limpeza,
#                        sem nenhum rastro no log).
# REVISION: 2026-07-17 - v2.2.8 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.7 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.6 - instala_modulo_remoto passa a remover do
#                        home do usuario SSH os .rpm que copia (em qualquer
#                        desfecho, via _limpa_rpms_copiados), para nao
#                        deixar arquivos orfaos acumulando entre execucoes.
# REVISION: 2026-07-17 - v2.2.5 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.4 - corrige layout do log: a saida de erro
#                        do zypper install (varias linhas) era passada
#                        inteira num unico _log(), entao so a primeira
#                        linha recebia o prefixo padrao (timestamp/nivel/
#                        host) e o resto aparecia cru no arquivo,
#                        quebrando o layout (mesma classe de problema ja
#                        corrigida no dump do dmesg). Agora loga linha a
#                        linha, cada uma com seu proprio prefixo.
# REVISION: 2026-07-16 - v2.2.3 - implementa de vez a instalacao remota
#                        do KMP amibios_dmi (ate entao so preparada, nunca
#                        conectada ao caminho remoto real, ver bios_sysfs.py
#                        v2.2.3). Novas funcoes: verifica_pacote_rpm_remoto
#                        (rpm -q remoto, loga o NVR completo para permitir
#                        conferir se e o build esperado), instala_modulo_
#                        remoto (localiza os .rpm em module_rpm_dir por
#                        padrao de nome, copia via scp, confere SHA-256 da
#                        copia contra o arquivo local antes de instalar com
#                        sudo -- aborta se nao bater -- e instala via
#                        'zypper install <caminho-local>', reconferindo no
#                        final via rpm -q em vez de confiar so no rc do
#                        zypper) e _sha256_arquivo_local. Bugs reais
#                        corrigidos durante validacao em campo (VM
#                        192.168.56.167, 2026-07-16): padrao de busca do
#                        RPM userspace tambem casava com o nome do KMP
#                        (ambos comecam com "amibios-dmi-"), copiando/
#                        instalando o KMP em duplicidade -- corrigido para
#                        exigir digito logo apos o nome do pacote
#                        userspace; e shlex.quote aplicado no "~/arquivo"
#                        inteiro impedia a expansao do "~" pelo shell
#                        remoto (sha256sum/zypper procuravam um arquivo
#                        chamado literalmente "~/nome", sempre "ausente")
#                        -- corrigido para aspear so o nome do arquivo,
#                        deixando o "~/" fora das aspas.
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

import glob
import hashlib
import os
import shlex
import subprocess

from .constants import (
    SYSMODULE_PATH, SYSFS_IFACE_PATH, MARCADOR_KMP_KERNEL_INCOMPATIVEL,
)
from .logging_utils import gravar_log, gravar_log_remoto
from .ssh_utils import ssh_run, _filtra_banner, _scp_arquivo_com_erro


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
    RETURNS: str, versao no formato "X.Y.Z" ou "DESCONHECIDO"
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
    RETURNS: tuple(bool, str), (wsmt_presente, linha_dmesg_ou_vazio)
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
    RETURNS: str, MACs separados por virgula, ex: "aa:bb:cc:dd:ee:ff,11:22:33:44:55:66"
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
    RETURNS: str, MACs separados por virgula, ex: "aa:bb:cc:dd:ee:ff (eth0)"
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
    RETURNS: dict, dicionario com os dados coletados
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
    RETURNS: dict, dicionario com os dados coletados
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

    # SMBIOS version, cascata de 3 tentativas para compatibilidade
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
            # Tentativa 3: sysfs, /sys/firmware/dmi/tables/DMI nao e legivel
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

    # Asset tag atual, cascata de 2 tentativas:
    #   1. dmidecode -s chassis-asset-tag com sudo (precisa de privilegio,
    #      funciona em todos os modelos com dmidecode moderno)
    #   2. /sys/class/dmi/id/chassis_asset_tag via sysfs (sem sudo,
    #      funciona em equipamentos Legacy BIOS sem suporte a dmidecode
    #      moderno, ex: Gigabyte H81M, PERTOSA GA-H81M)
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


def verifica_pacote_rpm_remoto(ip, ssh_user, sudo_cmd, nome_pacote,
                                caminho_log, verbose, suprime_tela,
                                caminho_log_local=""):
    """
    NAME: verifica_pacote_rpm_remoto
    DESCRIPTION: Verifica, via SSH, se um pacote RPM esta instalado no
                 host remoto (rpm -q). Loga o NVR (nome-versao-release)
                 completo quando instalado, para permitir conferencia
                 manual de que o pacote e de fato o build esperado (o
                 nome do pacote sozinho nao garante que veio da mesma
                 origem/fork; ver rpm/README.md).
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               sudo_cmd          - prefixo sudo (nao usado, rpm -q nao
                                   exige privilegio; mantido por simetria
                                   com as demais funcoes remotas)
               nome_pacote       - nome do pacote RPM a verificar
               caminho_log       - log remoto
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: bool, True se instalado
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    rc, stdout, _ = ssh_run(
        ip, ssh_user,
        "rpm -q --qf '%{{NAME}}-%{{VERSION}}-%{{RELEASE}}' {} 2>/dev/null".format(
            nome_pacote),
        timeout=10)
    nvr = _filtra_banner(stdout).strip()
    if rc == 0 and nvr:
        _log("DEBUG", "Pacote RPM instalado no alvo: {}".format(nvr))
        return True
    _log("DEBUG", "Pacote RPM ausente no alvo: {}".format(nome_pacote))
    return False


def _sha256_arquivo_local(caminho):
    """
    NAME: _sha256_arquivo_local
    DESCRIPTION: Calcula o SHA-256 de um arquivo local, em blocos (nao
                 carrega o arquivo inteiro na memoria).
    PARAMETER: caminho - caminho do arquivo local
    RETURNS: str, hash SHA-256 em hexadecimal
    """
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def instala_modulo_remoto(ip, ssh_user, sudo_cmd, rpm_dir, module_package,
                           userspace_package, caminho_log, verbose,
                           suprime_tela, caminho_log_local=""):
    """
    NAME: instala_modulo_remoto
    DESCRIPTION: Copia via scp e instala via zypper local os RPMs do KMP
                 amibios_dmi (fork mariosergiosl/amibios_dmi, GPLv2, nao
                 e NDA) num host remoto, quando o pacote ainda nao
                 estiver instalado. Localiza os arquivos em rpm_dir por
                 padrao de nome (a versao/git-date/kernel-alvo mudam a
                 cada build, ver rpm/README.md), copia para o home do
                 usuario SSH (scp nao precisa de sudo) e instala com
                 'zypper install <caminho-local>' (sudo), que resolve
                 dependencias pelo mirror ja configurado no host. Confere
                 a instalacao no final via verifica_pacote_rpm_remoto
                 (nao confia apenas no codigo de retorno do zypper).
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               sudo_cmd          - prefixo sudo no host remoto
               rpm_dir           - diretorio local com os .rpm (ver
                                   DEFAULT_MODULE_RPM_DIR)
               module_package    - nome do pacote KMP (ex.:
                                   amibios-dmi-kmp-default)
               userspace_package - nome do pacote userspace complementar
                                   (ex.: amibios-dmi)
               caminho_log       - log remoto
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: tuple(bool, str), (sucesso, detalhe). sucesso e True somente
             se o pacote KMP foi confirmado instalado ao final (via rpm -q
             no alvo). detalhe fica vazio no sucesso ou falha generica; se
             a causa foi falta de KMP compilado para o kernel exato do
             host, detalhe comeca com constants.MARCADOR_KMP_KERNEL_
             INCOMPATIVEL (ver constants.eh_kmp_incompativel_com_kernel),
             usado por write_cascade.py para nao escalar ao Mecanismo 3.
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    # Padrao do userspace usa "-[0-9]*.rpm" (nao "-*.rpm") para nao
    # tambem casar com o nome do KMP -- ambos comecam com "amibios-dmi-",
    # e "amibios-dmi-kmp-default-1.0.0...rpm" bateria com um padrao
    # generico "amibios-dmi-*.rpm", copiando/instalando o KMP em
    # duplicidade (constatado em teste real, VM 192.168.56.167).
    padrao_kmp = os.path.join(rpm_dir, "{}-*.rpm".format(module_package))
    padrao_userspace = os.path.join(rpm_dir, "{}-[0-9]*.rpm".format(userspace_package))
    candidatos_kmp = sorted(glob.glob(padrao_kmp))
    candidatos_userspace = sorted(glob.glob(padrao_userspace))

    if not candidatos_kmp:
        detalhe = (
            "{}: nenhum RPM do modulo encontrado em '{}' (padrao: "
            "{}-*.rpm).".format(MARCADOR_KMP_KERNEL_INCOMPATIVEL,
                                 rpm_dir, module_package))
        _log("ERROR", detalhe)
        return False, detalhe

    # A pasta agora pode conter um KMP por SP (SP5/SP6/SP7, ver
    # rpm/README.md e o projeto OBS home:mariosergiosl:amibios_dmi). O
    # KMP so carrega no kernel exato para o qual foi compilado, entao
    # nao da para so pegar "o ultimo em ordem alfabetica" (bug real:
    # com varios candidatos na pasta, isso escolhia o KMP errado
    # independente do kernel do host). Casa o kernel real do alvo
    # (osrelease) contra o nome de cada arquivo antes de escolher.
    rc_kernel, stdout_kernel, _ = ssh_run(
        ip, ssh_user, "cat /proc/sys/kernel/osrelease", timeout=10)
    kernel_alvo = stdout_kernel.strip()
    if rc_kernel != 0 or not kernel_alvo:
        detalhe = ("Nao foi possivel ler o kernel do host remoto "
                    "(/proc/sys/kernel/osrelease) para escolher o KMP "
                    "correto.")
        _log("ERROR", detalhe)
        return False, detalhe

    # BUG REAL corrigido em 2026-07-20: osrelease vem no formato
    # "<versao>-<build>-<flavor>" (ex.: "5.3.18-22-default"), mas o nome
    # do arquivo e "amibios-dmi-kmp-<flavor>-<versao>-<build>.rpm" (o
    # flavor vem ANTES da versao no nome, depois no osrelease). A
    # comparacao por substring direta (kernel_alvo in nome_arquivo) nunca
    # batia com nenhum candidato real, fazendo TODO host cair em
    # KMP-KERNEL-MISMATCH mesmo com o RPM certo presente na pasta
    # (regressao total da instalacao automatica do KMP). O flavor
    # ("default", unico usado neste projeto, ver amibios-dmi.spec) e
    # removido do fim do osrelease antes de comparar.
    kernel_base = kernel_alvo
    if kernel_base.endswith("-default"):
        kernel_base = kernel_base[:-len("-default")]

    # Comparacao por IGUALDADE do nome completo do arquivo, nao por
    # substring: "in" permitiria colisao de prefixo (ex.: kernel_base
    # "5.3.18-22" seria substring tanto de "...-5.3.18-22.rpm" quanto de
    # um hipotetico "...-5.3.18-220.rpm"). O padrao de nome deste
    # projeto e sempre exatamente "<module_package>-<kernel>.rpm" (ver
    # rpm/README.md), entao a igualdade exata e sempre o suficiente e
    # elimina essa classe de bug.
    nome_esperado = "{}-{}.rpm".format(module_package, kernel_base)
    candidatos_compat = [c for c in candidatos_kmp
                         if os.path.basename(c) == nome_esperado]
    if not candidatos_compat:
        detalhe = (
            "{}: host roda o kernel '{}', mas nenhum RPM em '{}' foi "
            "compilado para esse kernel (candidatos disponiveis: {}). "
            "Gere um novo build no projeto OBS "
            "home:mariosergiosl:amibios_dmi (repos SP5/SP6/SP7) para esse "
            "kernel e adicione o .rpm resultante a pasta, mantendo o "
            "padrao de nome '{}-<kernel>.rpm'.".format(
                MARCADOR_KMP_KERNEL_INCOMPATIVEL, kernel_alvo, rpm_dir,
                ", ".join(os.path.basename(c) for c in candidatos_kmp),
                module_package))
        _log("ERROR", detalhe)
        return False, detalhe

    caminho_kmp_local = candidatos_compat[-1]
    arquivos_para_copiar = [caminho_kmp_local]
    if candidatos_userspace:
        arquivos_para_copiar.append(candidatos_userspace[-1])
    else:
        _log("DEBUG",
             "RPM userspace ({}-*.rpm) nao encontrado em '{}'; "
             "seguindo so com o KMP.".format(userspace_package, rpm_dir))

    def _limpa_rpms_copiados():
        """Remove do home do usuario SSH os .rpm que copiamos (em qualquer
        desfecho, sucesso ou falha), para nao deixar arquivos orfaos
        acumulando entre execucoes. rm -f e seguro mesmo para arquivo que
        nao chegou a ser copiado. Melhor esforco: falha aqui nao aborta o
        fluxo, mas agora fica visivel no log (antes era descartada em
        silencio, dificultando saber por que RPMs orfaos se acumulavam
        num host que ficou instavel entre a instalacao e a limpeza)."""
        alvos = " ".join(
            "~/{}".format(shlex.quote(os.path.basename(c)))
            for c in arquivos_para_copiar)
        if alvos:
            rc_limpa, _, err_limpa = ssh_run(
                ip, ssh_user, "rm -f {}".format(alvos), timeout=15)
            if rc_limpa != 0:
                _log("WARNING",
                     "Falha ao limpar RPMs copiados ({}): {}. Arquivos podem "
                     "ter ficado orfaos no home do usuario SSH.".format(
                         alvos, (err_limpa or "").strip() or "sem detalhe"))

    caminhos_remotos = []
    nomes_arquivos = []
    for caminho_local in arquivos_para_copiar:
        nome_arquivo = os.path.basename(caminho_local)
        # "~/" fica FORA do shlex.quote de proposito: aspeado junto, o
        # shell remoto para de expandir o "~" e trata como nome literal
        # de arquivo (bug constatado em teste real, VM 192.168.56.167 --
        # sha256sum sempre retornava vazio). So o nome do arquivo (vindo
        # do nosso proprio glob local, mas aspeado por precaucao) e
        # aspeado; o "~/" continua expandindo normalmente no shell.
        caminho_remoto = "~/{}".format(nome_arquivo)
        caminho_remoto_shell = "~/{}".format(shlex.quote(nome_arquivo))
        _log("INFO", "Copiando {} para {}@{}:{}".format(
            nome_arquivo, ssh_user, ip, caminho_remoto))
        sucesso, erro = _scp_arquivo_com_erro(
            ip, ssh_user, caminho_local, caminho_remoto)
        if not sucesso:
            _log("ERROR", "Falha ao copiar {}: {}".format(nome_arquivo, erro))
            _limpa_rpms_copiados()
            return False, ""

        # Confere o SHA-256 remoto contra o arquivo local antes de instalar
        # como root -- garante que o zypper vai instalar exatamente os
        # bytes que saem daqui, nao uma copia corrompida na transferencia.
        sha_local = _sha256_arquivo_local(caminho_local)
        rc_sha, stdout_sha, _ = ssh_run(
            ip, ssh_user,
            "sha256sum {} 2>/dev/null | cut -d' ' -f1".format(
                caminho_remoto_shell),
            timeout=15)
        sha_remoto = stdout_sha.strip()
        if rc_sha != 0 or not sha_remoto or sha_remoto != sha_local:
            _log("ERROR",
                 "SHA-256 do arquivo copiado nao confere ({}): "
                 "local={} remoto={}. Abortando instalacao.".format(
                     nome_arquivo, sha_local, sha_remoto or "N/D"))
            _limpa_rpms_copiados()
            return False, ""

        # Guarda a forma ja "tilde-safe" (so o nome do arquivo aspeado,
        # "~/" fora das aspas) para reuso no comando de instalacao abaixo.
        caminhos_remotos.append(caminho_remoto_shell)
        nomes_arquivos.append(nome_arquivo)

    cmd_install = "{} zypper --non-interactive --no-gpg-checks install {}".format(
        sudo_cmd, " ".join(caminhos_remotos))
    _log("INFO", "Instalando via zypper local: {}".format(
        " ".join(nomes_arquivos)))
    rc, stdout, stderr = ssh_run(ip, ssh_user, cmd_install, timeout=120)
    if rc != 0:
        # A saida do zypper costuma vir em varias linhas (mensagem de
        # conflito, opcoes de resolucao, etc.); loga linha a linha, cada
        # uma com o prefixo padrao (timestamp/nivel/host), em vez de uma
        # unica chamada com string multi-linha -- isso deixava so a
        # primeira linha prefixada e o resto cru no arquivo, quebrando o
        # layout do log (mesma classe de problema ja corrigida no dump do
        # dmesg, ver bios_sysfs.py).
        saida_erro = _filtra_banner(stderr).strip() or _filtra_banner(stdout).strip()
        _log("ERROR", "zypper install falhou (rc={}):".format(rc))
        for linha_erro in saida_erro.splitlines():
            if linha_erro.strip():
                _log("ERROR", "  {}".format(linha_erro.strip()))
        _limpa_rpms_copiados()
        return False, ""

    instalado = verifica_pacote_rpm_remoto(
        ip, ssh_user, sudo_cmd, module_package,
        caminho_log, verbose, suprime_tela, caminho_log_local)
    if instalado:
        _log("INFO", "Pacote '{}' confirmado instalado no alvo.".format(
            module_package))
    else:
        _log("ERROR",
             "zypper install rodou sem erro, mas '{}' nao aparece instalado "
             "no alvo (rpm -q).".format(module_package))
    _limpa_rpms_copiados()
    return instalado, ""


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

