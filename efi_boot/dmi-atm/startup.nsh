echo -off
cls
echo ============================================
echo  DMI EDIT - Ajustando Asset Tags
echo ============================================
cd \EFI\UPDATEDMITAG
AMIDEEFIx64.EFI /CA "TESTE-001"
echo ============================================
echo  Concluido! Reiniciando...
echo ============================================
stall 3000000
reset