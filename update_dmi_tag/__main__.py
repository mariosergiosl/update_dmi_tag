# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: __main__.py
#
# USAGE: update_dmi_tag.py [opcoes]
#        update_dmi_tag.py --hosts <arquivo> [opcoes]
#        python3 -m update_dmi_tag [opcoes]
#
# DESCRIPTION: Ponto de entrada do pacote update_dmi_tag. checa_super-
#              usuario garante root em modo standalone. main() faz o
#              parse de argumentos, resolve a senha SSH efetiva, e
#              despacha para o modo remoto (le_arquivo_hosts +
#              processa_host_remoto + monta_tabela_resumo) ou standalone
#              (coleta de ambiente local + validacao + cascata de
#              escrita + sincronizacao do BBconfig.conf local).
#
# OPTIONS: ver ajuda em "--help"
#
# REQUIREMENTS: python3 (stdlib apenas, 3.6+)
#               amidelnx_64 e/ou modulo de kernel amibios_dmi
#               ssh, scp, ssh-keygen, ssh-copy-id (para modo remoto)
#
# BUGS: ---
#
# NOTES: Codificacao US-ASCII nos comentarios e codigo-fonte.
#        Acentos apenas em documentos externos (.md, .docx).
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
#
# VERSION: 2.1.2
#
# CREATED: 2026-05-29
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py
#                        (arquivo unico) na modularizacao em pacote.
#                        Logica de main() e checa_superusuario()
#                        identica. Unica mudanca funcional: o default de
#                        --amide-local-path, que no arquivo unico era
#                        baseado em os.path.dirname(__file__) do proprio
#                        script (DEFAULT_AMIDE_LOCAL_PATH em constants.py
#                        nao serve mais para isso, pois __file__ de
#                        constants.py fica dentro do pacote). Aqui o
#                        default e calculado a partir do diretorio de
#                        trabalho atual (os.getcwd()), que e onde o
#                        shim update_dmi_tag.py e tipicamente executado
#                        junto do binario amidelnx_64.
#
# =======================================================================
#
# COMPATIBILITY: ver constants.py (bloco COMPATIBILITY) para a tabela de
# modelos de placa-mae testados e seus status.
#
# =======================================================================

"""
Ponto de entrada do pacote update_dmi_tag.
Cascata: amidelnx_64 (primeiro) -> amibios_dmi sysfs (fallback).
Modos: standalone (local) e remoto (lista de IPs via SSH).
Codificacao: US-ASCII (sem acentos nos comentarios ou codigo-fonte).
"""

import argparse
import os
import subprocess
import sys
import time

from .constants import (
    SCRIPT_VERSION,
    DEFAULT_CONFIG_FILE, DEFAULT_VAR_NAME,
    DEFAULT_LOG_FILE, DEFAULT_LOCAL_LOG_FILE,
    DEFAULT_AMIDE_REMOTE_PATH, DEFAULT_AMIDE_PACKAGE, DEFAULT_AMIDE_REPO_URL,
    DEFAULT_SYSFS_TARGET, DEFAULT_MODULE_REPO_URL, DEFAULT_MODULE_PACKAGE,
    DEFAULT_SSH_USER,
    PatrimonioPendenteError, TodosMecanismosFalharam,
    RC_OK, RC_FILE_NOT_FOUND, RC_PERMISSION_ERROR, RC_VALIDATION_ERROR,
    RC_ALL_MECHANISMS_FAILED, RC_PATRIMONIO_PENDENTE, RC_UNKNOWN_ERROR,
)
from .logging_utils import gravar_log
from .ssh_bootstrap import _resolve_ssh_pass
from .environment import coletar_dados_ambiente, verifica_pacote_rpm
from .patrimonio import valida_e_calcula_tag, valida_via_patrimonial_cli
from .bbconfig import le_valor_configuracao, sincroniza_bbconfig_local
from .write_cascade import tenta_escrever_tag_local
from .hosts import le_arquivo_hosts
from .host_processor import processa_host_remoto
from .summary import monta_tabela_resumo


