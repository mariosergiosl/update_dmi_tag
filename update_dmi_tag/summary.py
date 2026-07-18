# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: summary.py
#
# DESCRIPTION: Geracao da tabela de resumo final (monta_tabela_resumo):
#              tabela detalhada (1 linha por host, com colunas IP,
#              Hostname, Fabricante, Modelo, Fab.BIOS, Versao BIOS,
#              SMBIOS, WSMT, tags, BEM conf/usado, Resultado, BBconfig
#              e MAC) e sumario agregado (agrupado por Versao BIOS +
#              flag -w + Resultado).
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.2.8
# REVISION: 2026-07-17 - v2.2.8 - contabiliza o novo resultado
#                        "OK-ja-correto" (tag ja estava correta na BIOS,
#                        nenhum mecanismo executado). Soma esse total ao
#                        ok_total e exibe uma linha propria no resumo
#                        agregado, com sua descricao em _DESCRICOES_RESULTADO.
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
# REVISION: 2026-07-14 - v2.2.0 - adiciona descricoes e contadores para
#                        os novos status INCOMPATIVEL-HW e INCOMPATIVEL-
#                        efiboot (ver write_cascade.py/boot_efi.py).
#                        Coluna Resultado alargada de 18 para 21
#                        caracteres para caber INCOMPATIVEL-efiboot.
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
# REVISION: 2026-07-08 - v2.1.11 - adiciona descricoes e contadores para os
#                        status do Mecanismo 3 (OK-efiboot, FALHOU-efiboot,
#                        TRAVADO-POS-REBOOT, BLOQUEADO-*). Novo bloco
#                        "Mecanismo 3" no sumario agregado, so exibido
#                        quando --allow-efi-fallback foi usado em algum
#                        host, com destaque especial para
#                        TRAVADO-POS-REBOOT (requer verificacao fisica).
# REVISION: 2026-07-07 - v2.1.10 - alarga a coluna Teste Escrita (13 -> 15)
#                        para acomodar o novo status RESTORE-FALHOU (ver
#                        write_cascade.py), que sinaliza quando a
#                        restauracao da tag virgem no --test-write falha e a
#                        BIOS fica com o valor de teste em vez do original.
# REVISION: 2026-07-07 - v2.1.10 - adiciona bloco "Teste de Escrita" ao
#                        sumario agregado, com contagem de OK-amidelnx/
#                        OK-amibios/FALHOU-todos/RESTORE-FALHOU/TAG-DESCONH.
#                        Antes so aparecia por host na tabela detalhada; o
#                        sumario so contava "Resultado" (gravacao real, que
#                        so acontece com --write), deixando sem visibilidade
#                        agregada quantos hosts o --test-write realmente
#                        confirmou como compativeis ou nao.
# REVISION: 2026-07-07 - v2.1.9 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem
#                        mudanca funcional neste arquivo.
# REVISION: 2026-06-12 - v2.1.0 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
# REVISION: 2026-06-15 - v2.1.1 - adiciona coluna MAC.
# REVISION: 2026-06-15 - v2.1.2 - remove coluna Backup; BBconfig exibe
#                        DRY-RUN; corrige coluna fantasma no sumario.
# REVISION: 2026-06-15 - v2.1.3 - colunas Fabricante, Modelo, Fab.BIOS
#                        e Versao BIOS separadas.
# REVISION: 2026-06-15 - v2.1.4 - adiciona coluna Teste Escrita.
# REVISION: 2026-06-15 - v2.1.5 - adiciona SEM-SUDO a _DESCRICOES_RESULTADO.
# REVISION: 2026-06-16 - v2.1.6 - substitui bloco de contadores por
#                        linhas individuais explicitas para cada status
#                        (OK-amidelnx, OK-amibios, DRY-RUN, FALHOU,
#                        SEM-SUDO, PENDENTE, INVALIDO, INACESSIVEL).
#                        Todas as linhas sempre exibidas mesmo com valor
#                        zero: explicito e melhor que implicito.
#
# =======================================================================

