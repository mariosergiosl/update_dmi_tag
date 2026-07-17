#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: efi_write.py
#
# USAGE: tools/efi_write.py --hosts <arquivo> [opcoes]
#        tools/efi_write.py --ip <IP> --tag <14 digitos> [opcoes]
#
# DESCRIPTION: Script standalone para o Mecanismo 3 (boot EFI temporario,
#              experimental, ver update_dmi_tag/boot_efi.py). Reaproveita
#              o mesmo modulo usado pela integracao no update_dmi_tag.py
#              (--allow-efi-fallback), mas roda isolado: pensado para
#              reprocessar so os hosts onde os Mecanismos 1 e 2 ja
#              falharam numa execucao anterior do update_dmi_tag.py com
#              -w, sem precisar repetir toda a auditoria/cascata.
#
#              NAO decide sozinho se os mecanismos diretos falharam --
#              isso e responsabilidade do operador confirmar antes (via
#              o resultado FALHOU-todos na tabela de resumo do
#              update_dmi_tag.py). Este script vai direto para a
#              checagem de seguranca + Mecanismo 3.
#
#              Fluxo por host:
#                1. Testa conectividade e bootstrap de chave SSH
#                   (reaproveita ssh_bootstrap/ssh_utils do pacote).
#                2. Detecta sudo.
#                3. Resolve a tag: --tag explicito (modo --ip unico) ou
#                   le o BEM_NUMERO do BBconfig.conf remoto (modo --hosts,
#                   igual ao update_dmi_tag.py).
#                4. Chama boot_efi.executa_boot_efi_remoto.
#
#              Exige confirmacao interativa antes de iniciar (mesma
#              exigencia de --allow-efi-fallback no script principal) --
#              este script sempre reboota fisicamente os hosts que
#              passarem na checagem de seguranca, nao tem modo dry-run.
#
# REQUIREMENTS: python3 (stdlib apenas), pacote update_dmi_tag/ acessivel
#               (este arquivo assume que fica em tools/, um nivel abaixo
#               da raiz do projeto onde update_dmi_tag/ mora).
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.2.5
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
# CREATED: 2026-07-08
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
# REVISION: 2026-07-08 - v2.1.11 - criacao do script (Mecanismo 3
#                        standalone, experimental). Ainda nao validado em
#                        hardware real.
#
# =======================================================================

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from update_dmi_tag.constants import (
    DEFAULT_SSH_USER, DEFAULT_CONFIG_FILE, DEFAULT_VAR_NAME, DEFAULT_LOG_FILE,
    DEFAULT_EFI_LOCAL_DIR, DEFAULT_EFI_REBOOT_TIMEOUT, DEFAULT_EFI_LOG_FILE,
    RC_FILE_NOT_FOUND, RC_SAFETY_ABORT, RC_VALIDATION_ERROR,
)
from update_dmi_tag.logging_utils import gravar_log
from update_dmi_tag.ssh_utils import testa_porta_ssh, testa_conexao_ssh, detecta_sudo
from update_dmi_tag.ssh_bootstrap import prepara_autenticacao_ssh, _resolve_ssh_pass
from update_dmi_tag.hosts import le_arquivo_hosts
from update_dmi_tag.bbconfig import le_valor_configuracao_remoto
from update_dmi_tag.patrimonio import valida_e_calcula_tag
from update_dmi_tag.boot_efi import executa_boot_efi_remoto


def _log_local(caminho_log_local, verbose, nivel, msg):
    gravar_log(caminho_log_local, nivel, msg, verbose, False)


