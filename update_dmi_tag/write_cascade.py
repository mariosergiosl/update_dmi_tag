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
# VERSION: 2.1.8
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
# REVISION: 2026-06-15 - v2.1.4 - adiciona tenta_teste_escrita_remoto.
# REVISION: 2026-06-16 - v2.1.8 - TAG-VIRGEM no test-write: em vez de
#                        pular, usa bem_usado (se disponivel) ou "O.E.M."
#                        como valor de teste, grava, verifica e restaura
#                        o valor virgem original. Refatorado em funcao
#                        interna _executa_cascata para evitar duplicacao.
#                        Assinatura de tenta_teste_escrita_remoto recebe
#                        bem_usado como parametro opcional.
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
                                caminho_log_remoto, caminho_log_local,
                                bem_usado=""):
    """
    NAME: tenta_teste_escrita_remoto
    DESCRIPTION: Executa um rewrite no-op para validar a capacidade de
                 escrita do equipamento sem alterar nenhum dado. Ativado
                 pela flag --test-write, independente de --write.

                 Fluxo:
                   1. Se tag_atual DESCONHECIDA -> TAG-DESCONH (pulado).
                   2. Se tag_atual virgem (Default String etc.):
                      usa bem_usado como valor de teste se disponivel,
                      ou "O.E.M." como fallback. Grava, verifica, e
                      restaura o valor virgem original ao final.
                      Retorna OK-* ou FALHOU-todos conforme resultado.
                   3. Tag conhecida -> rewrite no-op direto.
                   Cascata: Mecanismo 1 (amidelnx_64) -> Mecanismo 2
                   (amibios_dmi). Para no primeiro sucesso.
                   O BBconfig.conf NAO e atualizado por esta funcao.

    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               sudo_cmd          - prefixo sudo no host
               tag_atual         - valor atual lido da BIOS
               args              - namespace do argparse
               caminho_log_remoto - log remoto do host
               caminho_log_local  - log consolidado local
               bem_usado         - BEM_NUMERO calculado (14 digitos),
                                   usado como valor de teste quando a
                                   tag atual for virgem (opcional)
    RETURNS: str -- "OK-amidelnx", "OK-amibios", "FALHOU-todos",
             "TAG-VIRGEM" (obsoleto, mantido para compatibilidade) ou
             "TAG-DESCONH"
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel, msg, caminho_log_local, args.verbose, args.csv)

    def _executa_cascata(tag_teste):
        """Executa cascata Mec1->Mec2 com tag_teste. Retorna (resultado, sucesso)."""
        _log("INFO", "[TEST-WRITE] --- Mecanismo 1: amidelnx_64 ---")
        try:
            sucesso = executa_amidelnx_remoto(
                ip, ssh_user, sudo_cmd, tag_teste,
                args.amide_remote_path, args.amide_local_path,
                caminho_log_remoto, caminho_log_local,
                args.verbose, args.csv, dry_run=False,
                amide_repo_url=args.amide_repo_url,
                amide_package=args.amide_package,
            )
            if sucesso:
                _log("INFO",
                     "[TEST-WRITE] Mecanismo 1 OK -- modelo compativel "
                     "com amidelnx_64.")
                return "OK-amidelnx", True
            _log("WARNING",
                 "[TEST-WRITE] Mecanismo 1 falhou; tentando Mecanismo 2.")
        except MecanismoIndisponivelError as e:
            _log("WARNING",
                 "[TEST-WRITE] Mecanismo 1 indisponivel: {}".format(e))

        _log("INFO", "[TEST-WRITE] --- Mecanismo 2: amibios_dmi (sysfs) ---")
        try:
            sucesso = executa_amibios_remoto(
                ip, ssh_user, sudo_cmd, tag_teste,
                args.target, caminho_log_remoto, caminho_log_local,
                args.verbose, args.csv, dry_run=False,
                module_repo_url=args.module_repo_url,
                module_package=args.module_package,
            )
            if sucesso:
                _log("INFO",
                     "[TEST-WRITE] Mecanismo 2 OK -- modelo compativel "
                     "via amibios_dmi.")
                return "OK-amibios", True
            _log("ERROR", "[TEST-WRITE] Mecanismo 2 tambem falhou.")
        except MecanismoIndisponivelError as e:
            _log("ERROR",
                 "[TEST-WRITE] Mecanismo 2 indisponivel: {}".format(e))

        _log("ERROR",
             "[TEST-WRITE] Ambos os mecanismos falharam -- modelo "
             "incompativel ou binario ausente.")
        return "FALHOU-todos", False

    # 1. Tag DESCONHECIDA -- nao ha valor para testar
    if not tag_atual or tag_atual == "DESCONHECIDO":
        _log("WARNING",
             "[TEST-WRITE] Tag atual DESCONHECIDA -- teste de escrita pulado.")
        return "TAG-DESCONH"

    # 2. Tag VIRGEM -- usa BEM_NUMERO ou "O.E.M." como valor de teste
    if tag_atual.strip() in _TAGS_VIRGEM:
        tag_teste  = bem_usado.strip() if bem_usado and bem_usado.strip() else "O.E.M."
        tag_restore = tag_atual.strip()
        _log("INFO",
             "[TEST-WRITE] Tag virgem ('{}') -- testando com '{}' "
             "e restaurando ao final.".format(tag_restore, tag_teste))
        resultado, gravou = _executa_cascata(tag_teste)
        if gravou:
            # Restaura o valor virgem original
            _log("INFO",
                 "[TEST-WRITE] Restaurando tag virgem original: "
                 "'{}'".format(tag_restore if tag_restore else "vazio"))
            tag_restaurar = tag_restore if tag_restore else "O.E.M."
            _executa_cascata(tag_restaurar)
        return resultado

    # 3. Tag conhecida -- rewrite no-op direto
    _log("INFO",
         "[TEST-WRITE] Iniciando rewrite no-op com tag atual: "
         "'{}'".format(tag_atual))
    resultado, _ = _executa_cascata(tag_atual)
    return resultado

