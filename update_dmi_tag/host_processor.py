# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: host_processor.py
#
# DESCRIPTION: Orquestra o fluxo completo de auditoria e gravacao para
#              um host remoto (processa_host_remoto): bootstrap SSH,
#              deteccao de sudo, coleta de ambiente, auditoria de RPMs,
#              leitura/validacao do BEM_NUMERO, cascata de escrita,
#              sincronizacao do BBconfig.conf e acoes --production
#              (_executa_acoes_production), com a guarda que so executa
#              reinstall-enable/reboot quando a gravacao retornou OK.
#              Retorna um dict consumido por summary.monta_tabela_resumo.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.1.7
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.0 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
# REVISION: 2026-06-15 - v2.1.1 - adiciona campo mac ao registro.
# REVISION: 2026-06-15 - v2.1.3 - registro separado em board_vendor,
#                        board_name, bios_vendor e bios_version.
# REVISION: 2026-06-15 - v2.1.4 - adiciona campo teste_escrita ao
#                        registro (default N/A); chamada condicional a
#                        tenta_teste_escrita_remoto quando --test-write
#                        ativo, entre a leitura pos-escrita e a
#                        sincronizacao do BBconfig.conf.
#
# =======================================================================

from .logging_utils import gravar_log, gravar_log_remoto
from .ssh_bootstrap import prepara_autenticacao_ssh
from .ssh_utils import ssh_run, testa_conexao_ssh, detecta_sudo
from .environment import coletar_dados_ambiente_remoto
from .bbconfig import le_valor_configuracao_remoto, sincroniza_bbconfig_remoto
from .patrimonio import (
    calcula_dv_modulo11, valida_e_calcula_tag, valida_via_patrimonial_cli,
)
from .write_cascade import tenta_escrever_tag_remoto, tenta_teste_escrita_remoto


