# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: summary.py
#
# DESCRIPTION: Geracao da tabela de resumo final (monta_tabela_resumo):
#              tabela detalhada (1 linha por host, com colunas IP,
#              Hostname, Placa normalizada, BIOS, SMBIOS, WSMT, tags,
#              BEM conf/usado, Resultado, BBconfig e Backup) e sumario
#              agregado (agrupado por BIOS + flag -w + Resultado, com
#              contagem e descricao em linguagem natural via
#              _descricao_resultado). _normaliza_fabricante reduz nomes
#              verbosos de fabricante (ex: "Daten Tecnologia Ltda" ->
#              "Daten") para liberar espaco na tabela.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.1
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.0 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
# REVISION: 2026-06-15 - v2.1.1 - adiciona captura de MACs de todas as
#                        interfaces de rede ativas (excluindo lo e
#                        interfaces virtuais) via /sys/class/net. Log
#                        INFO "MAC : ..." adicionado ao bloco de
#                        auditoria de ambiente. Coluna MAC adicionada
#                        no final da tabela detalhada de resumo.
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
#
# =======================================================================

import sys


def _normaliza_fabricante(board):
    """
    NAME: _normaliza_fabricante
    DESCRIPTION: Normaliza nomes de fabricante/placa verbosos para
                 liberar espaco na tabela detalhada, sem perder a
                 informacao relevante (a BIOS Info tem coluna propria).
                 Atualmente normaliza apenas o caso observado:
                   "Daten Tecnologia Ltda DH..." -> "Daten DH..."
                 Demais fabricantes permanecem inalterados.
    PARAMETER: board - string "fabricante modelo" (registro["board"])
    RETURNS: str -- board normalizado
    """
    if not board:
        return board
    prefixo = "Daten Tecnologia Ltda"
    if board.startswith(prefixo):
        return "Daten" + board[len(prefixo):]
    return board


# Mapeamento de resultado/status para descricao em linguagem natural,
# usado no sumario agregado. Chaves sao comparadas por prefixo (ex:
# "FALHOU" cobre "FALHOU-todos"; "INACESSIVEL" e exato).
_DESCRICOES_RESULTADO = (
    ("OK-amidelnx", "Sucesso. Gravacao confirmada via amidelnx_64 (Mecanismo 1)."),
    ("OK-amibios",  "Sucesso. Gravacao confirmada via amibios_dmi/sysfs (Mecanismo 2, fallback)."),
    ("DRY-RUN",     "Leitura realizada com sucesso (Simulacao). Nenhuma gravacao executada."),
    ("FALHOU",      "Bloqueio no firmware: ambos os mecanismos rejeitaram a gravacao."),
    ("PENDENTE",    "BEM_NUMERO ausente no BBconfig.conf. Aguardando provisionamento."),
    ("INVALIDO",    "BEM_NUMERO com formato invalido (esperado 13 ou 14 digitos)."),
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
    RETURNS: str -- descricao em linguagem natural
    """
    resultado = str(resultado or "")
    for prefixo, descricao in _DESCRICOES_RESULTADO:
        if resultado.startswith(prefixo):
            return descricao
    return resultado


def monta_tabela_resumo(registros, caminho_log_local, verbose, suprime_tela,
                        write_ativo=False):
    """
    NAME: monta_tabela_resumo
    DESCRIPTION: Gera duas tabelas no log final:
                   1. TABELA DETALHADA -- uma linha por host, com
                      colunas IP, Hostname, Placa (normalizada), BIOS,
                      SMBIOS, WSMT, Tag Antes, BEM conf, BEM usado,
                      Tag Depois, Resultado, BBconfig (status da
                      sincronizacao do BBconfig.conf) e Backup (nome do
                      arquivo de backup gerado, se houve).
                   2. SUMARIO AGREGADO -- agrupa os registros por
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
        "ip":              15,
        "hostname":        13,
        "board":           17,
        "bios":            12,
        "smbios":           7,
        "wsmt":             7,
        "tag_antes":       15,
        "bem_conf":        14,
        "bem_usado":       14,
        "tag_depois":      15,
        "resultado":       13,
        "bbconfig_sync":   17,
        "bbconfig_backup": 50,
        "mac":             52,
    }
    CABECALHOS = [
        "IP", "Hostname", "Placa", "BIOS", "SMBIOS", "WSMT",
        "Tag Antes", "BEM conf", "BEM usado", "Tag Depois",
        "Resultado", "BBconfig", "Backup", "MAC",
    ]

    div = "+-" + "-+-".join("-" * (v + 2) for v in C.values()) + "-+"
    cab = "| " + " | ".join(_cel(h, w) for h, w in zip(CABECALHOS, C.values())) + " |"

    _escreve("")
    _escreve("=" * len(div))
    _escreve("RESUMO DETALHADO -- {} equipamento(s) processado(s)".format(len(registros)))
    _escreve("=" * len(div))
    _escreve(div)
    _escreve(cab)
    _escreve(div)

    for r in registros:
        linha_valores = dict(r)
        linha_valores["board"] = _normaliza_fabricante(r.get("board", "N/D"))
        partes = []
        for k, w in C.items():
            if k == "bbconfig_backup":
                partes.append(_cel_raw(linha_valores.get(k, ""), w))
            else:
                partes.append(_cel(linha_valores.get(k, "N/D"), w))
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
        bios = r.get("bios", "N/D") or "N/D"
        resultado = r.get("resultado", "N/D") or "N/D"
        chave = (bios, flag_w, resultado)
        grupos[chave] = grupos.get(chave, 0) + 1

    CS = {
        "bios":       15,
        "flag_w":      5,
        "resultado":  14,
        "qtd":         5,
        "observacao": 80,
    }
    CABECALHOS_S = ["BIOS", "-w", "Status", "Qtd", "Observacao"]
    div_s = "+-" + "-+-".join("-" * (v + 2) for v in CS.values()) + "-+"
    cab_s = "| " + " | ".join(_cel(h, w) for h, w in zip(CABECALHOS_S, CS.values())) + " |"

    _escreve("=" * len(div_s))
    _escreve("SUMARIO AGREGADO")
    _escreve("=" * len(div_s))
    _escreve(div_s)
    _escreve(cab_s)
    _escreve(div_s)

    for (bios, fw, resultado), qtd in grupos.items():
        observacao = _descricao_resultado(resultado)
        valores = {
            "bios": bios, "flag_w": fw, "resultado": resultado,
            "qtd": qtd, "observacao": observacao,
        }
        partes = [_cel(valores[k], w) for k, w in CS.items()]
        _escreve("| " + " | ".join(partes) + " |")

    _escreve(div_s)
    _escreve("")

    # Contadores globais por prefixo do resultado (mantidos por
    # compatibilidade com versoes anteriores do log)
    ok     = sum(1 for r in registros if str(r.get("resultado","")).startswith("OK"))
    dryrun = sum(1 for r in registros if r.get("resultado") == "DRY-RUN")
    falhou = sum(1 for r in registros if str(r.get("resultado","")).startswith("FALHOU"))
    outros = len(registros) - ok - dryrun - falhou

    _escreve("  OK       : {}".format(ok))
    _escreve("  DRY-RUN  : {}".format(dryrun))
    _escreve("  FALHOU   : {}".format(falhou))
    if outros > 0:
        _escreve("  OUTROS   : {} (PENDENTE/INACESSIVEL/INVALIDO)".format(outros))
    _escreve("")