import sys


def _normaliza_fabricante(board_vendor):
    """
    NAME: _normaliza_fabricante
    DESCRIPTION: Normaliza nomes de fabricante de placa-mae verbosos
                 para liberar espaco na tabela detalhada. Apenas o
                 caso observado no parque:
                   "Daten Tecnologia Ltda" -> "Daten"
                   "Gigabyte Technology Co., Ltd." -> "Gigabyte"
                   "Positivo Tecnologia" -> "Positivo"
                 Demais fabricantes permanecem inalterados.
    PARAMETER: board_vendor - string do fabricante (registro["board_vendor"])
    RETURNS: str, fabricante normalizado
    """
    if not board_vendor:
        return board_vendor
    mapeamentos = (
        ("Daten Tecnologia Ltda", "Daten"),
        ("Gigabyte Technology Co., Ltd.", "Gigabyte"),
        ("Positivo Tecnologia", "Positivo"),
        ("PERTOSA", "PERTOSA"),
    )
    for origem, destino in mapeamentos:
        if board_vendor.startswith(origem):
            return destino
    return board_vendor


def _normaliza_bios_vendor(bios_vendor):
    """
    NAME: _normaliza_bios_vendor
    DESCRIPTION: Abrevia nomes de fabricante de BIOS conhecidos para
                 exibicao na coluna Fab.BIOS da tabela detalhada.
                 Fabricantes conhecidos sao mapeados para abreviatura.
                 Valores desconhecidos aparecem truncados como vieram
                 (sem perder informacao inesperadamente).
    PARAMETER: bios_vendor - string do fabricante da BIOS
                             (registro["bios_vendor"])
    RETURNS: str, fabricante abreviado ou primeiros 10 chars se
             desconhecido
    """
    if not bios_vendor or bios_vendor == "N/D":
        return bios_vendor
    mapeamentos = (
        ("American Megatrends", "AMI"),
        ("Phoenix Technologies", "Phoenix"),
        ("Award Software", "Award"),
        ("Insyde Software", "Insyde"),
        ("Positivo", "Positivo"),
        ("Hewlett-Packard", "HP"),
        ("Dell Inc.", "Dell"),
        ("Lenovo", "Lenovo"),
    )
    for origem, destino in mapeamentos:
        if bios_vendor.startswith(origem):
            return destino
    # Valor desconhecido: retorna os primeiros 10 chars para nao truncar
    # silenciosamente sem aviso, mas caber na coluna
    return bios_vendor[:10]


# Mapeamento de resultado/status para descricao em linguagem natural,
# usado no sumario agregado. Chaves sao comparadas por prefixo (ex:
# "FALHOU" cobre "FALHOU-todos"; "INACESSIVEL" e exato).
_DESCRICOES_RESULTADO = (
    ("OK-ja-correto", "Tag ja estava correta na BIOS; nenhum mecanismo executado (sem escrita, sem reboot)."),
    ("OK-efiboot",  "Sucesso via Mecanismo 3 (boot EFI temporario apos reboot unico, ver log dedicado)."),
    ("OK-amidelnx", "Sucesso. Gravacao confirmada via amidelnx_64 (Mecanismo 1)."),
    ("OK-amibios",  "Sucesso. Gravacao confirmada via amibios_dmi/sysfs (Mecanismo 2, fallback)."),
    ("DRY-RUN",     "Leitura realizada com sucesso (Simulacao). Nenhuma gravacao executada."),
    ("TRAVADO-POS-REBOOT", "ATENCAO: Mecanismo 3 reiniciou o host e ele nao respondeu via SSH, requer intervencao fisica."),
    ("INCOMPATIVEL-efiboot", "Hardware incompativel: o proprio AMIDEEFIx64.EFI rejeitou a gravacao em pre-boot (assinatura de firmware conhecida, ver log dedicado). Nao vale a pena repetir sem reflash de BIOS."),
    ("FALHOU-efiboot", "Mecanismo 3 tentado (host voltou do reboot) mas a tag nao conferiu."),
    ("BLOQUEADO-",  "Mecanismo 3 nao foi tentado por seguranca (Secure Boot, TPM, espaco, etc., ver log dedicado)."),
    ("INCOMPATIVEL-HW", "Hardware incompativel: os Mecanismos 1 e 2 rejeitaram a gravacao com assinatura de firmware conhecida (ver log). Nao vale a pena repetir sem --allow-efi-fallback ou reflash de BIOS."),
    ("FALHOU",      "Bloqueio no firmware: ambos os mecanismos rejeitaram a gravacao."),
    ("PENDENTE",    "BEM_NUMERO ausente no BBconfig.conf. Aguardando provisionamento."),
    ("INVALIDO",    "BEM_NUMERO com formato invalido (esperado 13 ou 14 digitos)."),
    ("SEM-SUDO",    "Usuario sem privilegio sudo no host (ou --sudo-pass incorreto/ausente). Escrita nao tentada."),
    ("INACESSIVEL", "Host nao respondeu via SSH (timeout, desligado, ou bootstrap de chave falhou)."),
)


