# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: write_cascade.py
#
# DESCRIPTION: Orquestra a cascata de mecanismos de gravacao do DMI
#              Asset Tag: tenta Mecanismo 1 (amidelnx_64), e em falha
#              ou indisponibilidade cai para o Mecanismo 2 (amibios_dmi
#              via sysfs). tenta_escrever_tag_local e usada no modo
#              standalone; tenta_escrever_tag_remoto no modo remoto.
#              Ambas retornam uma string descritiva: "OK-amidelnx",
#              "OK-amibios", "DRY-RUN" ou "FALHOU-todos".
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

from .constants import MecanismoIndisponivelError, TodosMecanismosFalharam
from .logging_utils import gravar_log, gravar_log_remoto
from .bios_amidelnx import executa_amidelnx_local, executa_amidelnx_remoto
from .bios_sysfs import executa_amibios_local, executa_amibios_remoto


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


