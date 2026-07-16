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
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
#
# VERSION: 2.2.2
# REVISION: 2026-07-16 - v2.2.2 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.1 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-14 - v2.2.0 - adiciona --parallel N (EXPERIMENTAL):
#                        pool de threads, log isolado por host em
#                        logs/<timestamp>/hosts/, ticker de progresso no
#                        stdout, merge no consolidado na ordem do arquivo
#                        de hosts ao final. --parallel 1 (padrao) mantem
#                        o loop sequencial original, sem mudanca de
#                        comportamento. Adiciona tambem --force-efi-
#                        secureboot (PERIGOSO, ver boot_efi.py), com
#                        segunda confirmacao interativa separada.
#                        Validado em campo com 3 hosts heterogeneos reais
#                        (ver Docs_Test_boot/).
# CREATED: 2026-05-29
# REVISION: 2026-07-13 - v2.1.14 - renumeracao do mecanismo de boot EFI
#                        de "Mecanismo 4" para "Mecanismo 3" (elimina o
#                        buraco na numeracao; cascata agora 1, 2, 3). So
#                        exibicao (log/ajuda/docs); identificadores
#                        funcionais (status, flags, labels) inalterados.
# REVISION: 2026-07-09 - v2.1.13 - adiciona o usuario do SO (getpass)
#                        ao cabecalho do log, para rastreabilidade
#                        quando varios operadores compartilham a
#                        mesma instalacao/log. Empacotamento RPM.
# REVISION: 2026-07-09 - v2.1.12 - atualizacao de numero de versao para
#                        v2.1.12 (correcoes no Mecanismo 3, ver
#                        boot_efi.py).
# REVISION: 2026-07-08 - v2.1.11 - adiciona --allow-efi-fallback,
#                        --efi-local-dir, --efi-timeout e --log-efi
#                        (Mecanismo 3, experimental, ver boot_efi.py).
#                        Validacao dura dos binarios quando a flag e usada,
#                        confirmacao interativa obrigatoria (aborta com
#                        RC_SAFETY_ABORT se nao houver terminal ou o
#                        operador recusar).
# REVISION: 2026-07-07 - v2.1.10 - RC do modo remoto passa a considerar
#                        teste_escrita == "RESTORE-FALHOU" como falha (retorna
#                        1), alem do criterio existente de "resultado". Ver
#                        write_cascade.py para o novo status.
# REVISION: 2026-06-15 - v2.1.4 - adiciona argumento --test-write.
# REVISION: 2026-06-15 - v2.1.5 - loga a linha de comando completa
#                        (sys.argv via shlex.quote) no cabecalho de
#                        execucao para rastreabilidade. Mensagem "Modo"
#                        passa a incluir descricao de TEST-WRITE quando
#                        --test-write esta ativo. Aplicado em modo
#                        remoto e standalone.
# REVISION: 2026-07-06 - v2.1.9 - adiciona validacoes previas de arquivos
#                        locais, do parametro --ssh-pass-file e Fase 1 de
#                        triagem de conectividade de hosts remotos.
# REVISION: 2026-07-07 - v2.1.9 - --amide-local-path passa a distinguir
#                        explicito (erro fatal se invalido) de default nao
#                        informado (avisa e pergunta se houver terminal
#                        interativo; segue automaticamente se nao houver).
#                        Grava arquivo separado com os hosts descartados na
#                        triagem (Fase 1) para reprocessamento posterior.
# REVISION: 2026-07-07 - v2.1.9 - repassa a flag chave_ok (retornada por
#                        triagem_hosts_remotos) para processa_host_remoto via
#                        chave_ja_validada, evitando retest de porta/SSH ja
#                        confirmados na Fase 1.
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
import getpass
import concurrent.futures
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
    DEFAULT_EFI_LOCAL_DIR, DEFAULT_EFI_REBOOT_TIMEOUT, DEFAULT_EFI_LOG_FILE,
    PatrimonioPendenteError, TodosMecanismosFalharam,
    RC_OK, RC_FILE_NOT_FOUND, RC_PERMISSION_ERROR, RC_VALIDATION_ERROR,
    RC_ALL_MECHANISMS_FAILED, RC_SAFETY_ABORT, RC_PATRIMONIO_PENDENTE, RC_UNKNOWN_ERROR,
)
from .logging_utils import gravar_log
from .ssh_bootstrap import _resolve_ssh_pass
from .environment import coletar_dados_ambiente, verifica_pacote_rpm
from .patrimonio import valida_e_calcula_tag, valida_via_patrimonial_cli
from .bbconfig import le_valor_configuracao, sincroniza_bbconfig_local
from .write_cascade import tenta_escrever_tag_local
from .hosts import le_arquivo_hosts
from .host_processor import processa_host_remoto, triagem_hosts_remotos
from .summary import monta_tabela_resumo


