# efi_boot/dmi-atm: binários do Mecanismo 4 (EXPERIMENTAL)

Pasta usada por `--efi-local-dir` (padrão) para o Mecanismo 4 de gravação
da DMI Asset Tag via boot temporário em UEFI Shell. Ver seção 17 do
`manual_operacao.md` para o fluxo completo.

## Arquivos

- `AMIDEEFIx64.EFI`: utilitário AMI (mesmo binário usado no modo remoto
  normal), grava o Chassis Asset Tag via `/CA`. **Proprietário, sob NDA
  da AMI, igual ao `amidelnx_64`: não está neste repositório git** (ver
  `.gitignore`). Obter pelo mesmo canal OEM e colocar manualmente nesta
  pasta.
- `bootx64.efi`: nome fixo esperado pelo código (`DEFAULT_EFI_SHELL_FILENAME`
  em `update_dmi_tag/constants.py`). É uma cópia do UEFI Shell oficial
  do projeto TianoCore/EDK2, open-source (ver origem abaixo). Este sim
  fica versionado no git, licença permite redistribuição.
- `startup.nsh`: script executado automaticamente pelo shell, roda o
  `AMIDEEFIx64.EFI /CA "<tag>"` e reinicia. Gerado dinamicamente pelo
  código em produção; a cópia aqui é só um exemplo/manual de referência.

## Origem do bootx64.efi atual (2026-07-09)

- Projeto: [pbatard/UEFI-Shell](https://github.com/pbatard/UEFI-Shell)
  (Pete Batard), binários do UEFI Shell recompilados a partir do EDK2
  stable oficial (TianoCore), mesmo projeto usado pelo Rufus.
- Release: `25H1`
- Arquivo original: `shellx64.efi`
- SHA-256: `fc9e2b45cf0f593d4e5b9268b0cb7c3887a2193643294ef134ff4e8b715ca55e`
- Baixado de: `https://github.com/pbatard/UEFI-Shell/releases/download/25H1/shellx64.efi`
- Cópia idêntica preservada aqui como `bootx64_UEFI-Shell-25H1-pbatard.efi`
  (mesmo conteúdo de `bootx64.efi`, só para deixar a origem/versão
  identificável no nome do arquivo; `bootx64.efi` existe porque o
  código exige esse nome literal).

## Arquivo anterior (problemático, mantido só como referência local)

- `bootx64_ANTIGO_problematico.efi`: SHA-256
  `e6c8c8b6ecf594927724894a394f12c1cb110faa393d6c0e01c1784f9df7cd7d`,
  908192 bytes. Testado em VM real (SLES 15.6, firmware EFI,
  VirtualBox/OVMF) em 2026-07-09: falhou em 3 formas diferentes de
  execução (entrada `efibootmgr`, `chainloader` via GRUB, execução
  manual no `Shell>`), sempre com `Invalid Parameter` ou reset completo
  da plataforma. Origem original desconhecida/não documentada, por isso
  **não está neste repositório git** (licença desconhecida). Mantido só
  localmente, fora do git, como referência do que não usar. Não usar.

## Status de validação

Validado em VM real com firmware EFI (SLES 15.6, VirtualBox/OVMF) em
2026-07-09, ver `Docs_Test_boot/README.md` para o registro completo dos
testes. O `bootx64.efi` novo (25H1) funciona corretamente como shell; a
checagem de segurança e o fluxo de escrita/reboot/recuperação foram
validados, incluindo a correção do bug no `startup.nsh` e do risco de
loop de reboot infinito. A gravação real da tag via `AMIDEEFIx64.EFI`
ainda depende de teste em hardware AMI real (a firmware de VM não é
reconhecida pelo utilitário, ver "Platform identification failed" no
registro de testes).
