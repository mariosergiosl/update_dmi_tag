# =======================================================================
# ARQUIVO DE EXEMPLO / REFERENCIA MANUAL. NUNCA E EXECUTADO DE VERDADE.
#
# Este arquivo existe so para ilustrar o formato esperado e permitir
# teste manual (via console/EFI Shell) fora do fluxo automatizado. Na
# execucao real do Mecanismo 4, o "update_dmi_tag" NAO usa este
# arquivo: o startup.nsh de verdade e gerado dinamicamente, em Python,
# por executa_boot_efi_remoto (ver update_dmi_tag/boot_efi.py), com a
# tag real de cada host (calculada a partir do BEM_NUMERO, igual aos
# Mecanismos 1/2), e copiado por scp para o host remoto no lugar deste.
#
# O conteudo gerado de verdade e bem mais enxuto que este exemplo (sem
# "cls", banners de "echo" decorativos, nem "stall"):
#
#   echo -off
#   cd \EFI\UPDATEDMITAG
#   AMIDEEFIx64.EFI /CA "<tag real de 14 digitos>"
#   reset
#
# O "cd" antes do AMIDEEFIx64.EFI e obrigatorio: o UEFI Shell auto
# executa o startup.nsh com o diretorio atual em FS0:\ (raiz da ESP),
# nao no diretorio onde o proprio startup.nsh esta. Sem o "cd", o shell
# nao encontra o AMIDEEFIx64.EFI (erro "is not recognized...", bug real
# encontrado e corrigido em validacao real de VM, ver
# Docs_Test_boot/README.md).
#
# "TESTE-001" abaixo e so um valor de exemplo para teste manual pelo
# console; nunca reflete a tag real de nenhum host. Se for testar isso
# manualmente numa maquina real, troque por um valor que voce saiba
# identificar como teste, nunca uma tag de patrimonio valida.
# =======================================================================

echo -off
cls
echo ============================================
echo  DMI EDIT - Ajustando Asset Tags (EXEMPLO MANUAL)
echo ============================================
cd \EFI\UPDATEDMITAG
AMIDEEFIx64.EFI /CA "TESTE-001"
echo ============================================
echo  Concluido! Reiniciando...
echo ============================================
stall 3000000
reset