def processa_host_remoto(ip, bem_numero_lista, args, caminho_log_local):
    """
    NAME: processa_host_remoto
    DESCRIPTION: Executa o fluxo completo de auditoria e gravacao para
                 um unico host remoto:
                   1. Testa conectividade SSH
                   2. Detecta sudo
                   3. Coleta dados de ambiente (kernel, placa, SMBIOS, WSMT)
                   4. Verifica dependencias RPM
                   5. Le BEM_NUMERO do BBconfig.conf remoto (sempre loga)
                   6. Define BEM_NUMERO a usar (lista tem precedencia)
                   7. Valida e calcula tag de 14 digitos
                   8. Executa cascata de escrita
                   9. Executa acoes --production se solicitado
                 Retorna dicionario com todos os dados para a tabela de resumo.
    PARAMETER: ip               - endereco IP do host remoto
               bem_numero_lista - BEM_NUMERO da linha do arquivo (pode ser vazio)
               args             - namespace do argparse
               caminho_log_local - log consolidado local
    RETURNS: dict -- dados do host para compor a linha do resumo
    """
    caminho_log_remoto = args.log_file
    ssh_user           = args.ssh_user
    sudo_pass          = args.sudo_pass

    # Estrutura de retorno com valores default
    registro = {
        "ip":              ip,
        "hostname":        "N/D",
        "board_vendor":    "N/D",
        "board_name":      "N/D",
        "bios_vendor":     "N/D",
        "bios_version":    "N/D",
        "smbios":          "N/D",
        "wsmt":            "N/D",
        "tag_antes":       "N/D",
        "bem_conf":        "N/D",
        "bem_usado":       "N/D",
        "tag_depois":      "N/D",
        "mecanismo":       "N/D",
        "resultado":       "INACESSIVEL",
        "bbconfig_sync":   "N/A",
        "bbconfig_backup": "",
        "mac":             "N/D",
        "teste_escrita":   "N/A",
    }

    def _log(nivel, msg, sudo_cmd=""):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel, msg, caminho_log_local, args.verbose, args.csv)

    # 1. Testa conectividade SSH
    # Separador visual entre hosts no log local
    gravar_log(
        caminho_log_local, "INFO",
        "# " + "-" * 68,
        args.verbose, args.csv,
    )
    _log("INFO", "====== Iniciando processamento do host {} ======".format(ip))

    # 1.a Bootstrap de autenticacao SSH (gera/distribui chave se necessario).
    # Caminho feliz (chave ja autorizada no host): nao executa nada,
    # apenas retorna True silenciosamente. Em falha, marca INACESSIVEL.
    if not prepara_autenticacao_ssh(
        ip, ssh_user,
        getattr(args, "ssh_pass_efetiva", ""),
        caminho_log_local, args.verbose,
    ):
        _log("ERROR", "Host inacessivel via SSH (bootstrap de autenticacao falhou).")
        return registro

    if not testa_conexao_ssh(ip, ssh_user):
        _log("ERROR", "Host inacessivel via SSH.")
        return registro

    # 2. Detecta sudo
    # detecta_sudo retorna (prefixo, confirmado):
    #   confirmado=True  -> sudo verificado (sem senha ou com senha)
    #   confirmado=False -> sudo indisponivel ou senha incorreta/ausente
    # Quando nao confirmado: loga WARNING e continua apenas para coleta
    # de dados (sem tentar gravar). A cascata de escrita nao e executada.
    sudo_cmd, sudo_confirmado = detecta_sudo(ip, ssh_user, sudo_pass)
    if sudo_confirmado:
        _log("INFO", "sudo detectado: {}".format(
            "sem senha" if sudo_cmd == "sudo" else "com senha"), sudo_cmd)
    else:
        _log("WARNING",
             "sudo NAO confirmado (usuario sem privilegio ou --sudo-pass "
             "incorreto/ausente). Coleta de ambiente sera feita sem sudo "
             "(dados limitados). Gravacao na BIOS NAO sera tentada.",
             sudo_cmd)

    # 3. Coleta dados de ambiente
    dados_amb = coletar_dados_ambiente_remoto(
        ip, ssh_user, sudo_cmd,
        caminho_log_remoto, caminho_log_local,
        args.verbose, args.csv,
    )
    registro["hostname"]     = dados_amb.get("hostname",      "N/D")
    registro["board_vendor"] = dados_amb.get("board_vendor",  "N/D")
    registro["board_name"]   = dados_amb.get("board_name",    "N/D")
    registro["bios_vendor"]  = dados_amb.get("bios_vendor",   "N/D")
    registro["bios_version"] = dados_amb.get("bios_version",  "N/D")
    registro["smbios"]       = dados_amb.get("smbios_version","N/D")
    registro["wsmt"]         = dados_amb.get("wsmt",          "N/D")
    registro["tag_antes"]    = dados_amb.get("tag_atual",     "N/D")
    registro["mac"]          = dados_amb.get("mac",           "N/D")

    # 4. Verifica dependencias RPM remotas
    for pkg in ("python3-patrimonial", args.module_package,
                "amibios-dmi-kmp", "amibios-dmi"):
        rc_rpm, stdout_rpm, _ = ssh_run(
            ip, ssh_user,
            "rpm -q {} 2>/dev/null | head -1 || echo AUSENTE".format(pkg))
        # Pega apenas a primeira linha relevante -- rpm em SLES
        # pode retornar mensagem em portugues no stdout
        linhas_rpm = [x.strip() for x in stdout_rpm.splitlines() if x.strip()]
        nvr = linhas_rpm[0] if linhas_rpm else "AUSENTE"
        nivel_rpm = "DEBUG" if "AUSENTE" not in nvr else "DEBUG"
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel_rpm,
                          "RPM {}: {}".format(pkg, nvr),
                          caminho_log_local, args.verbose, args.csv)

    # 5. Le BEM_NUMERO do BBconfig.conf remoto (sempre loga)
    bem_conf = le_valor_configuracao_remoto(
        ip, ssh_user,
        args.config, args.var,
        caminho_log_remoto, caminho_log_local,
        args.verbose, args.csv, sudo_cmd,
    )
    registro["bem_conf"] = bem_conf or "PENDENTE"

    # 6. Define BEM_NUMERO a usar (lista tem precedencia; loga discrepancia)
    if bem_numero_lista:
        if bem_conf and bem_conf != bem_numero_lista:
            gravar_log_remoto(
                ip, ssh_user, sudo_cmd, caminho_log_remoto,
                "WARNING",
                "BEM_NUMERO da lista ({}) difere do BBconfig ({}) -- usando da lista.".format(
                    bem_numero_lista, bem_conf),
                caminho_log_local, args.verbose, args.csv)
        bem_usar = bem_numero_lista
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto,
            "INFO", "BEM_NUMERO em uso (fonte: lista de hosts): {}".format(bem_usar),
            caminho_log_local, args.verbose, args.csv)
    elif bem_conf and bem_conf != "PENDENTE":
        bem_usar = bem_conf
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto,
            "INFO", "BEM_NUMERO em uso (fonte: BBconfig.conf): {}".format(bem_usar),
            caminho_log_local, args.verbose, args.csv)
    else:
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto,
            "WARNING", "BEM_NUMERO ausente em todas as fontes -- host ignorado.",
            caminho_log_local, args.verbose, args.csv)
        registro["resultado"] = "PENDENTE"
        return registro

    registro["bem_usado"] = bem_usar

    # 7. Valida e calcula tag de 14 digitos
    # Suprime log interno (caminho vazio) para evitar linhas sem prefixo [IP].
    # O resultado e logado aqui via gravar_log_remoto com prefixo correto.
    try:
        tag_esperada, base_13 = valida_e_calcula_tag(
            bem_usar, "", False, True)
    except ValueError as e:
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto,
            "ERROR", "Validacao falhou: {}".format(e),
            caminho_log_local, args.verbose, args.csv)
        registro["resultado"] = "INVALIDO"
        return registro

    # Loga resultado da validacao com prefixo [IP]
    if len(bem_usar) == 14:
        dv_calc = calcula_dv_modulo11(bem_usar[:13])
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "INFO",
            "Valor ja possui 14 digitos. DV verificado: {}".format(dv_calc),
            caminho_log_local, args.verbose, args.csv)
    else:
        dv_calc = calcula_dv_modulo11(bem_usar)
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "INFO",
            "Valor possui 13 digitos. DV calculado: {} (Tag: {})".format(
                dv_calc, tag_esperada),
            caminho_log_local, args.verbose, args.csv)

    # Validacao redundante CLI patrimonial -- loga com prefixo [IP]
    tag_cli = valida_via_patrimonial_cli(base_13, "", False, True)
    if tag_cli:
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "DEBUG",
            "CLI patrimonial: {}".format(tag_cli),
            caminho_log_local, args.verbose, args.csv)
        if tag_cli != tag_esperada:
            gravar_log_remoto(
                ip, ssh_user, sudo_cmd, caminho_log_remoto, "WARNING",
                "CLI patrimonial retornou {} vs calculado {}".format(
                    tag_cli, tag_esperada),
                caminho_log_local, args.verbose, args.csv)
    else:
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "DEBUG",
            "CLI patrimonial nao disponivel no PATH local",
            caminho_log_local, args.verbose, args.csv)

    # 8. Cascata de escrita
    # Guarda: so tenta gravar se sudo foi confirmado. Sem privilegio,
    # a gravacao na BIOS falharia com "Permission denied" ou com o
    # banner do sudo pedindo senha (que contamina a saida do amidelnx_64
    # e causa falsos FALHOU-todos). Marca resultado como SEM-SUDO e
    # pula toda a etapa de escrita, bbconfig e production.
    if not sudo_confirmado and (args.write or getattr(args, "test_write", False)):
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "ERROR",
            "Escrita abortada: sudo nao confirmado. "
            "Verifique se o usuario tem privilegio no host ou "
            "forneca --sudo-pass correto.",
            caminho_log_local, args.verbose, args.csv)
        registro["resultado"] = "SEM-SUDO"
        registro["tag_depois"] = registro["tag_antes"]
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "INFO",
            "====== Fim do processamento: {} -- SEM-SUDO ======".format(ip),
            caminho_log_local, args.verbose, args.csv)
        return registro

    resultado_escrita = tenta_escrever_tag_remoto(
        ip, ssh_user, sudo_cmd, tag_esperada, args,
        caminho_log_remoto, caminho_log_local,
    )
    # resultado ja e descritivo (ex: "OK-amidelnx", "FALHOU-todos")
    registro["resultado"] = resultado_escrita

    # Leitura da tag pos-escrita para o resumo
    if str(resultado_escrita).startswith("OK"):
        _, tag_depois, _ = ssh_run(
            ip, ssh_user,
            "{} dmidecode -s chassis-asset-tag 2>/dev/null".format(sudo_cmd),
            timeout=10)
        registro["tag_depois"] = tag_depois.strip() or "N/D"
    else:
        registro["tag_depois"] = registro["tag_antes"]

    # 8.6. Teste de escrita (--test-write): rewrite no-op com o valor
    # atual da BIOS para validar compatibilidade do modelo sem alterar
    # nenhum dado real. Executado independente de --write (pode ser
    # combinado com DRY-RUN). Nao atualiza BBconfig.conf.
    if getattr(args, "test_write", False):
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "INFO",
            "[TEST-WRITE] Iniciando validacao de capacidade de gravacao...",
            caminho_log_local, args.verbose, args.csv)
        # Quando --write foi bem-sucedido, a BIOS ja tem o novo valor
        # (tag_depois). O rewrite no-op deve usar esse valor para nao
        # desfazer a gravacao que acabou de ser feita.
        # Em DRY-RUN ou falha, usa tag_antes (valor ainda na BIOS).
        tag_para_teste = (
            registro["tag_depois"]
            if str(resultado_escrita).startswith("OK")
            else registro["tag_antes"]
        )
        registro["teste_escrita"] = tenta_teste_escrita_remoto(
            ip, ssh_user, sudo_cmd,
            tag_para_teste,
            args, caminho_log_remoto, caminho_log_local,
        )
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "INFO",
            "[TEST-WRITE] Resultado: {}".format(registro["teste_escrita"]),
            caminho_log_local, args.verbose, args.csv)

    # 8.5. Sincroniza BBconfig.conf remoto com o BEM_NUMERO usado na
    # gravacao. So executa com --write e apos gravacao confirmada
    # (resultado_escrita comecando com "OK"). Faz backup imutavel do
    # arquivo original antes de editar; nome do backup vai para o
    # registro e aparece na tabela de resumo.
    if args.write and str(resultado_escrita).startswith("OK"):
        sync_result = sincroniza_bbconfig_remoto(
            ip, ssh_user, sudo_cmd, args.config, args.var,
            bem_conf, bem_usar,
            caminho_log_remoto, caminho_log_local, args.verbose, args.csv)
        registro["bbconfig_sync"] = (
            "OK" if sync_result["sincronizado"] else sync_result["motivo"])
        registro["bbconfig_backup"] = sync_result.get("backup") or ""
    elif str(resultado_escrita).startswith("OK") and not args.write:
        # Defensivo: nao deveria ocorrer (resultado OK implica write),
        # mas mantem o campo coerente caso a logica mude no futuro.
        registro["bbconfig_sync"] = "N/A"
    # Em DRY-RUN, FALHOU-todos, PENDENTE, INVALIDO: mantem default "N/A"

    # 9. Acoes finais --production
    # Guarda critica: reinstall-enable e reboot so devem executar quando
    # a gravacao da tag retornou sucesso. Sem essa guarda, hosts com
    # resultado FALHOU-todos, PENDENTE ou INVALIDO sofreriam reboot sem
    # que a tag tivesse sido atualizada. Modo standalone ja tinha essa
    # guarda no fluxo principal; modo remoto nao tinha ate v2.0.2.
    if args.production:
        if str(resultado_escrita).startswith("OK"):
            _executa_acoes_production(
                ip, ssh_user, sudo_cmd, args,
                caminho_log_remoto, caminho_log_local)
        else:
            gravar_log_remoto(
                ip, ssh_user, sudo_cmd, caminho_log_remoto, "WARNING",
                "[PRODUCTION] reinstall-enable e reboot NAO executados: "
                "resultado da gravacao = {}".format(resultado_escrita),
                caminho_log_local, args.verbose, args.csv)

    gravar_log_remoto(
        ip, ssh_user, sudo_cmd, caminho_log_remoto,
        "INFO",
        "====== Fim do processamento: {} -- {} ======".format(
            ip, resultado_escrita),
        caminho_log_local, args.verbose, args.csv)

    return registro


