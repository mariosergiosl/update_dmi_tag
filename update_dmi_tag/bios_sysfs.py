# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: bios_sysfs.py
#
# DESCRIPTION: Mecanismo 2 de gravacao do DMI Asset Tag (fallback):
#              modulo de kernel amibios_dmi via sysfs
#              (/sys/firmware/amibios/chassis/asset_tag).
#              _carrega_modulo_amibios / _descarrega_modulo_amibios
#              fazem o auto-load/auto-unload do modulo (finally
#              obrigatorio para preservar o estado do sistema).
#              executa_amibios_local roda no proprio equipamento.
#              executa_amibios_remoto roda via SSH. Em placas com WSMT
#              presente, este mecanismo falha com SMI error 0x84 e o
#              script usa o Mecanismo 1 (amidelnx_64) automaticamente.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE
# VERSION: 2.2.4
# REVISION: 2026-07-16 - v2.2.4 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.3 - executa_amibios_remoto passa a instalar
#                        o KMP amibios_dmi automaticamente (via
#                        instala_modulo_remoto, environment.py) quando
#                        ausente no alvo, antes de tentar o modprobe; loga
#                        as ultimas linhas do dmesg quando a interface SMI
#                        nao aparece apos o modprobe, para diagnostico.
#                        Corrige BUG REAL pre-existente: a checagem de
#                        "interface pronta" usava o rc de um comando
#                        composto "test -d X && echo ready || echo
#                        absent", que e sempre 0 (o "echo absent" do ramo
#                        else tambem retorna 0) -- fazia iface_pronta
#                        ficar sempre True, pulando por completo a
#                        instalacao automatica do modulo em TODAS as
#                        execucoes anteriores, em qualquer host (bug
#                        constatado em teste real, VM 192.168.56.167,
#                        2026-07-16, com o modulo deliberadamente
#                        ausente). Corrige tambem a mensagem de erro do
#                        modprobe, que era descartada silenciosamente
#                        (comando usa "2>&1", mas so o stderr vazio era
#                        capturado; agora le do stdout mesclado).
# REVISION: 2026-07-16 - v2.2.2 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.1 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-14 - v2.2.0 - executa_amibios_local/remoto passam a
#                        retornar tupla (sucesso, detalhe) em vez de bool
#                        (ver bios_amidelnx.py). Corrige tambem um crash
#                        nao tratado (OSError) na escrita local do sysfs,
#                        que antes propagava sem captura ate o chamador.
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
import subprocess

from .constants import (
    MecanismoIndisponivelError, SYSMODULE_PATH, SYSFS_IFACE_PATH,
    DEFAULT_MODULE_USERSPACE_PACKAGE,
)
from .logging_utils import gravar_log, gravar_log_remoto
from .ssh_utils import ssh_run
from .environment import (
    modulo_esta_carregado, interface_esta_pronta, instala_modulo_via_zypper,
    loga_versao_modulo, verifica_pacote_rpm_remoto, instala_modulo_remoto,
)


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
    RETURNS: bool, True se interface sysfs esta pronta
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
    RETURNS: tuple(bool, str), (sucesso, detalhe) -- ver
             bios_amidelnx.executa_amidelnx_local para o motivo desta
             mudanca de assinatura.
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
            return True, "valor ja atualizado (sem gravacao SMI)"

        if dry_run:
            _log("WARNING",
                 "[DRY-RUN] amibios_dmi: valor que seria gravado: '{}'".format(tag))
            _log("WARNING",
                 "[DRY-RUN] Para gravar, passe a flag -w ou --write.")
            return False, "DRY-RUN"

        # Gravacao fisica no sysfs
        _log("INFO", "Mecanismo 2: gravando via sysfs amibios_dmi: {}".format(tag))

        if not os.path.exists(sysfs_target):
            raise FileNotFoundError(
                "Caminho sysfs de escrita nao encontrado: {}".format(sysfs_target))
        if not os.access(sysfs_target, os.W_OK):
            raise PermissionError(
                "Sem permissao de escrita no sysfs: {}".format(sysfs_target))

        try:
            with open(sysfs_target, "w") as f:
                f.write(tag)
        except OSError as e:
            detalhe = "sysfs rejeitou a escrita: {}".format(e)
            _log("ERROR", "amibios_dmi: falha na escrita ({}).".format(detalhe))
            return False, detalhe
        _log("INFO", "Operacao de escrita concluida.")

        # Auditoria pos-escrita
        try:
            with open(sysfs_target, "r") as f:
                valor_novo = f.read().strip()
            _log("INFO", "Valor auditado pos-escrita: '{}'".format(valor_novo))
        except Exception as e:
            _log("ERROR", "Falha na leitura de auditoria pos-escrita: {}".format(e))
            return False, "falha na leitura de auditoria pos-escrita: {}".format(e)

        if valor_novo == tag:
            _log("INFO", "amibios_dmi: gravacao confirmada e auditada.")
            return True, "gravacao confirmada e auditada"

        detalhe = "integridade falhou, esperado '{}', lido '{}'".format(tag, valor_novo)
        _log("ERROR", "amibios_dmi: {}".format(detalhe))
        return False, detalhe

    finally:
        # Unload garantido se o modulo foi carregado temporariamente
        if modulo_carregado_pelo_script:
            _descarrega_modulo_amibios(caminho_log, verbose, suprime_tela,
                                       caminho_log_local)


