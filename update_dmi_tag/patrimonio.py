# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: patrimonio.py
#
# DESCRIPTION: Validacao do numero patrimonial (Banco do Brasil) por
#              Modulo 11. calcula_dv_modulo11 calcula o digito
#              verificador a partir da base de 13 digitos.
#              valida_via_patrimonial_cli faz validacao redundante via
#              CLI python3-patrimonial, se disponivel no PATH local.
#              valida_e_calcula_tag centraliza a validacao de formato
#              (13 ou 14 digitos) e retorna a tag final de 14 digitos,
#              usada tanto no modo standalone quanto no remoto.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE
# VERSION: 2.2.8
# REVISION: 2026-07-17 - v2.2.8 - corrige dois bugs na validacao redundante
#                        valida_via_patrimonial_cli (nunca corrigidos na
#                        v2.2.7, que so tratou calcula_dv_modulo11):
#                        1) faltava --verbose na chamada do CLI patrimonial;
#                        sem ele o utilitario valida mas nao imprime o numero
#                        completado, entao a funcao sempre retornava vazio e
#                        a validacao redundante nunca acontecia de fato;
#                        2) o parse filtrava so digitos (isdigit), descartando
#                        o "X" final de BEMs com DV=10, o que geraria WARNING
#                        falso de divergencia exatamente nesses BEMs. Agora o
#                        parse pega o primeiro token da saida e aceita 13
#                        digitos + DV numerico ou "X".
# REVISION: 2026-07-17 - v2.2.7 - corrige BUG REAL no DV do Modulo 11:
#                        quando o DV bruto (11 - resto) dava 10, a funcao
#                        calcula_dv_modulo11 retornava "0", mas o padrao
#                        do BB representa DV=10 como "X" (confirmado contra
#                        o utilitario oficial python3-patrimonial:
#                        7417161830009 -> ...X, 7417191152222 -> ...X). O
#                        DV=11 (resto 0) continua "0". Antes disso, cerca
#                        de 1 em 11 BEMs (os que caem em DV=10) recebiam a
#                        tag errada, terminando em 0 em vez de X. Documenta
#                        tambem a estrutura da base: PPPP.AA.DDD.NNNN + DV
#                        (ver docstring de calcula_dv_modulo11).
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
# REVISION: 2026-07-14 - v2.2.0 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
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
# REVISION: 2026-07-08 - v2.1.11 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem
#                        mudanca funcional neste arquivo.
# REVISION: 2026-07-07 - v2.1.10 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem
#                        mudanca funcional neste arquivo.
# REVISION: 2026-07-07 - v2.1.9 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem
#                        mudanca funcional neste arquivo.
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
# REVISION: 2026-06-16 - v2.1.8 - aceita X/x como DV valido em BEM de
#                        14 digitos (DV=10 no padrao patrimonial BB).
#                        Registra WARNING quando DV lido difere do
#                        calculado mas segue a gravacao. Tag preservada
#                        com X maiusculo para gravacao na BIOS.
#
# =======================================================================

import subprocess

from .logging_utils import gravar_log


def calcula_dv_modulo11(base_num):
    """
    NAME: calcula_dv_modulo11
    DESCRIPTION: Calcula o digito verificador (DV) do numero patrimonial do
                 Banco do Brasil pelo algoritmo de Modulo 11.

                 Estrutura da base de 13 digitos (PPPP.AA.DDD.NNNN):
                   PPPP - prefixo do comprador (hoje 7417)
                   AA   - ano de assinatura do contrato
                   DDD  - dia do ano da geracao do range (001 a 366)
                   NNNN - serie do range (0000 a 9999)
                 O DV (1 caractere) fecha o numero em 14 posicoes.

                 Multiplicadores da direita para a esquerda:
                   2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5, 6.
                 dv = 11 - (soma % 11). Convencao do DV, confirmada contra o
                 utilitario oficial python3-patrimonial (2026-07-17):
                   dv == 11 (resto 0) -> "0"
                   dv == 10 (resto 1) -> "X" (ex.: 7417161830009 -> ...X)
                   dv de 1 a 9        -> o proprio digito
    PARAMETER: base_num - string numerica de 13 digitos
    RETURNS: str, digito verificador ("0" a "9" ou "X")
    """
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(d) * p for d, p in zip(base_num, pesos))
    resto = soma % 11
    dv = 11 - resto
    if dv == 11:
        return "0"
    if dv == 10:
        return "X"
    return str(dv)