def _processa_host(ip, bem_lista, args, tag_explicita=""):
    """
    NAME: _processa_host
    DESCRIPTION: Prepara o acesso ao host (conectividade, chave SSH,
                 sudo) e resolve a tag a ser gravada, depois delega para
                 boot_efi.executa_boot_efi_remoto. Nao tenta os
                 Mecanismos 1 e 2, pressupoe que ja falharam numa
                 execucao anterior do update_dmi_tag.py.
    PARAMETER: ip              - endereco IP do host
               bem_lista        - BEM_NUMERO da lista de hosts (pode ser vazio)
               args             - namespace do argparse
               tag_explicita    - tag de 14 digitos ja calculada (modo --ip)
    RETURNS: str, resultado (ver boot_efi.executa_boot_efi_remoto)
    """
    caminho_log_local = args.log_local

    def _log(nivel, msg):
        _log_local(caminho_log_local, args.verbose, nivel, "[{}] {}".format(ip, msg))

    _log("INFO", "====== Iniciando Mecanismo 3 standalone: {} ======".format(ip))

    if not testa_porta_ssh(ip, timeout=2.0):
        _log("ERROR", "Host offline ou porta SSH (TCP 22) fechada. Pulado.")
        return "INACESSIVEL"

    if not prepara_autenticacao_ssh(
        ip, args.ssh_user, getattr(args, "ssh_pass_efetiva", ""),
        caminho_log_local, args.verbose,
    ):
        _log("ERROR", "Bootstrap de autenticacao SSH falhou. Pulado.")
        return "INACESSIVEL"

    sudo_cmd, sudo_confirmado = detecta_sudo(ip, args.ssh_user, args.sudo_pass)
    if not sudo_confirmado:
        _log("ERROR", "Sudo nao confirmado no host. Pulado (Mecanismo 3 exige privilegio).")
        return "SEM-SUDO"

    if tag_explicita:
        tag = tag_explicita
    else:
        valor_config = le_valor_configuracao_remoto(
            ip, args.ssh_user, args.config, args.var,
            DEFAULT_LOG_FILE, caminho_log_local, args.verbose, False, sudo_cmd=sudo_cmd)
        valor_usado = bem_lista.strip() if bem_lista and bem_lista.strip() else valor_config
        if not valor_usado:
            _log("ERROR", "BEM_NUMERO ausente (lista de hosts e BBconfig.conf remoto vazios). Pulado.")
            return "PENDENTE"
        try:
            tag, _base13 = valida_e_calcula_tag(valor_usado, "", args.verbose, False,
                                                caminho_log_local=caminho_log_local)
        except ValueError as e:
            _log("ERROR", "BEM_NUMERO invalido: {}".format(e))
            return "INVALIDO"

    resultado = executa_boot_efi_remoto(
        ip, args.ssh_user, sudo_cmd, tag, args,
        caminho_log_remoto=DEFAULT_LOG_FILE,
        caminho_log_local=caminho_log_local,
        caminho_log_efi=args.log_efi,
    )
    _log("INFO", "====== Fim (Mecanismo 3 standalone): {} -- {} ======".format(ip, resultado))
    return resultado