def _executa_acoes_production(ip, ssh_user, sudo_cmd, args,
                               caminho_log_remoto, caminho_log_local):
    """
    NAME: _executa_acoes_production
    DESCRIPTION: Executa as acoes finais protegidas pela flag --production:
                 reinstall-enable e reboot. Antes de cada acao, verifica
                 se o comando esta disponivel no alvo. Sem --production,
                 apenas loga o que seria feito.
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               sudo_cmd          - prefixo sudo
               args              - namespace do argparse
               caminho_log_remoto - log remoto
               caminho_log_local  - log consolidado local
    RETURNS: None
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel, msg, caminho_log_local, args.verbose, args.csv)

    # reinstall-enable
    rc_which, _, _ = ssh_run(
        ip, ssh_user,
        "which reinstall-enable 2>/dev/null || echo AUSENTE", timeout=10)
    _, which_out, _ = ssh_run(
        ip, ssh_user,
        "which reinstall-enable 2>/dev/null || echo AUSENTE", timeout=10)
    if "AUSENTE" in which_out:
        _log("WARNING", "[PRODUCTION] reinstall-enable nao encontrado no alvo.")
    else:
        _log("INFO", "[PRODUCTION] Executando reinstall-enable...")
        rc_ri, stdout_ri, stderr_ri = ssh_run(
            ip, ssh_user,
            "{} reinstall-enable".format(sudo_cmd), timeout=60)
        if rc_ri == 0:
            _log("INFO", "[PRODUCTION] reinstall-enable concluido.")
        else:
            _log("ERROR", "[PRODUCTION] reinstall-enable falhou (rc={}): {}".format(
                rc_ri, stderr_ri.strip()))

    # reboot
    _log("INFO", "[PRODUCTION] Iniciando reboot do host...")
    ssh_run(ip, ssh_user,
            "{} reboot".format(sudo_cmd), timeout=10)
    _log("INFO", "[PRODUCTION] Comando reboot enviado.")


