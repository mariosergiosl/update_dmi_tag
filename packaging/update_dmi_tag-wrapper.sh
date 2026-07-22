#!/bin/sh
# =======================================================================
#
# FILE: update_dmi_tag-wrapper.sh
#
# DESCRIPTION: Instalado como /usr/bin/update_dmi_tag pelo pacote RPM.
#              Todos os arquivos do projeto (codigo, exemplos, binarios
#              opcionais como amidelnx_64/AMIDEEFIx64.EFI) vivem juntos
#              em /opt/update_dmi_tag, entao o wrapper entra nesse
#              diretorio antes de chamar o script, para que os defaults
#              do codigo (--amide-local-path, --efi-local-dir, leitura
#              de bb_repo.conf) resolvam corretamente sem mudanca de
#              codigo, exatamente como no fluxo manual documentado no
#              manual_operacao.md (secao 2.1).
#
# =======================================================================

INSTALL_DIR="/opt/update_dmi_tag"

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Erro: diretorio de instalacao nao encontrado: $INSTALL_DIR" >&2
    exit 1
fi

cd "$INSTALL_DIR" || exit 1
exec python3 update_dmi_tag.py "$@"
