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
# VERSION: 2.2.9
# REVISION: 2026-07-22 - v2.2.9 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-20 - v2.2.8 - documenta (sem remover) que o campo
#                        "mecanismo" do registro de retorno e morto:
#                        inicializado como "N/D" mas nunca atualizado;
#                        summary.py nao le essa chave. Comentario apenas,
#                        sem mudanca de comportamento.
# REVISION: 2026-07-17 - v2.2.8 - trava global: antes de acionar a cascata
#                        de escrita, compara a tag ja lida na BIOS
#                        (tag_antes) com a tag esperada. Se forem iguais,
#                        nenhum mecanismo e executado (sem escrita, sem
#                        reboot) e o resultado vira "OK-ja-correto". Evita
#                        reprocessar hosts que ja estao corretos e, em
#                        especial, evita escalar ao Mecanismo 3 (reboot) sem
#                        necessidade. Vale so no modo de escrita real
#                        (--write sem --test-write). Revisao de codigo na
#                        mesma versao: remove chamada SSH duplicada de
#                        "which reinstall-enable" em _executa_acoes_production
#                        (o primeiro resultado nunca era usado, custava uma
#                        viagem SSH extra por host em --production); simplifica
#                        ternario sem efeito no nivel de log da auditoria de
#                        RPMs (sempre resultava DEBUG); ajusta mensagem de log
#                        do CLI patrimonial para nao afirmar "nao esta no
#                        PATH" quando o CLI existe mas nao deu retorno valido.
# REVISION: 2026-07-17 - v2.2.7 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.6 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
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
# REVISION: 2026-07-14 - v2.2.0 - processa_host_remoto aceita o novo
#                        parametro opcional caminho_log_efi (None usa
#                        args.log_efi, modo sequencial; --parallel N>1
#                        passa um caminho isolado por host).
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
# REVISION: 2026-07-08 - v2.1.11 - registro["tag_depois"] passa a virar
#                        "DESCONHECIDO" quando resultado_escrita for
#                        "TRAVADO-POS-REBOOT" (Mecanismo 3, ver
#                        write_cascade.py/boot_efi.py), assumir tag_antes
#                        nesse caso seria enganoso, pois nao ha como
#                        confirmar por SSH se a gravacao chegou a
#                        acontecer antes do host travar.
# REVISION: 2026-07-07 - v2.1.10 - tabela da Fase 1 (triagem) passa a usar
#                        nivel INFO uniforme em todas as linhas (evita
#                        desalinhamento causado por ERROR/WARNING terem
#                        largura diferente de INFO no log bruto) e ganha uma
#                        4a coluna "Observacao / Proxima Acao" com
#                        explicacao humanizada de cada status (OFFLINE,
#                        OK, PENDENTE, NEGADO) e se exige alguma acao do
#                        operador. Larguras de coluna calculadas
#                        dinamicamente a partir do maior conteudo.
# REVISION: 2026-07-07 - v2.1.10 - textos de OBS_* encurtados (evitar quebra
#                        de linha/desalinhamento em terminais mais estreitos,
#                        detalhe como nome do arquivo de hosts_inacessiveis
#                        removido do texto por ja sair em linha propria).
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
# REVISION: 2026-07-06 - v2.1.9 - adiciona teste de conectividade tcp rapido
#                        antes do bootstrap de autenticacao ssh.
# REVISION: 2026-07-07 - v2.1.9 - triagem_hosts_remotos passa a retornar
#                        tambem a lista (ip, bem_numero) dos hosts
#                        descartados, para gravacao do arquivo de hosts
#                        inacessiveis em __main__.py. Extrai construcao do
#                        registro descartado para _registro_descartado
#                        (elimina duplicacao do dict).
# REVISION: 2026-07-07 - v2.1.9 - hosts_validos passa a carregar um 3o
#                        elemento (chave_ok) por host, indicando que a Fase 1
#                        ja confirmou porta 22 aberta e chave SSH autorizada.
#                        processa_host_remoto recebe chave_ja_validada e pula
#                        o retest quando True, eliminando round trips de rede
#                        redundantes entre Fase 1 e Fase 2. Tambem remove o
#                        testa_conexao_ssh residual apos prepara_autenticacao_ssh,
#                        que ja garante a conexao por chave internamente antes
#                        de retornar True.
#
# =======================================================================