def _descricao_resultado(resultado):
    """
    NAME: _descricao_resultado
    DESCRIPTION: Traduz o codigo de resultado/status de um host para uma
                 descricao em linguagem natural, usada no sumario
                 agregado. Faz match por prefixo (primeira correspon-
                 dencia na ordem de _DESCRICOES_RESULTADO). Se nenhum
                 prefixo bater, retorna o proprio resultado como
                 descricao (fallback seguro para status desconhecidos
                 introduzidos no futuro).
    PARAMETER: resultado - string de resultado (ex: "OK-amidelnx",
               "FALHOU-todos", "INACESSIVEL")
    RETURNS: str, descricao em linguagem natural
    """
    resultado = str(resultado or "")
    for prefixo, descricao in _DESCRICOES_RESULTADO:
        if resultado.startswith(prefixo):
            return descricao
    return resultado


def _status_curto(resultado):
    """
    NAME: _status_curto
    DESCRIPTION: Encurta status longos apenas para exibicao nas colunas
                 das tabelas de resumo, evitando o corte no meio de uma
                 palavra (ex: "BLOQUEADO-Ja e"). O caso principal e o
                 "BLOQUEADO-<motivo>", onde o motivo completo (60+ chars)
                 embutido no status estoura a coluna; o motivo continua
                 integral no log dedicado e na coluna Observacao. Status
                 ja curtos (OK-*, FALHOU-*, DRY-RUN, etc.) passam
                 inalterados. Nao altera o valor real do resultado usado
                 na logica (RC, agrupamento), so o texto exibido.
    PARAMETER: resultado - string de resultado
    RETURNS: str, status abreviado para caber na coluna
    """
    s = str(resultado or "")
    if s.startswith("BLOQUEADO"):
        return "BLOQUEADO"
    return s