def _operador_execucao():
    """
    NAME: _operador_execucao
    DESCRIPTION: Retorna o usuario do SO que esta executando a ferramenta,
                 para rastreabilidade no cabecalho do log (util quando
                 varios operadores compartilham a mesma instalacao/log).
                 Nao confundir com --ssh-user (usuario SSH de destino).
    PARAMETER: nenhum
    RETURNS: str, nome do usuario local ou "desconhecido"
    """
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER") or os.environ.get("LOGNAME") or "desconhecido"


def _processa_hosts_paralelo(hosts_validos, args, caminho_log_local):
    """
    NAME: _processa_hosts_paralelo
    DESCRIPTION: Processa hosts_validos em ate args.parallel threads
                 simultaneas (EXPERIMENTAL, v2.2). Cada host escreve no
                 proprio arquivo de log, isolado, dentro de
                 logs/<timestamp>/hosts/ (sem lock entre threads: hosts
                 sao independentes, cada um com NVRAM/ESP/BBconfig
                 proprios). Um ticker de progresso e impresso no stdout
                 conforme cada host termina (ordem de conclusao, nao a
                 ordem do arquivo de hosts). Ao final, os logs por host
                 sao mesclados no consolidado (caminho_log_local) e no
                 log dedicado do Mecanismo 3 (args.log_efi, se em uso),
                 na ORDEM do arquivo de hosts (facil de achar um host
                 especifico), nao na ordem de conclusao. A prova de
                 kill: se o processo morrer no meio, os logs por host ja
                 estao no disco em logs/<timestamp>/hosts/.
    PARAMETER: hosts_validos     - lista de (ip, bem_lista, chave_ok),
                                    ja triados na Fase 1
               args              - namespace do argparse (args.parallel
                                    define o tamanho do pool)
               caminho_log_local - log consolidado onde os logs por host
                                    serao mesclados ao final
    RETURNS: list, registros na mesma ordem de hosts_validos (nao na
             ordem de conclusao), prontos para summary.monta_tabela_resumo
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(
        os.path.dirname(os.path.abspath(caminho_log_local)),
        "logs", timestamp)
    hosts_dir = os.path.join(log_dir, "hosts")
    os.makedirs(hosts_dir, exist_ok=True)

    log_efi_ativo = bool(getattr(args, "allow_efi_fallback", False))

    def _caminhos_host(ip):
        base = os.path.join(hosts_dir, ip)
        log_host = "{}.log".format(base)
        log_efi_host = "{}.efi.log".format(base) if log_efi_ativo else None
        return log_host, log_efi_host

    def _worker(item):
        ip, bem_lista, chave_ok = item
        log_host, log_efi_host = _caminhos_host(ip)
        registro = processa_host_remoto(
            ip, bem_lista, args, log_host,
            chave_ja_validada=chave_ok, caminho_log_efi=log_efi_host)
        return ip, registro

    total = len(hosts_validos)
    concluidos = 0
    falhas = 0
    resultados_por_ip = {}

    sys.stdout.write(
        "[PARALELO] Iniciando {} host(s) com ate {} em voo simultaneamente. "
        "Logs por host em: {}\n".format(total, args.parallel, hosts_dir))
    sys.stdout.flush()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futuros = [executor.submit(_worker, item) for item in hosts_validos]
        for futuro in concurrent.futures.as_completed(futuros):
            ip, registro = futuro.result()
            resultados_por_ip[ip] = registro
            concluidos += 1
            resultado_str = str(registro.get("resultado", "N/D"))
            if not (resultado_str.startswith("OK") or resultado_str == "DRY-RUN"):
                falhas += 1
            sys.stdout.write("[{}/{}] {} -> {} (falhas ate agora: {})\n".format(
                concluidos, total, ip, resultado_str, falhas))
            sys.stdout.flush()

    # Merge no fim, sem lock, na ORDEM do arquivo de hosts (nao a ordem de
    # conclusao): facil achar um host especifico no consolidado.
    registros_ordenados = []
    with open(caminho_log_local, "a", encoding="utf-8") as consolidado:
        for ip, _bem, _chave in hosts_validos:
            registros_ordenados.append(resultados_por_ip[ip])
            log_host, _ = _caminhos_host(ip)
            if os.path.isfile(log_host):
                with open(log_host, "r", encoding="utf-8", errors="replace") as f:
                    consolidado.write(f.read())

    if log_efi_ativo and getattr(args, "log_efi", ""):
        with open(args.log_efi, "a", encoding="utf-8") as efi_consolidado:
            for ip, _bem, _chave in hosts_validos:
                _, log_efi_host = _caminhos_host(ip)
                if log_efi_host and os.path.isfile(log_efi_host):
                    with open(log_efi_host, "r", encoding="utf-8", errors="replace") as f:
                        efi_consolidado.write(f.read())

    return registros_ordenados


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
    RETURNS: int, codigo de saida
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
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        metavar="N",
        help=(
            "EXPERIMENTAL (v2.2). Numero de hosts processados em paralelo "
            "(padrao: 1, sequencial, comportamento identico as versoes "
            "anteriores). Cada host escreve no proprio log isolado em "
            "logs/<timestamp>/hosts/<IP>.log (sem lock); os logs sao "
            "mesclados no consolidado ao final, na ordem do arquivo de "
            "hosts (nao na ordem de conclusao). Concorrencia limitada por "
            "decisao operacional: nunca processar o parque inteiro de uma "
            "vez, o operador escolhe quantos hosts ficam em voo ao mesmo "
            "tempo."
        ),
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
    # default=None (em vez do caminho ja resolvido) para que, apos o parse,
    # seja possivel diferenciar "usuario nao informou --amide-local-path"
    # (default de conveniencia, tratado com aviso) de "usuario informou um
    # caminho que nao existe" (erro fatal). Ver validacao apos parse_args().
    parser.add_argument(
        "--amide-local-path",
        default=None,
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

    # --- Mecanismo 3: boot EFI temporario (experimental) ---
    parser.add_argument(
        "--allow-efi-fallback",
        action="store_true",
        dest="allow_efi_fallback",
        help=(
            "EXPERIMENTAL. Habilita o Mecanismo 3 (reboot unico via UEFI "
            "Shell + AMIDEEFIx64.EFI) para hosts onde os Mecanismos 1 e 2 "
            "falharem numa gravacao real (-w). Independente de --write/"
            "--test-write: sozinho ja autoriza o reboot fisico se houver "
            "algo a corrigir, mas so tem efeito quando -w tambem estiver "
            "presente (sem -w, os mecanismos diretos nunca sao realmente "
            "testados, entao nao ha FALHOU-todos para acionar o Mecanismo 3). "
            "Pede confirmacao interativa antes de iniciar; recusa aborta a "
            "execucao inteira. NAO pode ser usado sem terminal interativo."
        ),
    )
    parser.add_argument(
        "--force-efi-secureboot",
        action="store_true",
        dest="force_efi_secureboot",
        help=(
            "PERIGOSO, SOMENTE PARA TESTE DE CAMPO CONTROLADO. Pula a "
            "checagem de Secure Boot do Mecanismo 3 (ver boot_efi.py), que "
            "normalmente BLOQUEIA o mecanismo em hosts com Secure Boot "
            "ativo. Com esta flag, o host reinicia mesmo assim; como o "
            "bootx64.efi/AMIDEEFIx64.EFI nao sao assinados, a firmware "
            "provavelmente recusa executa-los e mostra uma tela de 'Secure "
            "Boot Violation' parada, exigindo alguem fisicamente presente "
            "para dispensar a tela antes do host voltar (nao causa perda de "
            "dados nem inutiliza o equipamento -- so trava esperando "
            "confirmacao fisica). So tem efeito junto com --allow-efi-"
            "fallback. Pede uma segunda confirmacao interativa, separada "
            "da confirmacao padrao do --allow-efi-fallback."
        ),
    )
    parser.add_argument(
        "--efi-local-dir",
        default=None,
        dest="efi_local_dir",
        help=(
            "Pasta local com AMIDEEFIx64.EFI e bootx64.efi para o Mecanismo 3 "
            "(padrao: ./efi_boot/dmi-atm). So usado com --allow-efi-fallback."
        ),
    )
    parser.add_argument(
        "--efi-timeout",
        type=int,
        default=DEFAULT_EFI_REBOOT_TIMEOUT,
        dest="efi_timeout",
        help=(
            "Segundos aguardando o host reconectar via SSH apos o reboot do "
            "Mecanismo 3 antes de declarar TRAVADO-POS-REBOOT (padrao: {}).".format(
                DEFAULT_EFI_REBOOT_TIMEOUT)
        ),
    )
    parser.add_argument(
        "--log-efi",
        default=DEFAULT_EFI_LOG_FILE,
        dest="log_efi",
        help="Log dedicado do Mecanismo 3 (padrao: {})".format(DEFAULT_EFI_LOG_FILE),
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
        "--test-write",
        action="store_true",
        default=False,
        dest="test_write",
        help=(
            "Valida a capacidade de gravacao do modelo sem alterar dados. "
            "Executa um rewrite no-op (regrava o valor atual da BIOS) via "
            "cascata amidelnx_64 -> amibios_dmi. Pode ser combinado com "
            "DRY-RUN (sem --write) ou com --write. O resultado aparece na "
            "coluna 'Teste Escrita' da tabela de resumo. Hosts com tag "
            "virgem (Default String) ou DESCONHECIDA tem o teste pulado."
        ),
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

    # Validacoes previas de arquivos locais.
    # Regra: parametro informado explicitamente pelo usuario e invalido =>
    # aborta sempre (erro duro, sem excecao). Parametro nao informado que
    # dependia de um valor de conveniencia (default) que nao existe => nao
    # e um erro do usuario, entao apenas avisa (e pergunta, se possivel).
    if args.hosts:
        if not os.path.isfile(args.hosts):
            sys.stderr.write("Erro: arquivo de hosts nao encontrado: {}\n".format(args.hosts))
            sys.exit(RC_FILE_NOT_FOUND)

    if args.ssh_pass_file:
        if not os.path.isfile(args.ssh_pass_file):
            sys.stderr.write("Erro: arquivo de senha SSH nao encontrado: {}\n".format(args.ssh_pass_file))
            sys.exit(RC_FILE_NOT_FOUND)
        # Se informou o arquivo de senha, valida se a senha lida nao esta vazia.
        # ssh_pass_efetiva ja e o resultado da precedencia --ssh-pass > SSH_PASS
        # > --ssh-pass-file (ver _resolve_ssh_pass); se estiver vazia aqui e
        # porque nenhuma das tres fontes produziu senha.
        if not args.ssh_pass_efetiva:
            sys.stderr.write("Erro: arquivo de senha SSH '{}' existe mas esta vazio ou nao pode ser lido.\n".format(args.ssh_pass_file))
            sys.exit(RC_PERMISSION_ERROR)

    # --amide-local-path: distingue explicito (usuario passou) de default
    # (chute de conveniencia = pasta atual). So sabemos qual foi por causa
    # do default=None no argparse.
    amide_local_explicito = args.amide_local_path is not None
    if args.amide_local_path is None:
        args.amide_local_path = DEFAULT_AMIDE_LOCAL_PATH

    if not os.path.isfile(args.amide_local_path):
        if amide_local_explicito:
            sys.stderr.write("Erro: binario do Amide local nao encontrado: {}\n".format(args.amide_local_path))
            sys.exit(RC_FILE_NOT_FOUND)

        # Nao foi informado, e apenas um chute de conveniencia. Nao trava
        # a execucao inteira por isso: avisa e, se houver terminal
        # interativo, pergunta antes de prosseguir. Sem terminal (chamado
        # por outro script, pipe, etc.), segue automaticamente apos avisar,
        # pois nao ha como perguntar.
        if args.hosts:
            contexto = ("Hosts remotos que ainda nao tem o binario instalado "
                        "vao depender apenas do Mecanismo 2 (sysfs).")
            caminho_log_aviso = args.log_local
        else:
            contexto = "Este host vai depender apenas do Mecanismo 2 (sysfs)."
            caminho_log_aviso = args.log_file

        aviso = ("Binario amidelnx_64 nao encontrado em '{}' (--amide-local-path "
                 "nao foi informado). {}").format(args.amide_local_path, contexto)
        gravar_log(caminho_log_aviso, "WARNING", aviso, args.verbose, False)

        if sys.stdin.isatty() and sys.stdout.isatty():
            sys.stderr.write("AVISO: {}\n".format(aviso))
            resposta = input("Deseja continuar mesmo assim? [s/N]: ").strip().lower()
            if resposta not in ("s", "sim", "y", "yes"):
                gravar_log(caminho_log_aviso, "ERROR",
                           "Execucao cancelada pelo usuario (binario Amide ausente).",
                           args.verbose, False)
                sys.stderr.write("Execucao cancelada.\n")
                sys.exit(RC_FILE_NOT_FOUND)
            gravar_log(caminho_log_aviso, "INFO",
                       "Usuario confirmou prosseguir sem o binario local do Amide.",
                       args.verbose, False)
        else:
            gravar_log(caminho_log_aviso, "WARNING",
                       "Execucao nao-interativa detectada (sem terminal): "
                       "prosseguindo automaticamente.",
                       args.verbose, False)

    # --allow-efi-fallback: validacao dura (arquivos precisam existir,
    # sempre, e uma flag explicita, sem valor de conveniencia como o
    # --amide-local-path) + confirmacao interativa obrigatoria, porque
    # esta flag pode causar reboot fisico de equipamentos em producao.
    # Diferente do aviso do binario Amide (baixo risco, segue sozinho sem
    # terminal), aqui a ausencia de terminal ABORTA sempre: ninguem deve
    # conseguir disparar reboots em lote sem um humano confirmando.
    if getattr(args, "allow_efi_fallback", False):
        if not args.efi_local_dir:
            args.efi_local_dir = DEFAULT_EFI_LOCAL_DIR

        amide_efi = os.path.join(args.efi_local_dir, "AMIDEEFIx64.EFI")
        shell_efi = os.path.join(args.efi_local_dir, "bootx64.efi")
        if not os.path.isfile(amide_efi) or not os.path.isfile(shell_efi):
            sys.stderr.write(
                "Erro: --allow-efi-fallback exige AMIDEEFIx64.EFI e bootx64.efi "
                "em '{}'.\n".format(args.efi_local_dir))
            sys.exit(RC_FILE_NOT_FOUND)

        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            sys.stderr.write(
                "Erro: --allow-efi-fallback exige confirmacao interativa (pode "
                "reiniciar equipamentos em producao) e nao ha terminal disponivel "
                "nesta execucao. Rode manualmente, num terminal, para usar esta "
                "flag.\n")
            sys.exit(RC_SAFETY_ABORT)

        sys.stderr.write(
            "AVISO: --allow-efi-fallback esta ativo. Isso vai REINICIAR "
            "fisicamente os equipamentos da lista que precisarem do Mecanismo "
            "4 (os 2 mecanismos diretos, amidelnx_64 e amibios_dmi, ja tiverem "
            "falhado numa gravacao real com -w). Isso vai reiniciar as maquinas "
            "da lista. Voce tem certeza? [s/N]: ")
        resposta = input().strip().lower()
        if resposta not in ("s", "sim", "y", "yes"):
            sys.stderr.write("Execucao cancelada.\n")
            sys.exit(RC_SAFETY_ABORT)

        # --force-efi-secureboot: segunda confirmacao, separada e mais
        # explicita, porque esta flag pula uma checagem de seguranca real
        # (nao so autoriza o reboot, ignora o motivo que normalmente
        # impediria ele). So faz sentido para teste de campo controlado,
        # com alguem fisicamente presente no equipamento.
        if getattr(args, "force_efi_secureboot", False):
            sys.stderr.write(
                "AVISO ADICIONAL: --force-efi-secureboot esta ativo. A checagem "
                "de Secure Boot do Mecanismo 3 sera PULADA. Se o host tiver "
                "Secure Boot ativo, a firmware provavelmente vai recusar o "
                "binario nao assinado e mostrar uma tela de 'Secure Boot "
                "Violation' parada, exigindo alguem fisicamente presente para "
                "dispensar a tela antes do host voltar. So use isso com "
                "alguem junto do equipamento. Confirma? [s/N]: ")
            resposta2 = input().strip().lower()
            if resposta2 not in ("s", "sim", "y", "yes"):
                sys.stderr.write("Execucao cancelada.\n")
                sys.exit(RC_SAFETY_ABORT)

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
        _log_local("INFO", "update_dmi_tag.py v{}, MODO REMOTO".format(
            SCRIPT_VERSION))
        _log_local("INFO", "Inicio: {}".format(
            time.strftime("%Y-%m-%d %H:%M:%S")))
        _log_local("INFO", "Operad: {}".format(_operador_execucao()))
        _log_local("INFO", "Hosts : {}".format(args.hosts))
        _log_local("INFO", "User  : {}".format(args.ssh_user))
        _log_local("INFO", "Amide : {}".format(args.amide_local_path))
        _log_local("INFO", "Log   : {}".format(args.log_local))

        # Monta descricao do modo de execucao (combinacoes possiveis)
        if args.write:
            modo_desc = "GRAVACAO REAL"
        else:
            modo_desc = "DRY-RUN (simulacao, sem gravacao na BIOS)"
        if getattr(args, "test_write", False):
            modo_desc += " + TEST-WRITE (rewrite no-op para validar compatibilidade)"
        _log_local("INFO", "Modo  : {}".format(modo_desc))

        # Loga a linha de comando completa para rastreabilidade e auditoria
        import shlex
        _log_local("INFO", "Cmd   : {}".format(
            " ".join(shlex.quote(a) for a in sys.argv)))

        if args.production:
            _log_local("WARNING",
                       "PRODUCTION ativado: reinstall-enable e reboot serao executados.")
        _log_local("INFO", "=" * 70)

        hosts = le_arquivo_hosts(args.hosts)

        # Fase 1: Triagem preliminar de conectividade e acesso de todos os hosts
        hosts_validos, registros, hosts_descartados = triagem_hosts_remotos(
            hosts, args, args.log_local)

        # Grava arquivo separado com os hosts descartados na triagem (offline
        # ou acesso negado), no mesmo formato aceito por --hosts, para
        # facilitar reprocessar so esses depois.
        if hosts_descartados:
            caminho_inacessiveis = os.path.join(
                os.path.dirname(os.path.abspath(args.log_local)),
                "hosts_inacessiveis_{}.txt".format(time.strftime("%Y%m%d_%H%M%S")))
            try:
                with open(caminho_inacessiveis, "w", encoding="utf-8") as f:
                    for ip, bem in hosts_descartados:
                        f.write("{},{}\n".format(ip, bem) if bem else "{}\n".format(ip))
                _log_local("INFO", "Hosts inacessiveis ({}) gravados em: {}".format(
                    len(hosts_descartados), caminho_inacessiveis))
            except Exception as e:
                _log_local("WARNING", "Nao foi possivel gravar arquivo de hosts "
                           "inacessiveis {}: {}".format(caminho_inacessiveis, e))

        # Fase 2: Processamento ativo da BIOS nos hosts acessiveis.
        # chave_ok=True (confirmado na Fase 1) evita repetir o retest de
        # porta/chave SSH dentro de processa_host_remoto.
        # --parallel N>1 (EXPERIMENTAL, v2.2): pool de threads com log por
        # host e merge no final. --parallel 1 (padrao) mantem o loop
        # sequencial original, comportamento identico as versoes anteriores.
        if args.parallel > 1 and hosts_validos:
            registros.extend(
                _processa_hosts_paralelo(hosts_validos, args, args.log_local))
        else:
            for ip, bem_lista, chave_ok in hosts_validos:
                registro = processa_host_remoto(
                    ip, bem_lista, args, args.log_local,
                    chave_ja_validada=chave_ok)
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

        # RC do modo remoto: 0 se todos OK ou DRY-RUN, 1 se algum falhou.
        # RESTORE-FALHOU (teste_escrita) tambem conta como falha: mesmo com
        # resultado "DRY-RUN", o --test-write pode ter deixado a BIOS com o
        # valor de teste em vez do valor virgem original (ver write_cascade.py).
        falhas = sum(1 for r in registros
                     if (not str(r.get("resultado", "")).startswith("OK")
                         and r.get("resultado") not in ("DRY-RUN", "PENDENTE", "INVALIDO"))
                     or r.get("teste_escrita") == "RESTORE-FALHOU")
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
               "Operador (SO): {}".format(_operador_execucao()),
               args.verbose, args.csv)

    if args.write:
        _modo_standalone = "GRAVACAO REAL"
    else:
        _modo_standalone = "DRY-RUN (simulacao, sem gravacao na BIOS)"
    if getattr(args, "test_write", False):
        _modo_standalone += " + TEST-WRITE (rewrite no-op para validar compatibilidade)"
    gravar_log(args.log_file, "INFO",
               "Modo: {}".format(_modo_standalone),
               args.verbose, args.csv)

    import shlex as _shlex
    gravar_log(args.log_file, "INFO",
               "Cmd : {}".format(" ".join(_shlex.quote(a) for a in sys.argv)),
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
