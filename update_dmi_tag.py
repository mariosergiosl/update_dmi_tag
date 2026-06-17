#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: update_dmi_tag.py
#
# USAGE: update_dmi_tag.py [opcoes]
#        update_dmi_tag.py --hosts <arquivo> [opcoes]
#
# DESCRIPTION: Shim de compatibilidade. A partir da v2.1.2, a logica do
#              script foi modularizada no pacote update_dmi_tag/ (14
#              modulos). Este arquivo preserva o comando de execucao
#              historico -- "python3 update_dmi_tag.py [opcoes]" --
#              delegando para update_dmi_tag.__main__:main.
#
#              Estrutura esperada no diretorio de trabalho:
#                update_dmi_tag.py        <- este arquivo
#                update_dmi_tag/          <- pacote (14 modulos + __init__)
#                amidelnx_64               <- binario AMI (modo remoto)
#                hosts.txt, .ssh_pass, etc.
#
#              Alternativa equivalente, sem o shim:
#                python3 -m update_dmi_tag [opcoes]
#              (executar de dentro do diretorio que contem a pasta
#              update_dmi_tag/, ou com essa pasta no PYTHONPATH).
#
# OPTIONS: ver ajuda em "--help"
#
# REQUIREMENTS: python3 (stdlib apenas, 3.6+)
#               pacote update_dmi_tag/ no mesmo diretorio
#
# BUGS: ---
#
# NOTES: Codificacao US-ASCII nos comentarios e codigo-fonte.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
#
# VERSION: 2.1.8
#
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.2 - criacao do shim na modularizacao em
#                        pacote. Todo o codigo anterior (3.586 linhas em
#                        arquivo unico) foi distribuido em 14 modulos
#                        dentro de update_dmi_tag/. Ver
#                        update_dmi_tag/constants.py para o historico
#                        completo de revisoes (REVISION) anterior a esta.
#
# =======================================================================

import os
import sys

# Garante que o diretorio deste shim esteja no sys.path, para que
# "import update_dmi_tag" encontre o pacote irmao mesmo quando o shim
# e chamado por caminho absoluto/relativo de outro diretorio.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from update_dmi_tag.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