def main():
    parser = argparse.ArgumentParser(
        prog="efi_write.py",
        description=(
            "Mecanismo 3 standalone (boot EFI temporario, EXPERIMENTAL). "
            "Reprocessa hosts onde os Mecanismos 1 e 2 do update_dmi_tag.py "
            "ja falharam numa gravacao real (-w). Sempre reboota fisicamente "
            "os hosts que passarem na checagem de seguranca, sem modo dry-run."
        ),
    )
    parser.add_argument("--hosts", default="", metavar="ARQUIVO",
                        help="Arquivo de hosts (IP ou IP,BEM_NUMERO por linha).")
    parser.add_argument("--ip", default="", metavar="IP",
                        help="Um unico host (alternativa a --hosts). Exige --tag.")
    parser.add_argument("--tag", default="", metavar="TAG14",
                        help="Tag de 14 digitos a gravar (obrigatorio com --ip).")
    parser.add_argument("--ssh-user", default=DEFAULT_SSH_USER, dest="ssh_user")
    parser.add_argument("--ssh-pass", default="", dest="ssh_pass", metavar="SENHA")
    parser.add_argument("--ssh-pass-file", default="", dest="ssh_pass_file", metavar="ARQUIVO")
    parser.add_argument("--sudo-pass", default="", dest="sudo_pass", metavar="SENHA")
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("-s", "--var", default=DEFAULT_VAR_NAME)
    parser.add_argument("--efi-local-dir", default=DEFAULT_EFI_LOCAL_DIR, dest="efi_local_dir")
    parser.add_argument("--efi-timeout", type=int, default=DEFAULT_EFI_REBOOT_TIMEOUT, dest="efi_timeout")
    parser.add_argument("--log-local", default="./efi_write.log", dest="log_local")
    parser.add_argument("--log-efi", default=DEFAULT_EFI_LOG_FILE, dest="log_efi")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if not args.hosts and not args.ip:
        sys.stderr.write("Erro: informe --hosts <arquivo> ou --ip <IP> --tag <14 digitos>.\n")
        sys.exit(RC_VALIDATION_ERROR)
    if args.ip and not args.tag:
        sys.stderr.write("Erro: --ip exige --tag (14 digitos).\n")
        sys.exit(RC_VALIDATION_ERROR)
    if args.hosts and not os.path.isfile(args.hosts):
        sys.stderr.write("Erro: arquivo de hosts nao encontrado: {}\n".format(args.hosts))
        sys.exit(RC_FILE_NOT_FOUND)

    amide_efi = os.path.join(args.efi_local_dir, "AMIDEEFIx64.EFI")
    shell_efi = os.path.join(args.efi_local_dir, "bootx64.efi")
    if not os.path.isfile(amide_efi) or not os.path.isfile(shell_efi):
        sys.stderr.write(
            "Erro: AMIDEEFIx64.EFI e bootx64.efi nao encontrados em '{}'.\n".format(
                args.efi_local_dir))
        sys.exit(RC_FILE_NOT_FOUND)

    args.ssh_pass_efetiva = _resolve_ssh_pass(args)
    # boot_efi.py (compartilhado com o fluxo principal) espera args.csv
    # (usado so como "suprime_tela" nos logs); este script nao tem modo CSV.
    args.csv = False
    # allow_efi_fallback nao existe neste script (o gate ja e o proprio ato
    # de rodar o efi_write.py), mas boot_efi.py so usa esse atributo dentro
    # de write_cascade.py, aqui chamamos executa_boot_efi_remoto direto.

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.stderr.write(
            "Erro: efi_write.py exige confirmacao interativa (sempre reinicia "
            "fisicamente os hosts elegiveis) e nao ha terminal disponivel.\n")
        sys.exit(RC_SAFETY_ABORT)

    alvo_desc = args.ip if args.ip else "hosts em {}".format(args.hosts)
    sys.stderr.write(
        "AVISO: este script vai REINICIAR fisicamente os hosts ({}) que "
        "passarem na checagem de seguranca do Mecanismo 3. "
        "Isso vai reiniciar as maquinas da lista. Voce tem certeza? [s/N]: ".format(alvo_desc))
    resposta = input().strip().lower()
    if resposta not in ("s", "sim", "y", "yes"):
        sys.stderr.write("Execucao cancelada.\n")
        sys.exit(RC_SAFETY_ABORT)

    _log_local(args.log_local, args.verbose, "INFO", "=" * 70)
    _log_local(args.log_local, args.verbose, "INFO",
              "efi_write.py, Mecanismo 3 standalone (EXPERIMENTAL). Inicio: {}".format(
                  time.strftime("%Y-%m-%d %H:%M:%S")))
    _log_local(args.log_local, args.verbose, "INFO", "=" * 70)

    resultados = {}
    if args.ip:
        resultados[args.ip] = _processa_host(args.ip, "", args, tag_explicita=args.tag)
    else:
        for ip, bem in le_arquivo_hosts(args.hosts):
            resultados[ip] = _processa_host(ip, bem, args)

    _log_local(args.log_local, args.verbose, "INFO", "=" * 70)
    _log_local(args.log_local, args.verbose, "INFO", "RESUMO:")
    for ip, resultado in resultados.items():
        _log_local(args.log_local, args.verbose, "INFO", "  {}, {}".format(ip, resultado))
    _log_local(args.log_local, args.verbose, "INFO", "=" * 70)

    falhas = sum(1 for r in resultados.values() if not str(r).startswith("OK"))
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
