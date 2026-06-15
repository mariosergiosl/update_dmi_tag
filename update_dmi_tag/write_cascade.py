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
#              tenta_teste_escrita_remoto executa um rewrite no-op
#              (regrava o valor ja presente na BIOS) para validar a
#              capacidade de escrita de cada modelo sem alterar nada.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.1.4
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
# REVISION: 2026-06-15 - v2.1.4 - adiciona tenta_teste_escrita_remoto:
#                        cascata de mecanismos no modo rewrite no-op
#                        (regrava o valor atual da BIOS). Usado pela
#                        flag --test-write para validar compatibilidade
#                        de gravacao sem alterar nenhum dado. Pula hosts
#                        com tag virgem (Default String etc.) ou tag
#                        DESCONHECIDA. Retorna string descritiva:
#                        OK-amidelnx, OK-amibios, FALHOU-todos,
#                        TAG-VIRGEM ou TAG-DESCONH.
#
# =======================================================================

from .constants import MecanismoIndisponivelError, TodosMecanismosFalharam
from .logging_utils import gravar_log, gravar_log_remoto
from .bios_amidelnx import executa_amidelnx_local, executa_amidelnx_remoto
from .bios_sysfs import executa_amibios_local, executa_amibios_remoto


# Valores de tag que indicam placa sem tag gravada (virgem).
# O rewrite no-op nao e executado nesses casos pois regravar um
# placeholder nao valida a capacidade de escrita de tags reais.
_TAGS_VIRGEM = frozenset({
    "Default String",
    "Default string",
    "Not Specified",
    "Not Provided",
    "To Be Filled By O.E.M.",
    "To be filled by O.E.M.",
    "Asset-1234567890",
    "Chassis Asset Tag",
    "",
})


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


def tenta_teste_escrita_remoto(ip, ssh_user, sudo_cmd, tag_atual, args,
                                caminho_log_remoto, caminho_log_local):
    """
    NAME: tenta_teste_escrita_remoto
    DESCRIPTION: Executa um rewrite no-op (regrava o valor ja presente
                 na BIOS) para validar a capacidade de escrita do
                 equipamento sem alterar nenhum dado. Ativado pela flag
                 --test-write, independente de --write.

                 Fluxo:
                   1. Verifica se tag_atual e conhecida e nao virgem.
                      Se DESCONHECIDA -> retorna TAG-DESCONH (pulado).
                      Se virgem (Default String etc.) -> TAG-VIRGEM.
                   2. Tenta Mecanismo 1 (amidelnx_64) com tag_atual.
                      Sucesso -> retorna OK-amidelnx.
                   3. Tenta Mecanismo 2 (amibios_dmi sysfs).
                      Sucesso -> retorna OK-amibios.
                   4. Ambos falharam -> retorna FALHOU-todos.

                 Importante: esta funcao NUNCA executa em dry_run=True
                 (o objetivo e confirmar a escrita real). Por isso e
                 separada de tenta_escrever_tag_remoto e so e chamada
                 quando args.test_write=True, independente de args.write.
                 O BBconfig.conf NAO e atualizado por esta funcao.

    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               sudo_cmd          - prefixo sudo no host
               tag_atual         - valor atual lido da BIOS (para
                                   regravar identico)
               args              - namespace do argparse
               caminho_log_remoto - log remoto do host
               caminho_log_local  - log consolidado local
    RETURNS: str -- "OK-amidelnx", "OK-amibios", "FALHOU-todos",
             "TAG-VIRGEM" ou "TAG-DESCONH"
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel, msg, caminho_log_local, args.verbose, args.csv)

    # 1. Verifica se a tag atual e utilizavel como valor de teste
    if not tag_atual or tag_atual == "DESCONHECIDO":
        _log("WARNING",
             "[TEST-WRITE] Tag atual DESCONHECIDA -- teste de escrita pulado.")
        return "TAG-DESCONH"

    if tag_atual.strip() in _TAGS_VIRGEM:
        _log("WARNING",
             "[TEST-WRITE] Tag virgem ('{}') -- teste de escrita pulado "
             "(regravar placeholder nao valida compatibilidade).".format(tag_atual))
        return "TAG-VIRGEM"

    _log("INFO",
         "[TEST-WRITE] Iniciando rewrite no-op com tag atual: '{}'".format(tag_atual))

    # 2. Mecanismo 1: amidelnx_64 (dry_run=False -- escrita real no-op)
    _log("INFO", "[TEST-WRITE] --- Mecanismo 1: amidelnx_64 ---")
    try:
        sucesso = executa_amidelnx_remoto(
            ip, ssh_user, sudo_cmd, tag_atual,
            args.amide_remote_path, args.amide_local_path,
            caminho_log_remoto, caminho_log_local,
            args.verbose, args.csv, dry_run=False,
            amide_repo_url=args.amide_repo_url,
            amide_package=args.amide_package,
        )
        if sucesso:
            _log("INFO",
                 "[TEST-WRITE] Mecanismo 1 OK -- modelo compativel com amidelnx_64.")
            return "OK-amidelnx"
        _log("WARNING",
             "[TEST-WRITE] Mecanismo 1 falhou; tentando Mecanismo 2.")
    except MecanismoIndisponivelError as e:
        _log("WARNING",
             "[TEST-WRITE] Mecanismo 1 indisponivel: {}".format(e))

    # 3. Mecanismo 2: amibios_dmi via sysfs (dry_run=False)
    _log("INFO", "[TEST-WRITE] --- Mecanismo 2: amibios_dmi (sysfs) ---")
    try:
        sucesso = executa_amibios_remoto(
            ip, ssh_user, sudo_cmd, tag_atual,
            args.target, caminho_log_remoto, caminho_log_local,
            args.verbose, args.csv, dry_run=False,
            module_repo_url=args.module_repo_url,
            module_package=args.module_package,
        )
        if sucesso:
            _log("INFO",
                 "[TEST-WRITE] Mecanismo 2 OK -- modelo compativel via amibios_dmi.")
            return "OK-amibios"
        _log("ERROR", "[TEST-WRITE] Mecanismo 2 tambem falhou.")
    except MecanismoIndisponivelError as e:
        _log("ERROR",
             "[TEST-WRITE] Mecanismo 2 indisponivel: {}".format(e))

    _log("ERROR",
         "[TEST-WRITE] Ambos os mecanismos falharam -- modelo incompativel "
         "ou binario ausente.")
    return "FALHOU-todos"