from .logging_utils import gravar_log, gravar_log_remoto
from .ssh_bootstrap import prepara_autenticacao_ssh
from .ssh_utils import ssh_run, testa_conexao_ssh, detecta_sudo, testa_porta_ssh
from .environment import coletar_dados_ambiente_remoto
from .bbconfig import le_valor_configuracao_remoto, sincroniza_bbconfig_remoto
from .patrimonio import (
    calcula_dv_modulo11, valida_e_calcula_tag, valida_via_patrimonial_cli,
)
from .write_cascade import tenta_escrever_tag_remoto, tenta_teste_escrita_remoto


def processa_host_remoto(ip, bem_numero_lista, args, caminho_log_local,
                          chave_ja_validada=False, caminho_log_efi=None):
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
    PARAMETER: ip                - endereco IP do host remoto
               bem_numero_lista  - BEM_NUMERO da linha do arquivo (pode ser vazio)
               args              - namespace do argparse
               caminho_log_local - log consolidado local
               chave_ja_validada - se True, pula o retest de porta TCP 22 e
                                    de chave SSH (ja confirmados na Fase 1 de
                                    triagem_hosts_remotos), evitando round
                                    trips de rede redundantes. Default False
                                    preserva o comportamento antigo para
                                    quem chamar esta funcao diretamente.
               caminho_log_efi   - log dedicado do Mecanismo 3. None (default)
                                    usa args.log_efi (modo sequencial); em
                                    --parallel N>1, __main__.py passa um
                                    caminho por host (ver write_cascade.py).
    RETURNS: dict, dados do host para compor a linha do resumo
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
        # "mecanismo" e um campo morto: inicializado aqui e em
        # _registro_descartado, mas nunca atualizado ao longo desta funcao
        # (qual mecanismo gravou ja fica implicito no proprio "resultado",
        # ex. OK-amidelnx/OK-amibios/OK-efiboot). summary.py nao le esta
        # chave. Mantido por retrocompatibilidade do formato do dict; nao
        # remover sem checar se algum consumidor externo depende dele.
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

    if chave_ja_validada:
        # Fase 1 (triagem_hosts_remotos) ja confirmou porta TCP 22 aberta e
        # chave publica autorizada para este host: pula o retest, que so
        # repetiria round trips de rede sem checar nada novo.
        _log("DEBUG", "Conectividade e chave SSH ja validadas na triagem (Fase 1); pulando retest.")
    else:
        # 1.a Teste rapido de porta TCP 22 (evita timeouts demorados de hosts offline)
        if not testa_porta_ssh(ip, timeout=2.0):
            _log("ERROR", "Host offline ou porta SSH (TCP 22) fechada.")
            registro["resultado"] = "INACESSIVEL"
            return registro

        # 1.b Bootstrap de autenticacao SSH (gera/distribui chave se necessario).
        # Caminho feliz (chave ja autorizada no host): nao executa nada,
        # apenas retorna True silenciosamente. Em falha, marca INACESSIVEL.
        # prepara_autenticacao_ssh so retorna True apos confirmar a conexao
        # por chave internamente; nao ha necessidade de retestar aqui.
        if not prepara_autenticacao_ssh(
            ip, ssh_user,
            getattr(args, "ssh_pass_efetiva", ""),
            caminho_log_local, args.verbose,
        ):
            _log("ERROR", "Host inacessivel via SSH (bootstrap de autenticacao falhou).")
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
        # Pega apenas a primeira linha relevante, rpm em SLES
        # pode retornar mensagem em portugues no stdout
        linhas_rpm = [x.strip() for x in stdout_rpm.splitlines() if x.strip()]
        nvr = linhas_rpm[0] if linhas_rpm else "AUSENTE"
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          "DEBUG",
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
                "BEM_NUMERO da lista ({}) difere do BBconfig ({}), usando da lista.".format(
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
            "WARNING", "BEM_NUMERO ausente em todas as fontes, host ignorado.",
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

    # Validacao redundante CLI patrimonial, loga com prefixo [IP]
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
            "CLI patrimonial indisponivel no PATH local ou sem retorno valido",
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
            "====== Fim do processamento: {}, SEM-SUDO ======".format(ip),
            caminho_log_local, args.verbose, args.csv)
        return registro

    # 8.1. Trava global: se a tag ja esta correta na BIOS, nao roda nenhum
    # mecanismo (sem escrita, sem reboot). Serve, principalmente, para nao
    # escalar para o Mecanismo 3 (reboot) quando nao ha nada a corrigir, e
    # tambem evita escrita SMI redundante. So aplica em gravacao real
    # (--write); em dry-run e --test-write o fluxo segue para simular/
    # validar. Usa a tag lida na auditoria (tag_antes, via dmidecode). A
    # sincronizacao do BBconfig.conf continua rodando abaixo (resultado
    # comeca com "OK"), pois a tag estar correta nao garante o BBconfig
    # sincronizado.
    if (args.write and not getattr(args, "test_write", False)
            and registro.get("tag_antes", "N/D") == tag_esperada):
        gravar_log_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, "INFO",
            "Tag ja esta correta na BIOS ('{}'); nenhum mecanismo executado "
            "(sem escrita, sem reboot).".format(tag_esperada),
            caminho_log_local, args.verbose, args.csv)
        resultado_escrita = "OK-ja-correto"
    else:
        resultado_escrita = tenta_escrever_tag_remoto(
            ip, ssh_user, sudo_cmd, tag_esperada, args,
            caminho_log_remoto, caminho_log_local,
            caminho_log_efi=caminho_log_efi,
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
    elif resultado_escrita == "TRAVADO-POS-REBOOT":
        # Mecanismo 3: host nao respondeu apos o reboot. Nao ha como
        # confirmar por SSH se a gravacao chegou a acontecer antes de
        # travar, assumir tag_antes aqui seria enganoso.
        registro["tag_depois"] = "DESCONHECIDO"
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
            bem_usado=registro.get("bem_usado", ""),
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
        "====== Fim do processamento: {}, {} ======".format(
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


def _registro_descartado(ip):
    """
    NAME: _registro_descartado
    DESCRIPTION: Monta o registro placeholder (campos "N/D"/"N/A") usado
                 na tabela de resumo para um host descartado na triagem
                 (Fase 1), seja por estar offline ou por acesso negado.
    PARAMETER: ip - endereco IP do host descartado
    RETURNS: dict, registro no mesmo formato usado por processa_host_remoto
    """
    return {
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
        "mecanismo":       "N/D",  # campo morto, ver comentario em processa_host_remoto
        "resultado":       "INACESSIVEL",
        "bbconfig_sync":   "N/A",
        "bbconfig_backup": "",
        "mac":             "N/D",
        "teste_escrita":   "N/A",
    }


def triagem_hosts_remotos(hosts, args, caminho_log_local):
    """
    NAME: triagem_hosts_remotos
    DESCRIPTION: Fase 1: Realiza triagem rapida de todos os hosts remotos.
                 Testa a conectividade via porta TCP 22 e validacao rapida de SSH.
                 Exibe e grava o status consolidado de cada host no inicio da execucao
                 (tabela vai para o log consolidado e, se --verbose, para a tela).
                 Filtra a lista retornando apenas os hosts viaveis (online e autorizados).
    PARAMETER: hosts             - lista de tuplas (ip, bem_numero)
               args              - namespace do argparse
               caminho_log_local - log consolidado local
    RETURNS: tuple(list, list, list), (hosts_validos, registros_descartados,
             hosts_descartados).
             hosts_validos e uma lista de tuplas (ip, bem_numero, chave_ok):
             chave_ok=True indica que a chave publica ja foi confirmada
             autorizada aqui mesmo na Fase 1 (processa_host_remoto pode pular
             o retest de porta/SSH); chave_ok=False indica "PENDENTE"
             (chave ainda nao autorizada, mas ha senha para o bootstrap via
             ssh-copy-id, que so acontece na Fase 2).
             hosts_descartados e uma lista de tuplas (ip, bem_numero) no
             mesmo formato de le_arquivo_hosts, para uso na gravacao do
             arquivo de hosts inacessiveis.
    """
    ssh_user = args.ssh_user
    ssh_pass = getattr(args, "ssh_pass_efetiva", "")

    # Observacoes humanizadas por status, curtas de proposito, para nao
    # quebrar linha e desalinhar a tabela no terminal/log (o detalhe extra,
    # como o nome do arquivo de hosts inacessiveis, ja sai logo depois em
    # uma linha de log separada, nao precisa repetir aqui).
    OBS_OFFLINE  = "Desligada ou sem rede, nao sera processada agora."
    OBS_OK       = "Nenhuma acao necessaria, sera processada na Fase 2."
    OBS_PENDENTE = "Sera processada; chave SSH autorizada via senha na Fase 2."
    OBS_NEGADO   = "Sem chave/senha, nao processada. Informe --ssh-pass."

    # Larguras calculadas a partir do maior conteudo de cada coluna (cabecalho
    # ou observacao), para a tabela nunca ficar desalinhada.
    LARG_IP    = max(15, max((len(ip) for ip, _ in hosts), default=0))
    LARG_CONEC = len("Conectividade")
    LARG_SSH   = max(len("Acesso SSH"), len("NEGADO (Chave ausente/Sem senha)"))
    LARG_OBS   = max(len("Observacao / Proxima Acao"),
                      len(OBS_OFFLINE), len(OBS_OK),
                      len(OBS_PENDENTE), len(OBS_NEGADO))

    def _linha(ip_val, conec_val, ssh_val, obs_val):
        return "| {} | {} | {} | {} |".format(
            str(ip_val).ljust(LARG_IP), str(conec_val).ljust(LARG_CONEC),
            str(ssh_val).ljust(LARG_SSH), str(obs_val).ljust(LARG_OBS))

    divisor = "+-{}-+-{}-+-{}-+-{}-+".format(
        "-" * LARG_IP, "-" * LARG_CONEC, "-" * LARG_SSH, "-" * LARG_OBS)

    # Separador visual e cabecalho em formato de tabela. Tudo em nivel INFO
    # (mesmo para OFFLINE/NEGADO): o proprio conteudo da linha ja identifica
    # o problema, e manter um unico nivel evita desalinhamento no log bruto
    # (ERROR/WARNING/INFO tem larguras diferentes antes do "-").
    gravar_log(caminho_log_local, "INFO", "=" * 70, args.verbose, False)
    gravar_log(caminho_log_local, "INFO", "=== FASE 1: TRIAGEM PRELIMINAR DE CONECTIVIDADE E ACESSO ===", args.verbose, False)
    gravar_log(caminho_log_local, "INFO", divisor, args.verbose, False)
    gravar_log(caminho_log_local, "INFO",
               _linha("IP", "Conectividade", "Acesso SSH", "Observacao / Proxima Acao"),
               args.verbose, False)
    gravar_log(caminho_log_local, "INFO", divisor, args.verbose, False)

    hosts_validos = []
    registros_descartados = []
    hosts_descartados = []

    for ip, bem_lista in hosts:
        # 1. Teste de Socket TCP 22 (maquina ligada)
        if not testa_porta_ssh(ip, timeout=2.0):
            gravar_log(caminho_log_local, "INFO",
                       _linha(ip, "OFFLINE", "N/A", OBS_OFFLINE),
                       args.verbose, False)
            registros_descartados.append(_registro_descartado(ip))
            hosts_descartados.append((ip, bem_lista))
            continue

        # 2. Teste de Acesso SSH via chave publica
        if testa_conexao_ssh(ip, ssh_user):
            gravar_log(caminho_log_local, "INFO",
                       _linha(ip, "ONLINE", "OK (Chave publica)", OBS_OK),
                       args.verbose, False)
            hosts_validos.append((ip, bem_lista, True))
            continue

        # 3. Chave publica falhou. Verifica se ha credenciais para bootstrap
        if ssh_pass:
            gravar_log(caminho_log_local, "INFO",
                       _linha(ip, "ONLINE", "PENDENTE (Bootstrap com senha)", OBS_PENDENTE),
                       args.verbose, False)
            hosts_validos.append((ip, bem_lista, False))
        else:
            gravar_log(caminho_log_local, "INFO",
                       _linha(ip, "ONLINE", "NEGADO (Chave ausente/Sem senha)", OBS_NEGADO),
                       args.verbose, False)
            registros_descartados.append(_registro_descartado(ip))
            hosts_descartados.append((ip, bem_lista))

    gravar_log(caminho_log_local, "INFO", divisor, args.verbose, False)
    gravar_log(caminho_log_local, "INFO", "Fim da triagem: {} host(s) validos de {} total.".format(
        len(hosts_validos), len(hosts)), args.verbose, False)
    gravar_log(caminho_log_local, "INFO", "=" * 70, args.verbose, False)

    return hosts_validos, registros_descartados, hosts_descartados


