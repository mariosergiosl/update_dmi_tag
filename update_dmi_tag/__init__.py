# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: __init__.py
#
# DESCRIPTION: Marca update_dmi_tag como pacote Python. Reexporta
#              SCRIPT_VERSION e main() para conveniencia de quem importar
#              o pacote programaticamente (ex: testes).
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.8
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.2 - criacao inicial na modularizacao em
#                        pacote.
#
# =======================================================================

from .constants import SCRIPT_VERSION

__all__ = ["SCRIPT_VERSION"]
__version__ = SCRIPT_VERSION
