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
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.0
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.0 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
#
# =======================================================================

import subprocess

from .logging_utils import gravar_log


def calcula_dv_modulo11(base_num):
    """
    NAME: calcula_dv_modulo11
    DESCRIPTION: Calcula o digito verificador usando o algoritmo de Modulo 11
                 do Banco do Brasil. Multiplicadores da direita para a
                 esquerda: 2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5, 6.
                 Se o resultado for 10 ou 11, retorna "0".
    PARAMETER: base_num - string numerica de 13 digitos
    RETURNS: str -- digito verificador ("0" a "9")
    """
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(d) * p for d, p in zip(base_num, pesos))
    resto = soma % 11
    dv = 11 - resto
    if dv in (10, 11):
        return "0"
    return str(dv)


def valida_via_patrimonial_cli(base_num, caminho_log, verbose, suprime_tela,
                                caminho_log_local=""):
    """
    NAME: valida_via_patrimonial_cli
    DESCRIPTION: Validacao redundante via utilitario CLI oficial patrimonial.
                 Retorna o valor de 14 digitos resultante ou string vazia
                 em caso de falha ou indisponibilidade do comando.
    PARAMETER: base_num          - string numerica de 13 digitos
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: str -- 14 digitos ou string vazia
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    try:
        resultado = subprocess.run(
            ["patrimonial", "--non-strict", base_num],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        if resultado.returncode == 0:
            saida = resultado.stdout.strip()
            numeros = "".join(filter(str.isdigit, saida))
            _log("DEBUG", "Validacao redundante CLI patrimonial: {}".format(numeros))
            return numeros
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
    RETURNS: tuple(str, str) -- (tag_esperada_14d, base_13d)
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    if not (valor_config.isdigit() and len(valor_config) in (13, 14)):
        _log("ERROR", "Formato invalido: '{}' (deve ter 13 ou 14 digitos)".format(
            valor_config))
        raise ValueError(
            "Valor lido possui tamanho invalido ({}): {}".format(
                len(valor_config), valor_config))

    if len(valor_config) == 14:
        base_13     = valor_config[:13]
        dv_lido     = valor_config[13]
        dv_calculado = calcula_dv_modulo11(base_13)
        if dv_lido != dv_calculado:
            _log("WARNING",
                 "DV lido ({}) difere do calculado ({}) para base {}!".format(
                     dv_lido, dv_calculado, base_13))
        tag_esperada = valor_config
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

