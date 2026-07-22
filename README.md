# Update DMI Tag

Utilitario para validacao de patrimonio e gravacao do campo DMI Asset Tag na BIOS AMI.

**Versao atual: v2.2.9**

## Visao Geral

O `update_dmi_tag.py` e uma ferramenta desenvolvida em Python para ler um numero de patrimonio de 13 ou 14 digitos (de arquivos locais ou remotos), validar o digito verificador usando o algoritmo de Modulo 11 e gravar o valor no campo DMI Asset Tag da BIOS.

A gravacao e feita em cascata de forma automatica:
1. **amidelnx_64**: Binario proprietario da AMI (tentativa inicial).
2. **amibios_dmi**: Modulo de kernel via sysfs (fallback para placas Gigabyte/sem WSMT). O desenvolvimento e detalhes deste modulo do kernel estao no projeto [amibios_dmi](https://github.com/mariosergiosl/amibios_dmi).
3. **Boot EFI temporario** (opcional, experimental, ver seção 17 do manual): reinicia o equipamento uma unica vez para um UEFI Shell, so quando os dois mecanismos acima falharem numa gravacao real e o operador habilitar explicitamente com `--allow-efi-fallback`.

Se a tag ja lida na BIOS for igual a esperada, nenhum mecanismo e executado (resultado `OK-ja-correto`): a ferramenta nunca reescreve nem reinicia um host que ja esta correto.

O utilitario suporta execucao local (standalone) e execucao remota em lote (lista de IPs via SSH), com processamento paralelo opcional (`--parallel N`). Oferece modo Dry-Run por padrao.

---

## Pre-requisitos

* Python 3.6 ou superior (apenas biblioteca padrao).
* Binario `amidelnx_64` no mesmo diretorio do script.
* Acesso SSH e SCP configurados para execucao remota.

---

## Instalacao

Basta clonar o repositorio para a maquina local:

```bash
git clone <url-do-repositorio>
cd update_dmi_tag
```

---

## Como Usar

### 1. Execucao de Consulta (Apenas Leitura)

Esse comando realiza apenas a consulta do patrimonio nos hosts, sem gravar na BIOS:

```bash
python3 /home/[seu usuario ldap]/asset_tag_full/update_dmi_tag.py --hosts /home/[seu usuario ldap]/asset_tag_full/host.txt --amide-local-path /home/[seu usuario ldap]/asset_tag_full/amidelnx_64 --log-local /home/[seu usuario ldap]/asset_tag_full/update_dmi_tag_remoto.log --ssh-pass-file /home/[seu usuario ldap]/asset_tag_full/.ssh_pass --verbose
```

### 2. Execucao de Gravacao na BIOS

Para efetivar a gravacao do asset tag na BIOS, e necessario adicionar o parametro `-w` no final do comando:

```bash
python3 /home/[seu usuario ldap]/asset_tag_full/update_dmi_tag.py --hosts /home/[seu usuario ldap]/asset_tag_full/host.txt --amide-local-path /home/[seu usuario ldap]/asset_tag_full/amidelnx_64 --log-local /home/[seu usuario ldap]/asset_tag_full/update_dmi_tag_remoto.log --ssh-pass-file /home/[seu usuario ldap]/asset_tag_full/.ssh_pass --verbose -w
```

### 3. Execucao Completa (Paralela, com Mecanismo 3 e Gravacao Real)

Comando de referencia com todas as opcoes relevantes, explicado flag a
flag na seção 6.3.1 do [manual_operacao.md](manual_operacao.md):

```bash
python3 -m update_dmi_tag --hosts hosts.txt --ssh-user <usuario_ldap> \
  --ssh-pass-file .ssh_pass --amide-local-path amidelnx_64 \
  --module-rpm-dir ./rpm --allow-efi-fallback --force-efi-secureboot \
  --efi-local-dir ./efi_boot/dmi-atm --efi-timeout 900 \
  --log-efi ./update_dmi_tag_efi.log --log-local ./update_dmi_tag_remoto.log \
  --verbose --write --parallel 10
```

Esse exemplo aciona o Mecanismo 3 (reboot fisico, se os dois primeiros
falharem) e processa ate 10 hosts em paralelo. **Não rode com
`--allow-efi-fallback` num lote real sem antes ler a seção 17 do
manual.**

### 4. Setup dos Arquivos de Entrada
* **host.txt**: Insira os enderecos IP dos hosts alvos, um por linha.
* **.ssh_pass**: Insira a senha do seu usuario LDAP (utilizada para conexao SSH automatica).

---

## Documentacao Detalhada

Para informacoes completas sobre comandos, arquitetura, cenarios de teste e troubleshoot, consulte o [manual_operacao.md](manual_operacao.md).

---

## Licenca

GPL-3.0-only. Ver [LICENSE.md](LICENSE.md).

---

## Resumo de Codigos de Retorno (Exit Codes)

| Codigo | Significado |
| ------ | ----------- |
| 0      | Sucesso ou Dry-Run |
| 1      | Modo remoto: um ou mais hosts falharam |
| 2      | Standalone: falha de integridade pos-escrita |
| 3      | Arquivo nao encontrado |
| 4      | Erro de permissao |
| 5      | Erro de validacao do patrimonio |
| 6      | Todos os mecanismos de escrita falharam |
| 7      | Abortado por seguranca (Mecanismo 3, ver secao 17 do manual) |
| 10     | BEM_NUMERO pendente (vazio no arquivo de configuracao corporativo) |
| 99     | Erro nao mapeado |

Lista completa de flags, exemplos avancados (`--sudo-pass`, `--module-rpm-dir`,
`--allow-efi-fallback`, etc.) e detalhes de cada mecanismo estao no
[manual_operacao.md](manual_operacao.md).