def checa_superusuario():
    """
    NAME: checa_superusuario
    DESCRIPTION: Verifica se o script esta sendo executado como root.
                 Em modo remoto (--hosts), o root e necessario localmente
                 apenas para operacoes que exijam privilegio (ex: scp para
                 diretorios restritos). A verificacao e mantida para
                 garantir consistencia com o modo standalone.
    PARAMETER: nenhum
    RETURNS: None
    """
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        sys.stderr.write(
            "Erro: Este script deve ser executado como superusuario (root).\n")
        sys.exit(1)


def main():
    """
    NAME: main
    DESCRIPTION: Ponto de entrada principal. Faz o parse dos argumentos,
                 determina o modo de execucao (standalone ou remoto) e
                 delega para o fluxo correspondente.
    PARAMETER: nenhum
    RETURNS: int -- codigo de saida
    """
    # Caminho local padrao do amidelnx_64 (para scp em modo remoto):
    # diretorio de trabalho atual, onde o shim update_dmi_tag.py e
    # tipicamente executado junto do binario. Sobrescrevivel via
    # --amide-local-path.
    DEFAULT_AMIDE_LOCAL_PATH = os.path.join(os.getcwd(), "amidelnx_64")

    parser = argparse.ArgumentParser(
        prog="update_dmi_tag.py",
        description=(
            "Utilitario Mario Luz para atualizacao de DMI Asset Tag corporativa. "
            "Cascata: amidelnx_64 (primeiro) -> amibios_dmi sysfs (fallback). "
            "Modos: standalone (local) e remoto (lista de IPs via SSH)."
        )
    )

    # --- Arquivo de hosts (ativa modo remoto) ---
    parser.add_argument(
        "--hosts",
        default="",
        metavar="ARQUIVO",
        help="Arquivo de hosts (IP ou IP,BEM_NUMERO por linha). Ativa modo remoto.",
    )

    # --- SSH ---
    parser.add_argument(
        "--ssh-user",
        default=DEFAULT_SSH_USER,
        help="Usuario SSH para modo remoto (padrao: usuario da sessao atual)",
    )
    parser.add_argument(
        "--sudo-pass",
        default="",
        metavar="SENHA",
        help="Senha do sudo no host remoto (opcional; detecta automaticamente)",
    )
    parser.add_argument(
        "--ssh-pass",
        default="",
        metavar="SENHA",
        help=("Senha SSH para distribuir a chave via ssh-copy-id quando "
              "a autenticacao por chave ainda nao esta configurada. "
              "Tem precedencia sobre SSH_PASS env e --ssh-pass-file. "
              "Nao usada para autenticacao apos a chave estar distribuida."),
    )
    parser.add_argument(
        "--ssh-pass-file",
        default="",
        metavar="ARQUIVO",
        help=("Arquivo texto contendo a senha SSH na primeira linha. "
              "Usado apenas se --ssh-pass nao for fornecido e SSH_PASS "
              "nao estiver definida no ambiente."),
    )

    # --- Configuracao corporativa ---
    parser.add_argument(
        "-c", "--config",
        default=DEFAULT_CONFIG_FILE,
        help="Caminho do BBconfig.conf (padrao: {})".format(DEFAULT_CONFIG_FILE),
    )
    parser.add_argument(
        "-s", "--var",
        default=DEFAULT_VAR_NAME,
        help="Nome da variavel de patrimonio (padrao: {})".format(DEFAULT_VAR_NAME),
    )

    # --- Mecanismo 1: amidelnx_64 ---
    parser.add_argument(
        "--amide-local-path",
        default=DEFAULT_AMIDE_LOCAL_PATH,
        help="Caminho local do amidelnx_64 para scp (padrao: mesmo dir do script)",
    )
    parser.add_argument(
        "--amide-remote-path",
        default=DEFAULT_AMIDE_REMOTE_PATH,
        help="Caminho do amidelnx_64 no host remoto (padrao: {})".format(
            DEFAULT_AMIDE_REMOTE_PATH),
    )
    parser.add_argument(
        "--amide-repo-url",
        default=DEFAULT_AMIDE_REPO_URL,
        help="URL do repo zypper do amidelnx_64 (reservado para uso futuro)",
    )
    parser.add_argument(
        "--amide-package",
        default=DEFAULT_AMIDE_PACKAGE,
        help="Nome do pacote amidelnx_64 no OBS (reservado para uso futuro)",
    )

    # --- Mecanismo 2: amibios_dmi ---
    parser.add_argument(
        "-t", "--target",
        default=DEFAULT_SYSFS_TARGET,
        help="Caminho sysfs da asset tag (padrao: {})".format(DEFAULT_SYSFS_TARGET),
    )
    parser.add_argument(
        "--module-repo-url",
        default=DEFAULT_MODULE_REPO_URL,
        help="URL do repo zypper do KMP amibios_dmi",
    )
    parser.add_argument(
        "--module-package",
        default=DEFAULT_MODULE_PACKAGE,
        help="Nome do pacote KMP a instalar (padrao: {})".format(
            DEFAULT_MODULE_PACKAGE),
    )

    # --- Log ---
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help="Log no host alvo (padrao: {})".format(DEFAULT_LOG_FILE),
    )
    parser.add_argument(
        "--log-local",
        default=DEFAULT_LOCAL_LOG_FILE,
        help="Log local consolidado em modo remoto (padrao: {})".format(
            DEFAULT_LOCAL_LOG_FILE),
    )

    # --- Comportamento ---
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Exibe mensagens de log no terminal",
    )
    parser.add_argument(
        "-w", "--write",
        action="store_true",
        help="Habilita gravacao fisica. Sem esta flag, executa em Dry Run (simulacao).",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="(Modo standalone) Retorna linha CSV no stdout: antigo,config,novo",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Executa acoes finais apos gravacao: reinstall-enable e reboot.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="{} {}".format("update_dmi_tag.py", SCRIPT_VERSION),
    )

    args = parser.parse_args()

    # Resolve a senha SSH efetiva para o bootstrap de autenticacao,
    # aplicando precedencia: --ssh-pass > SSH_PASS env > --ssh-pass-file.
    # Sempre define args.ssh_pass_efetiva (mesmo que vazia) para que o
    # bootstrap possa consulta-la com getattr sem erro.
    args.ssh_pass_efetiva = _resolve_ssh_pass(args)

    # Em modo remoto, se --log-file nao foi passado explicitamente,
    # redireciona para arquivo local (evita Permission denied em /var/log).
    if args.hosts and args.log_file == DEFAULT_LOG_FILE:
        args.log_file = os.path.join(
            os.path.dirname(os.path.abspath(args.log_local)),
            'update_dmi_tag_alvo.log'
        )

    # Validacao: --csv incompativel com --hosts
    if args.csv and args.hosts:
        sys.stderr.write(
            "Erro: --csv nao e suportado em modo remoto (--hosts).\n")
        sys.exit(1)

    # ===================================================================
    # MODO REMOTO
    # ===================================================================
    if args.hosts:
        # Modo remoto: nao requer root local. O sudo e tratado remotamente
        # por detecta_sudo() em cada host alvo.

        # Abre o log local consolidado em modo APPEND para preservar
        # historico de todas as execucoes (antes era aberto em "w" e
        # truncava o arquivo a cada rodada, descartando o historico).
        # Se o arquivo nao existir ainda, e criado. Se ja existir, a
        # linha em branco abaixo serve como separador visual entre o
        # bloco anterior e o cabecalho que sera escrito a seguir.
        try:
            with open(args.log_local, "a", encoding="utf-8") as f:
                f.write("\n")
        except Exception as e:
            sys.stderr.write(
                "Aviso: nao foi possivel abrir log local {} para append: {}\n".format(
                    args.log_local, e))

        def _log_local(nivel, msg):
            gravar_log(args.log_local, nivel, msg, args.verbose, False)

        _log_local("INFO", "=" * 70)
        _log_local("INFO", "update_dmi_tag.py v{} -- MODO REMOTO".format(
            SCRIPT_VERSION))
        _log_local("INFO", "Inicio: {}".format(
            time.strftime("%Y-%m-%d %H:%M:%S")))
        _log_local("INFO", "Hosts : {}".format(args.hosts))
        _log_local("INFO", "User  : {}".format(args.ssh_user))
        _log_local("INFO", "Amide : {}".format(args.amide_local_path))
        _log_local("INFO", "Log   : {}".format(args.log_local))
        _log_local("INFO", "Modo  : {}".format(
            "GRAVACAO REAL" if args.write else "DRY-RUN (simulacao)"))
        if args.production:
            _log_local("WARNING",
                       "PRODUCTION ativado: reinstall-enable e reboot serao executados.")
        _log_local("INFO", "=" * 70)

        hosts = le_arquivo_hosts(args.hosts)
        registros = []

        for ip, bem_lista in hosts:
            registro = processa_host_remoto(
                ip, bem_lista, args, args.log_local)
            registros.append(registro)

        monta_tabela_resumo(registros, args.log_local, args.verbose, args.csv,
                            write_ativo=args.write)

        _log_local("INFO", "=" * 70)
        _log_local("INFO", "FINALE")
        _log_local("INFO", "Fim   : {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
        _log_local("INFO", "Total : {} equipamento(s) processado(s)".format(
            len(registros)))
        _log_local("INFO", "Log   : {}".format(args.log_local))
        _log_local("INFO", "=" * 70)

        # RC do modo remoto: 0 se todos OK ou DRY-RUN, 1 se algum falhou
        # RC do modo remoto: 0 se todos OK ou DRY-RUN, 1 se algum falhou
        falhas = sum(1 for r in registros
                     if not str(r.get("resultado", "")).startswith("OK")
                     and r.get("resultado") not in ("DRY-RUN", "PENDENTE", "INVALIDO"))
        return 0 if falhas == 0 else 1

    # ===================================================================
    # MODO STANDALONE
    # ===================================================================
    checa_superusuario()

    gravar_log(args.log_file, "INFO",
               "--- Iniciando processo de atualizacao de DMI Asset Tag ---",
               args.verbose, args.csv)
    gravar_log(args.log_file, "INFO",
               "update_dmi_tag.py v{} (Python {})".format(
                   SCRIPT_VERSION, sys.version.split()[0]),
               args.verbose, args.csv)
    gravar_log(args.log_file, "INFO",
               "Modo: {}".format(
                   "GRAVACAO REAL" if args.write else "DRY-RUN (simulacao)"),
               args.verbose, args.csv)
    if args.production:
        gravar_log(args.log_file, "WARNING",
                   "PRODUCTION ativado: reinstall-enable e reboot serao executados.",
                   args.verbose, args.csv)

    coletar_dados_ambiente(args.log_file, args.verbose, args.csv)

    valor_antigo    = "ERROR_OR_EMPTY"
    valor_config    = "ERROR_OR_EMPTY"
    valor_novo      = "ERROR_OR_EMPTY"
    retorno         = RC_UNKNOWN_ERROR

    try:
        # Auditoria de dependencias
        verifica_pacote_rpm(
            "python3-patrimonial", args.log_file, args.verbose, args.csv)
        kmp_instalado = verifica_pacote_rpm(
            args.module_package, args.log_file, args.verbose, args.csv)
        verifica_pacote_rpm(
            "amibios-dmi-kmp", args.log_file, args.verbose, args.csv)
        verifica_pacote_rpm(
            "amibios-dmi", args.log_file, args.verbose, args.csv)

        # Leitura e validacao do patrimonio
        valor_config = le_valor_configuracao(
            args.config, args.var, args.log_file, args.verbose, args.csv)

        if not valor_config:
            raise PatrimonioPendenteError(
                "Variavel '{}' vazia em {}: provisionamento pendente.".format(
                    args.var, args.config))

        tag_esperada, base_13 = valida_e_calcula_tag(
            valor_config, args.log_file, args.verbose, args.csv)

        # Validacao redundante via CLI patrimonial
        tag_cli = valida_via_patrimonial_cli(
            base_13, args.log_file, args.verbose, args.csv)
        if tag_cli and tag_cli != tag_esperada:
            gravar_log(args.log_file, "WARNING",
                       "CLI patrimonial retornou {} vs calculado {}".format(
                           tag_cli, tag_esperada),
                       args.verbose, args.csv)

        # Leitura do valor antigo (sysfs local se disponivel)
        if os.path.exists(args.target):
            try:
                with open(args.target, "r") as f:
                    valor_antigo = f.read().strip()
                gravar_log(args.log_file, "INFO",
                           "Valor antigo na BIOS (sysfs): '{}'".format(valor_antigo),
                           args.verbose, args.csv)
            except Exception as e:
                gravar_log(args.log_file, "WARNING",
                           "Nao foi possivel ler valor antigo: {}".format(e),
                           args.verbose, args.csv)

        # Cascata de escrita
        resultado_escrita = tenta_escrever_tag_local(
            tag_esperada, args, kmp_instalado)

        if str(resultado_escrita).startswith("OK"):
            # Leitura do valor novo para CSV e log
            if os.path.exists(args.target):
                try:
                    with open(args.target, "r") as f:
                        valor_novo = f.read().strip()
                except Exception:
                    valor_novo = tag_esperada
            else:
                valor_novo = tag_esperada
            gravar_log(args.log_file, "INFO",
                       "--- Atualizacao concluida: {} ---".format(resultado_escrita),
                       args.verbose, args.csv)
            retorno = RC_OK

            # Sincroniza BBconfig.conf local com a tag de 14 digitos
            # gravada na BIOS, caso o arquivo ainda contenha o valor de
            # 13 digitos (ou qualquer valor diferente do gravado). So
            # executa com --write (implicito aqui, pois resultado_escrita
            # so comeca com "OK" quando args.write esta ativo).
            if args.write:
                sincroniza_bbconfig_local(
                    args.config, args.var, valor_config, tag_esperada,
                    args.log_file, args.verbose, args.csv)
        elif resultado_escrita == "DRY-RUN":
            valor_novo = valor_antigo
            retorno    = RC_OK
        else:
            valor_novo = "WRITE_FAILED"
            retorno    = RC_ALL_MECHANISMS_FAILED

        # Acoes --production (standalone)
        if args.production and retorno == RC_OK and args.write:
            gravar_log(args.log_file, "INFO",
                       "[PRODUCTION] Verificando reinstall-enable...",
                       args.verbose, args.csv)
            try:
                rc_which = subprocess.run(
                    ["which", "reinstall-enable"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=False).returncode
                if rc_which == 0:
                    gravar_log(args.log_file, "INFO",
                               "[PRODUCTION] Executando reinstall-enable...",
                               args.verbose, args.csv)
                    subprocess.run(["reinstall-enable"], check=False, timeout=60)
                    gravar_log(args.log_file, "INFO",
                               "[PRODUCTION] reinstall-enable concluido.",
                               args.verbose, args.csv)
                else:
                    gravar_log(args.log_file, "WARNING",
                               "[PRODUCTION] reinstall-enable nao encontrado.",
                               args.verbose, args.csv)
            except Exception as e:
                gravar_log(args.log_file, "ERROR",
                           "[PRODUCTION] Falha no reinstall-enable: {}".format(e),
                           args.verbose, args.csv)
            gravar_log(args.log_file, "INFO",
                       "[PRODUCTION] Iniciando reboot...",
                       args.verbose, args.csv)
            subprocess.run(["reboot"], check=False)

    except PatrimonioPendenteError as e:
        gravar_log(args.log_file, "WARNING", str(e), args.verbose, args.csv)
        valor_novo = valor_antigo
        retorno    = RC_PATRIMONIO_PENDENTE
    except TodosMecanismosFalharam as e:
        gravar_log(args.log_file, "ERROR", str(e), args.verbose, args.csv)
        valor_novo = "ALL_FAILED"
        retorno    = RC_ALL_MECHANISMS_FAILED
    except FileNotFoundError as e:
        gravar_log(args.log_file, "ERROR",
                   "Arquivo nao encontrado: {}".format(e), args.verbose, args.csv)
        retorno = RC_FILE_NOT_FOUND
    except PermissionError as e:
        gravar_log(args.log_file, "ERROR",
                   "Erro de permissao: {}".format(e), args.verbose, args.csv)
        retorno = RC_PERMISSION_ERROR
    except ValueError as e:
        gravar_log(args.log_file, "ERROR",
                   "Erro de validacao: {}".format(e), args.verbose, args.csv)
        retorno = RC_VALIDATION_ERROR
    except Exception as e:
        gravar_log(args.log_file, "ERROR",
                   "Erro nao mapeado: {}".format(e), args.verbose, args.csv)
        retorno = RC_UNKNOWN_ERROR

    gravar_log(args.log_file, "INFO",
               "--- FINALE (rc={}) ---".format(retorno),
               args.verbose, args.csv)

    # Saida CSV (modo standalone)
    if args.csv:
        sys.stdout.write("{},{},{}\n".format(
            valor_antigo, valor_config, valor_novo))

    return retorno


if __name__ == "__main__":
    sys.exit(main())