def valida_via_patrimonial_cli(base_num, caminho_log, verbose, suprime_tela,
                                caminho_log_local=""):
    """
    NAME: valida_via_patrimonial_cli
    DESCRIPTION: Validacao redundante via utilitario CLI oficial patrimonial.
                 Retorna o valor de 14 posicoes resultante (13 digitos + DV,
                 onde o DV pode ser "X" para DV=10) ou string vazia em caso
                 de falha ou indisponibilidade do comando. O --verbose e
                 obrigatorio: sem ele o patrimonial valida mas nao imprime
                 o numero completado (constatado no CLI real, 2026-07-17).
    PARAMETER: base_num          - string numerica de 13 digitos
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: str, 14 posicoes (digitos + DV, DV pode ser "X") ou vazia
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    try:
        resultado = subprocess.run(
            ["patrimonial", "--non-strict", "--verbose", base_num],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        if resultado.returncode == 0:
            # Saida esperada (com --verbose): "<numero14>\tNumero valido".
            # O numero e o primeiro token; preserva o "X" final (DV=10 no
            # padrao BB), que o filtro antigo por isdigit descartava.
            tokens = resultado.stdout.strip().split()
            candidato = tokens[0].upper() if tokens else ""
            if (len(candidato) == 14 and candidato[:13].isdigit()
                    and (candidato[13].isdigit() or candidato[13] == "X")):
                _log("DEBUG", "Validacao redundante CLI patrimonial: {}".format(
                    candidato))
                return candidato
            _log("DEBUG", "CLI patrimonial retornou saida inesperada: '{}'".format(
                resultado.stdout.strip()))
    except FileNotFoundError:
        _log("DEBUG", "Comando CLI patrimonial nao esta no PATH")
    return ""




def valida_e_calcula_tag(valor_config, caminho_log, verbose, suprime_tela,
                          caminho_log_local=""):
    """
    NAME: valida_e_calcula_tag
    DESCRIPTION: Valida o formato do valor patrimonial (13 ou 14 digitos),
                 calcula ou verifica o DV de Modulo 11 e retorna a tag
                 final de 14 digitos. Centraliza a logica de validacao
                 usada tanto no modo standalone quanto no remoto.
                 Levanta ValueError para formatos invalidos.
    PARAMETER: valor_config      - valor lido do arquivo de configuracao
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: tuple(str, str), (tag_esperada_14d, base_13d)
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    # Aceita valor de 14 chars com DV numerico OU "X"/"x" (DV=10 no
    # padrao patrimonial BB). Valores de 13 chars devem ser todos numericos.
    valor_upper = valor_config.upper()
    tem_x_no_final = (len(valor_config) == 14
                      and valor_upper.endswith("X")
                      and valor_upper[:13].isdigit())
    if not (
        (valor_config.isdigit() and len(valor_config) in (13, 14))
        or tem_x_no_final
    ):
        _log("ERROR", "Formato invalido: '{}' (deve ter 13 ou 14 digitos, "
             "ou 13 digitos + X como DV)".format(valor_config))
        raise ValueError(
            "Valor lido possui tamanho invalido ({}): {}".format(
                len(valor_config), valor_config))

    if len(valor_config) == 14:
        base_13      = valor_upper[:13]
        dv_lido      = valor_upper[13]
        dv_calculado = calcula_dv_modulo11(base_13)
        if dv_lido != dv_calculado:
            _log("WARNING",
                 "DV lido ({}) difere do calculado ({}) para base {} "
                 "(aceito conforme padrao BB).".format(
                     dv_lido, dv_calculado, base_13))
        tag_esperada = valor_upper   # preserva X maiusculo para gravacao
        _log("INFO", "Valor ja possui 14 digitos. DV verificado: {}".format(
            dv_calculado))
    else:
        base_13      = valor_config
        dv_calculado = calcula_dv_modulo11(base_13)
        tag_esperada = base_13 + dv_calculado
        _log("INFO",
             "Valor possui 13 digitos. DV calculado: {} (Tag: {})".format(
                 dv_calculado, tag_esperada))

    return tag_esperada, base_13

