# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: hosts.py
#
# DESCRIPTION: Leitura do arquivo de lista de hosts (modo remoto).
#              le_arquivo_hosts aceita "IP" ou "IP,BEM_NUMERO" por linha,
#              ignorando linhas vazias, comentarios inteiros (#...) e
#              comentarios em fim de linha.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.2
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
#
# =======================================================================

import os
import sys

from .constants import RC_FILE_NOT_FOUND


def le_arquivo_hosts(caminho_hosts):
    """
    NAME: le_arquivo_hosts
    DESCRIPTION: Le o arquivo de lista de hosts. Cada linha pode ter:
                   IP
                   IP,BEM_NUMERO
                 Sao ignoradas:
                   - linhas vazias (apenas espacos)
                   - linhas inteiras de comentario (iniciadas com '#')
                   - comentarios em fim de linha
                     (ex: "192.168.1.10 # equip-01" -> processa apenas o IP)
                 Retorna lista de tuplas (ip, bem_numero_ou_vazio).
    PARAMETER: caminho_hosts - caminho do arquivo de hosts
    RETURNS: list of tuple(str, str) -- [(ip, bem_numero), ...]
    """
    if not os.path.isfile(caminho_hosts):
        sys.stderr.write("ERRO: arquivo de hosts nao encontrado: {}\n".format(
            caminho_hosts))
        sys.exit(RC_FILE_NOT_FOUND)

    hosts = []
    with open(caminho_hosts, "r", encoding="utf-8", errors="ignore") as f:
        for linha in f:
            # Remove comentario trailing antes de qualquer outro tratamento.
            # Ex: "192.168.1.10  # equip de teste" -> "192.168.1.10  "
            if "#" in linha:
                linha = linha.split("#", 1)[0]
            linha = linha.strip()
            # Pula vazias (originais ou que viraram vazias apos remover comentario).
            # Isso tambem cobre linhas que comecam com '#' (apos split, ficam vazias).
            if not linha:
                continue
            partes = linha.split(",", 1)
            ip = partes[0].strip()
            bem = partes[1].strip() if len(partes) > 1 else ""
            if ip:
                hosts.append((ip, bem))
    return hosts