def executa_amibios_remoto(ip, ssh_user, sudo_cmd, tag, sysfs_target,
                            caminho_log, caminho_log_local,
                            verbose, suprime_tela, dry_run=True,
                            module_repo_url="", module_package="",
                            module_rpm_dir=""):
    """
    NAME: executa_amibios_remoto
    DESCRIPTION: Executa o mecanismo amibios_dmi em um host remoto via SSH.
                 Verifica se a interface sysfs esta disponivel; se o
                 modulo nao estiver presente, confere se o RPM ja esta
                 instalado (rpm -q) e, senao, copia os RPMs de
                 module_rpm_dir via scp e instala via zypper local
                 (instala_modulo_remoto). So entao tenta o modprobe. Le
                 o valor antigo, grava e audita pos-escrita. Em dry_run,
                 apenas loga. Levanta MecanismoIndisponivelError se a
                 interface nao ficar disponivel, com diagnostico (dmesg)
                 anexado ao erro para investigacao.
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
               module_repo_url   - repo zypper (via --plus-repo, alternativa
                                   mais antiga a module_rpm_dir)
               module_package    - nome do pacote KMP
               module_rpm_dir    - diretorio local com os RPMs do KMP
                                   (scp + zypper install local; ver
                                   DEFAULT_MODULE_RPM_DIR)
    RETURNS: tuple(bool, str), (sucesso, detalhe) -- ver
             executa_amibios_local.
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    def _ssh(cmd, timeout=10):
        rc, stdout, stderr = ssh_run(ip, ssh_user, cmd, timeout=timeout)
        return rc, stdout, stderr

    modulo_carregado_pelo_script = False

    try:
        # Verifica se a interface sysfs esta disponivel no alvo. O rc do
        # comando composto abaixo e sempre 0 (o "echo absent" do ramo else
        # tambem retorna 0), entao a checagem tem que ser pelo conteudo do
        # stdout, nao pelo rc -- mesma classe de bug de precedencia de
        # shell (&&/|| sem parenteses) ja corrigida em boot_efi.py; aqui
        # o bug fazia iface_pronta ficar sempre True, pulando por completo
        # a instalacao automatica do modulo (constatado em teste real na
        # VM 192.168.56.167, 2026-07-16, com o modulo deliberadamente
        # ausente).
        _, stdout_iface, _ = _ssh(
            "test -d {} && echo ready || echo absent".format(SYSFS_IFACE_PATH))
        iface_pronta = (stdout_iface.strip() == "ready")

        if not iface_pronta:
            # Verifica se o modulo esta carregado
            rc_mod, stdout_mod, _ = _ssh(
                "test -d {} && echo loaded || echo absent".format(SYSMODULE_PATH))
            modulo_presente = (stdout_mod.strip() == "loaded")

            if not modulo_presente:
                _log("WARNING", "Modulo amibios_dmi ausente no alvo.")

                pacote_ja_instalado = verifica_pacote_rpm_remoto(
                    ip, ssh_user, sudo_cmd, module_package,
                    caminho_log, verbose, suprime_tela, caminho_log_local)

                if not pacote_ja_instalado:
                    if module_rpm_dir:
                        _log("INFO",
                             "Pacote '{}' nao instalado; tentando instalar via "
                             "RPM local ({})...".format(module_package, module_rpm_dir))
                        pacote_ja_instalado = instala_modulo_remoto(
                            ip, ssh_user, sudo_cmd, module_rpm_dir, module_package,
                            DEFAULT_MODULE_USERSPACE_PACKAGE,
                            caminho_log, verbose, suprime_tela, caminho_log_local)
                    else:
                        _log("WARNING",
                             "module_rpm_dir nao configurado; nao ha como "
                             "instalar '{}' automaticamente.".format(module_package))

                _log("INFO", "Tentando modprobe remoto...")
                # "2>&1" mistura stderr no stdout do proprio comando remoto;
                # por isso a mensagem de erro do modprobe sai em stdout_mp,
                # nao em stderr_mp (que fica sempre vazio aqui e mascarava
                # o motivo real da falha, ex.: "Invalid module format",
                # constatado em teste real na VM 192.168.56.167).
                rc_mp, stdout_mp, stderr_mp = _ssh(
                    "{} modprobe amibios_dmi 2>&1".format(sudo_cmd), timeout=15)
                detalhe_modprobe = stdout_mp.strip() or stderr_mp.strip()

                # Verifica interface apos modprobe
                rc_check, stdout_check, _ = _ssh(
                    "test -d {} && echo ready || echo absent".format(SYSFS_IFACE_PATH))
                if stdout_check.strip() == "ready":
                    modulo_carregado_pelo_script = True
                    _log("INFO", "Modulo amibios_dmi carregado via modprobe remoto.")
                    iface_pronta = True
                else:
                    # Diagnostico: dmesg ajuda a distinguir "modulo nao
                    # carregou" (insmod falhou) de "modulo carregou mas o
                    # handshake SMI falhou" (ex.: SMI error 0x84 no INFO,
                    # ver amibios_smi.c do fork), constatado em campo
                    # (10.24.80.96, 2026-07-16): insmod pode retornar rc=0
                    # sem a interface aparecer.
                    _, dmesg_out, _ = _ssh(
                        "dmesg 2>/dev/null | tail -15", timeout=10)
                    _log("ERROR",
                         "Interface sysfs indisponivel apos modprobe: {}".format(
                             detalhe_modprobe or "sem mensagem de erro"))
                    if dmesg_out.strip():
                        _log("ERROR", "dmesg (ultimas linhas) apos modprobe:")
                        for linha in dmesg_out.strip().splitlines():
                            _log("ERROR", "  {}".format(linha.strip()))

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
            return True, "valor ja atualizado (sem gravacao SMI)"

        if dry_run:
            _log("WARNING",
                 "[DRY-RUN] amibios_dmi remoto: valor que seria gravado: '{}'".format(tag))
            _log("WARNING",
                 "[DRY-RUN] Para gravar, passe a flag -w ou --write.")
            return False, "DRY-RUN"

        # Gravacao fisica via SSH
        _log("INFO",
             "Mecanismo 2: gravando via sysfs amibios_dmi remoto: {}".format(tag))

        cmd_write = (
            "test -w {sysfs} && echo '{tag}' | {sudo} tee {sysfs} > /dev/null"
            " || echo WRITE_ERROR"
        ).format(sysfs=sysfs_target, tag=tag, sudo=sudo_cmd)

        rc_w, stdout_w, stderr_w = _ssh(cmd_write, timeout=15)
        if "WRITE_ERROR" in stdout_w or rc_w != 0:
            # stderr costuma vir vazio (sysfs rejeita a escrita sem
            # mensagem), entao evita "falha na escrita, " com virgula
            # solta e sempre inclui o rc como detalhe util.
            detalhe = stderr_w.strip()
            if not detalhe:
                detalhe = "rc={}, sysfs rejeitou a escrita sem mensagem".format(rc_w)
            _log("ERROR",
                 "amibios_dmi remoto: falha na escrita ({}).".format(detalhe))
            return False, detalhe

        _log("INFO", "Operacao de escrita remota concluida.")

        # Auditoria pos-escrita
        rc_audit, valor_novo, _ = _ssh(
            "cat {} 2>/dev/null || echo AUDIT_FAILED".format(sysfs_target))
        valor_novo = valor_novo.strip()
        _log("INFO", "Valor auditado pos-escrita: '{}'".format(valor_novo))

        if valor_novo == tag:
            _log("INFO", "amibios_dmi remoto: gravacao confirmada e auditada.")
            return True, "gravacao confirmada e auditada"

        detalhe = "integridade falhou, esperado '{}', lido '{}'".format(tag, valor_novo)
        _log("ERROR", "amibios_dmi remoto: {}".format(detalhe))
        return False, detalhe

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

