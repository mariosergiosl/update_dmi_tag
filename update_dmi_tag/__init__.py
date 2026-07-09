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
# COMPANY: SUSE, consultor BB
# VERSION: 2.1.12
# CREATED: 2026-06-12
# REVISION: 2026-07-09 - v2.1.12 - atualizacao de numero de versao para
#                        v2.1.12 (correcoes no Mecanismo 4, ver
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
# REVISION: 2026-06-12 - v2.1.2 - criacao inicial na modularizacao em
#                        pacote.
#
# =======================================================================

from .constants import SCRIPT_VERSION

__all__ = ["SCRIPT_VERSION"]
__version__ = SCRIPT_VERSION