def monta_tabela_resumo(registros, caminho_log_local, verbose, suprime_tela,
                        write_ativo=False):
    """
    NAME: monta_tabela_resumo
    DESCRIPTION: Gera duas tabelas no log final:
                   1. TABELA DETALHADA, uma linha por host, com
                      colunas IP, Hostname, Placa (normalizada), BIOS,
                      SMBIOS, WSMT, Tag Antes, BEM conf, BEM usado,
                      Tag Depois, Resultado, BBconfig (status da
                      sincronizacao do BBconfig.conf) e Backup (nome do
                      arquivo de backup gerado, se houve).
                   2. SUMARIO AGREGADO, agrupa os registros por
                      (BIOS, flag -w, Resultado), mostrando a contagem
                      de cada combinacao e uma descricao em linguagem
                      natural do que aquele resultado significa
                      (_descricao_resultado). Permite avaliar o
                      resultado de uma execucao em massa rapidamente,
                      sem precisar ler linha a linha.
                 Ambas as tabelas sao escritas no log local (se
                 configurado) e no stdout (se nao suprimido).
    PARAMETER: registros         - lista de dicts retornados por
                                    processa_host_remoto
               caminho_log_local - log consolidado local
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               write_ativo       - bool, valor de args.write desta
                                    execucao (usado na coluna -w do
                                    sumario agregado)
    """
    def _escreve(linha):
        if caminho_log_local:
            try:
                with open(caminho_log_local, "a", encoding="utf-8") as f:
                    f.write(linha + "\n")
            except Exception:
                pass
        if not suprime_tela:
            sys.stdout.write(linha + "\n")

    def _cel(valor, largura):
        s = str(valor if valor not in (None, "") else "N/D")
        return s[:largura].ljust(largura)

    def _cel_raw(valor, largura):
        """Como _cel, mas string vazia permanece vazia (nao vira N/D).
        Usado para colunas onde 'vazio' e um valor valido, como Backup
        (nenhum backup foi gerado)."""
        s = str(valor) if valor is not None else ""
        return s[:largura].ljust(largura)

    # =====================================================================
    # 1. TABELA DETALHADA
    # =====================================================================
    C = {
        "ip":             15,
        "hostname":       13,
        "board_vendor":   10,
        "board_name":     20,
        "bios_vendor":     8,
        "bios_version":   14,
        "smbios":          7,
        "wsmt":            7,
        "tag_antes":      15,
        "bem_conf":       14,
        "bem_usado":      14,
        "tag_depois":     15,
        "resultado":      21,
        "teste_escrita":  15,
        "bbconfig_sync":  17,
        "mac":            52,
    }
    CABECALHOS = [
        "IP", "Hostname", "Fabricante", "Modelo",
        "Fab.BIOS", "Versao BIOS", "SMBIOS", "WSMT",
        "Tag Antes", "BEM conf", "BEM usado", "Tag Depois",
        "Resultado", "Teste Escrita", "BBconfig", "MAC",
    ]

    div = "+-" + "-+-".join("-" * (v + 2) for v in C.values()) + "-+"
    cab = "| " + " | ".join(_cel(h, w) for h, w in zip(CABECALHOS, C.values())) + " |"
    sep = "=" * len(cab)

    _escreve("")
    _escreve(sep)
    _escreve("RESUMO DETALHADO -- {} equipamento(s) processado(s)".format(len(registros)))
    _escreve(sep)
    _escreve(div)
    _escreve(cab)
    _escreve(div)

    for r in registros:
        linha_valores = dict(r)
        linha_valores["board_vendor"] = _normaliza_fabricante(
            r.get("board_vendor", "N/D"))
        linha_valores["bios_vendor"]  = _normaliza_bios_vendor(
            r.get("bios_vendor", "N/D"))
        # bbconfig_sync: substitui N/A por DRY-RUN quando resultado for DRY-RUN
        if (str(r.get("resultado", "")) == "DRY-RUN"
                and linha_valores.get("bbconfig_sync") == "N/A"):
            linha_valores["bbconfig_sync"] = "DRY-RUN"
        # Status abreviado na coluna (o motivo completo do BLOQUEADO fica
        # no log dedicado; aqui evita o corte no meio da palavra).
        linha_valores["resultado"] = _status_curto(r.get("resultado", "N/D"))
        partes = [_cel(linha_valores.get(k, "N/D"), w) for k, w in C.items()]
        _escreve("| " + " | ".join(partes) + " |")

    _escreve(div)
    _escreve("")

    # =====================================================================
    # 2. SUMARIO AGREGADO
    # =====================================================================
    # Agrupa por (BIOS, flag -w, Resultado). A ordem de insercao do dict
    # e preservada (Python 3.7+), mantendo a ordem em que os grupos
    # aparecem na execucao.
    grupos = {}
    flag_w = "-w" if write_ativo else ""
    for r in registros:
        bios = r.get("bios_version", "N/D") or "N/D"
        resultado = r.get("resultado", "N/D") or "N/D"
        chave = (bios, flag_w, resultado)
        grupos[chave] = grupos.get(chave, 0) + 1

    CS = {
        "bios":       15,
        "flag_w":      5,
        "resultado":  21,
        "qtd":         5,
        "observacao": 80,
    }
    CABECALHOS_S = ["BIOS", "-w", "Status", "Qtd", "Observacao"]
    div_s = "+-" + "-+-".join("-" * (v + 2) for v in CS.values()) + "-+"
    cab_s = "| " + " | ".join(_cel(h, w) for h, w in zip(CABECALHOS_S, CS.values())) + " |"
    sep_s = "=" * len(cab_s)

    _escreve(sep_s)
    _escreve("SUMARIO AGREGADO")
    _escreve(sep_s)
    _escreve(div_s)
    _escreve(cab_s)
    _escreve(div_s)

    for (bios, fw, resultado), qtd in grupos.items():
        observacao = _descricao_resultado(resultado)
        valores = {
            "bios": bios, "flag_w": fw, "resultado": _status_curto(resultado),
            "qtd": qtd, "observacao": observacao,
        }
        partes = [_cel(valores[k], w) for k, w in CS.items()]
        _escreve("| " + " | ".join(partes) + " |")

    _escreve(div_s)
    _escreve("")

    # =====================================================================
    # CONTADORES INDIVIDUAIS POR STATUS
    # Todas as linhas sao sempre exibidas (mesmo com valor 0) para que o
    # operador possa interpretar o resultado sem ambiguidade. Explicito
    # e sempre melhor que implicito.
    # =====================================================================
    total = len(registros)

    # Gravacoes bem-sucedidas (qualquer mecanismo)
    ok_amidelnx = sum(1 for r in registros if r.get("resultado") == "OK-amidelnx")
    ok_amibios  = sum(1 for r in registros if r.get("resultado") == "OK-amibios")
    # Tag ja estava correta: nenhum mecanismo rodou (trava global). Conta
    # como sucesso, mas em bucket proprio para deixar claro que nao houve
    # gravacao nova.
    ja_correto  = sum(1 for r in registros if r.get("resultado") == "OK-ja-correto")
    ok_total    = ok_amidelnx + ok_amibios + ja_correto

    # Simulacao sem gravacao
    dryrun = sum(1 for r in registros if r.get("resultado") == "DRY-RUN")

    # Falha na cascata de mecanismos (escrita foi tentada e rejeitada pela BIOS)
    falhou = sum(1 for r in registros if str(r.get("resultado","")).startswith("FALHOU"))

    # Hardware incompativel: Mecanismos 1 e 2 rejeitaram com assinatura de
    # firmware conhecida (ver constants.SINAIS_INCOMPATIBILIDADE_HW). Status
    # proprio, distinto do FALHOU generico: nao vale a pena repetir sem
    # --allow-efi-fallback ou reflash de BIOS (ver write_cascade.py).
    incompativel_hw = sum(1 for r in registros if r.get("resultado") == "INCOMPATIVEL-HW")

    # Sem privilegio sudo (escrita nao foi tentada)
    sem_sudo = sum(1 for r in registros if r.get("resultado") == "SEM-SUDO")

    # BEM_NUMERO ausente no arquivo de configuracao
    pendente = sum(1 for r in registros if r.get("resultado") == "PENDENTE")

    # BEM_NUMERO com formato invalido
    invalido = sum(1 for r in registros if r.get("resultado") == "INVALIDO")

    # Host inacessivel via SSH
    inacessivel = sum(1 for r in registros if r.get("resultado") == "INACESSIVEL")

    # Mecanismo 3 (boot EFI, experimental, ver boot_efi.py)
    efiboot_ok           = sum(1 for r in registros if r.get("resultado") == "OK-efiboot")
    efiboot_falhou       = sum(1 for r in registros if r.get("resultado") == "FALHOU-efiboot")
    efiboot_incompativel = sum(1 for r in registros if r.get("resultado") == "INCOMPATIVEL-efiboot")
    efiboot_travado      = sum(1 for r in registros if r.get("resultado") == "TRAVADO-POS-REBOOT")
    efiboot_bloqueado    = sum(1 for r in registros if str(r.get("resultado", "")).startswith("BLOQUEADO-"))
    efiboot_total        = (efiboot_ok + efiboot_falhou + efiboot_incompativel
                             + efiboot_travado + efiboot_bloqueado)

    # Qualquer outro status nao mapeado acima.
    # efiboot_falhou NAO entra aqui: "FALHOU-efiboot" ja comeca com "FALHOU"
    # e portanto ja esta contado dentro de "falhou" acima. So subtraimos os
    # status de Mecanismo 3 que nao tem bucket proprio nos contadores
    # classicos (OK-efiboot, INCOMPATIVEL-efiboot, TRAVADO-POS-REBOOT,
    # BLOQUEADO-*), subtrair efiboot_total inteiro contaria FALHOU-efiboot
    # duas vezes. incompativel_hw tambem tem bucket proprio, subtrai a parte.
    outros = (total - ok_total - dryrun - falhou - incompativel_hw - sem_sudo
              - pendente - invalido - inacessivel
              - efiboot_ok - efiboot_incompativel - efiboot_travado - efiboot_bloqueado)

    _escreve("  Gravacao OK (amidelnx_64)  : {:3d}  -- escrita confirmada via Mecanismo 1".format(ok_amidelnx))
    _escreve("  Gravacao OK (amibios_dmi)  : {:3d}  -- escrita confirmada via Mecanismo 2 (fallback)".format(ok_amibios))
    _escreve("  Ja correto (OK-ja-correto) : {:3d}  -- tag ja estava correta, nada a fazer (sem escrita, sem reboot)".format(ja_correto))
    _escreve("  Simulacao (DRY-RUN)        : {:3d}  -- apenas leitura, nenhuma gravacao executada".format(dryrun))
    _escreve("  Falha na escrita (FALHOU)  : {:3d}  -- cascata tentada, BIOS rejeitou ambos os mecanismos".format(falhou))
    _escreve("  Incompativel (INCOMPATIVEL-HW): {:3d}  -- Mecanismos 1/2 rejeitados com assinatura de firmware conhecida".format(incompativel_hw))
    _escreve("  Sem privilegio (SEM-SUDO)  : {:3d}  -- usuario sem sudo ou --sudo-pass incorreto/ausente".format(sem_sudo))
    _escreve("  BEM pendente (PENDENTE)    : {:3d}  -- BEM_NUMERO ausente no BBconfig.conf do host".format(pendente))
    _escreve("  BEM invalido (INVALIDO)    : {:3d}  -- BEM_NUMERO com formato invalido (esperado 13 ou 14 digitos)".format(invalido))
    _escreve("  Inacessivel (INACESSIVEL)  : {:3d}  -- host nao respondeu via SSH (desligado, rede, bootstrap)".format(inacessivel))
    if outros > 0:
        _escreve("  Outros (status desconhecido): {:3d}  -- status nao mapeado acima".format(outros))
    _escreve("  " + "-" * 60)
    _escreve("  Total processado           : {:3d}".format(total))
    _escreve("")

    # =====================================================================
    # CONTADORES, MECANISMO 3 (boot EFI, experimental)
    # So exibido se --allow-efi-fallback foi usado em algum host (algum
    # registro com resultado OK-efiboot/FALHOU-efiboot/TRAVADO-POS-REBOOT/
    # BLOQUEADO-*). Destaque especial para TRAVADO-POS-REBOOT: e o unico
    # status do pacote inteiro que significa "host pode estar preso,
    # requer verificacao fisica imediata".
    # =====================================================================
    if efiboot_total > 0:
        _escreve("  --- Mecanismo 3 (boot EFI, experimental) ---")
        _escreve("  OK (OK-efiboot)            : {:3d}  -- gravado com sucesso via reboot/EFI Shell".format(
            efiboot_ok))
        _escreve("  Falhou (FALHOU-efiboot)    : {:3d}  -- host voltou do reboot mas a tag nao conferiu".format(
            efiboot_falhou))
        _escreve("  Incompativel (INCOMPATIVEL-efiboot): {:3d}  -- AMIDEEFIx64.EFI rejeitou com assinatura de firmware conhecida".format(
            efiboot_incompativel))
        _escreve("  Bloqueado (BLOQUEADO-*)    : {:3d}  -- nao tentado por seguranca (ver log dedicado)".format(
            efiboot_bloqueado))
        if efiboot_travado > 0:
            _escreve("  *** TRAVADO-POS-REBOOT ***  : {:3d}  -- HOST(S) NAO RESPONDERAM APOS O REBOOT -- "
                     "VERIFICACAO FISICA IMEDIATA".format(efiboot_travado))
        _escreve("  " + "-" * 60)
        _escreve("  Total Mecanismo 3          : {:3d}".format(efiboot_total))
        _escreve("")

    # =====================================================================
    # CONTADORES, TESTE DE ESCRITA (--test-write)
    # So exibido se --test-write foi usado (algum registro com
    # teste_escrita != "N/A"). Importante nao confundir com os contadores
    # acima: "Resultado" e sobre a gravacao REAL do BEM_NUMERO (so acontece
    # com --write); "Teste Escrita" e sobre a validacao de compatibilidade
    # do modelo (roda mesmo em DRY-RUN, sempre que --test-write e passado).
    # Um host pode aparecer como "DRY-RUN" no Resultado e ainda assim ja
    # informar aqui se, no dia em que --write for usado, a gravacao real
    # vai funcionar (OK-amidelnx/OK-amibios) ou falhar (FALHOU-todos) nesse
    # modelo especifico.
    # =====================================================================
    te_ok_amidelnx      = sum(1 for r in registros if r.get("teste_escrita") == "OK-amidelnx")
    te_ok_amibios       = sum(1 for r in registros if r.get("teste_escrita") == "OK-amibios")
    te_falhou           = sum(1 for r in registros if r.get("teste_escrita") == "FALHOU-todos")
    te_restore_falhou   = sum(1 for r in registros if r.get("teste_escrita") == "RESTORE-FALHOU")
    te_tag_desconh      = sum(1 for r in registros if r.get("teste_escrita") == "TAG-DESCONH")
    te_testado          = (te_ok_amidelnx + te_ok_amibios + te_falhou
                            + te_restore_falhou + te_tag_desconh)

    if te_testado > 0:
        _escreve("  --- Teste de Escrita (--test-write): compatibilidade do modelo, "
                 "nao e a gravacao real do BEM_NUMERO ---")
        _escreve("  Compativel (OK-amidelnx)   : {:3d}  -- Mecanismo 1 grava neste modelo".format(
            te_ok_amidelnx))
        _escreve("  Compativel (OK-amibios)    : {:3d}  -- Mecanismo 2 grava neste modelo (fallback)".format(
            te_ok_amibios))
        _escreve("  Incompativel (FALHOU-todos): {:3d}  -- nenhum mecanismo grava neste modelo hoje".format(
            te_falhou))
        if te_restore_falhou > 0:
            _escreve("  ATENCAO (RESTORE-FALHOU)   : {:3d}  -- teste gravou, mas a restauracao do valor "
                     "virgem falhou; BIOS ficou com o valor de teste, corrija manualmente".format(
                         te_restore_falhou))
        _escreve("  Pulado (TAG-DESCONH)       : {:3d}  -- tag ilegivel no momento da leitura".format(
            te_tag_desconh))
        _escreve("  " + "-" * 60)
        _escreve("  Total testado              : {:3d}  (de {} processados)".format(
            te_testado, total))
        _escreve("")


