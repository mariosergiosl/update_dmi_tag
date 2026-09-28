# Update DMI Tag

Utilitario para validacao de patrimonio e gravacao do campo DMI Asset Tag na BIOS AMI.

**Versao atual: v2.3.3**

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
* **acesso.conf** (v2.3.0, opcional): perfis de acesso para lote misto, ver item 5. Copie de `acesso.conf.example` e proteja com `chmod 600`.

### 5. Lote Misto num Unico Comando (v2.3.0)

Com `--acesso`, um mesmo lote pode misturar equipamentos com acesso diferente, por exemplo a linha SLE 11 (root, senha temporaria) e as linhas SLE 12/15 (usuario do operador). Os perfis do arquivo sao tentados em ordem, maquina a maquina, e o resumo mostra qual foi usado (coluna Acesso). O pacote do modulo de kernel e escolhido pelo kernel de cada maquina, sem `--module-package`:

```bash
python3 update_dmi_tag.py --hosts lote.txt --acesso acesso.conf   --amide-local-path amidelnx_64 --module-rpm-dir ./rpm   --log-local ./lote.log --verbose --write --parallel 10
```

Formato do arquivo, regras de seguranca e o comportamento do sudo estao na secao 3.6 do [manual_operacao.md](manual_operacao.md).

Desde a v2.3.1, a chave SSH distribuida e RSA (o SLE 11 SP3 nao aceita ed25519), e um perfil que entra sem conseguir sudo passa a vez ao perfil seguinte do arquivo. Detalhes nas secoes 3.1 e 3.6 do manual.

Desde a v2.3.2, `--bios-digitos` e `--bbconfig-digitos` (13 ou 14) escolhem, cada um, o formato do numero gravado na BIOS e no arquivo de configuracao. Ver secao 5 do manual antes de mudar o da BIOS.

Na v2.3.3, o padrao do arquivo de configuracao passou a 13 (o formato do gestor oficial do arquivo) e voltou a 14 em 30/09/2026, igual ao da BIOS, sem nova versao; a variavel ausente no arquivo passa a ser acrescentada; e um numero de 14 posicoes com digito verificador errado resulta INVALIDO, sem gravar, para o operador corrigir o valor e rodar de novo.

### 6. Guia Rapido das Opcoes

A secao 7 do manual e a referencia tecnica. Esta e a leitura rapida, para o
operador decidir o que usar.

**Onde e em quais maquinas**

| Opcao | O que faz |
| --- | --- |
| `--hosts ARQUIVO` | Lista das maquinas a tratar, uma por linha (`IP` ou `IP,BEM`). Sem ela, a ferramenta trabalha na propria maquina onde roda |
| `--parallel N` | Quantas maquinas tratar ao mesmo tempo. `10` e o valor usado em campo |

**Como entrar nas maquinas**

| Opcao | O que faz |
| --- | --- |
| `--acesso ARQUIVO` | Arquivo com os usuarios e senhas a tentar, em ordem (operador, root). E o jeito recomendado desde a 2.3.0; com ele as quatro opcoes abaixo sao ignoradas |
| `--ssh-user USUARIO` | Usuario para entrar nas maquinas, no modo antigo sem `--acesso` |
| `--ssh-pass-file ARQUIVO` | Arquivo com a senha desse usuario, no modo antigo |
| `--ssh-pass SENHA` | A senha digitada na propria linha de comando. Evitar: fica no historico |
| `--sudo-pass SENHA` | Senha do sudo, quando ele pede e nao e a mesma do login |

**O que gravar e em que formato**

| Opcao | O que faz |
| --- | --- |
| `-w`, `--write` | Grava de verdade. **Sem ela, so simula**: le tudo e mostra o que faria, sem alterar nada |
| `--bios-digitos 13` ou `14` | Formato do numero gravado na BIOS. Padrao 14 (com o digito verificador). Mudar regrava maquinas ja corretas no outro formato |
| `--bbconfig-digitos 13` ou `14` | Formato do numero gravado no arquivo de configuracao do equipamento. Padrao 14 (desde 30/09/2026). Mudar so reescreve o arquivo, com backup |
| `-c`, `--config ARQUIVO` | Onde esta o arquivo de configuracao do equipamento. Padrao `/etc/BBconfig.conf` |
| `-s`, `--var NOME` | Nome da variavel do numero dentro desse arquivo. Padrao `BEM_NUMERO` |
| `--test-write` | Testa se o modelo aceita gravacao sem mudar o numero: regrava o valor atual; em etiqueta de fabrica, grava o numero e devolve o valor original |

**Os tres jeitos de gravar na BIOS**

A ferramenta tenta, em ordem, ate um funcionar:

1. **Utilitario do fabricante** (`amidelnx_64`), com o sistema ligado.
2. **Modulo de kernel** (`amibios_dmi`), com o sistema ligado. Instalado so durante a
   gravacao e removido depois.
3. **Gravacao durante o boot**, que **reinicia a maquina uma vez**. So entra com a opcao
   abaixo.

| Opcao | O que faz |
| --- | --- |
| `--allow-efi-fallback` | Autoriza o terceiro jeito, que reinicia a maquina. So age quando os dois primeiros falharam de verdade, so com `-w`, so em maquinas UEFI e sem Secure Boot, e pede confirmacao antes de comecar. Sem ela, a maquina em que so o terceiro jeito funcionaria fica marcada como falha, sem reiniciar. Em maquina com boot legado (toda a linha SLE 11) nao tem efeito |
| `--efi-local-dir PASTA` | Onde estao os arquivos do terceiro jeito. Padrao `./efi_boot/dmi-atm` |
| `--efi-timeout SEGUNDOS` | Quanto esperar a maquina voltar depois do reinicio. Padrao 300 (5 minutos) |
| `--force-efi-secureboot` | **Perigoso, so para teste controlado.** Reinicia mesmo com Secure Boot ligado; a maquina deve parar numa tela de bloqueio que exige alguem presente |
| `--amide-local-path ARQUIVO` | Onde esta o utilitario do fabricante no runner. Usar `amidelnx_64` |
| `--amide-remote-path CAMINHO` | Para onde ele e copiado na maquina. Padrao `~/amidelnx_64` |
| `--module-rpm-dir PASTA` | Pasta com os modulos de kernel. Usar `./rpm` |
| `--module-package NOME` | Nome do modulo a instalar. Automatico pelo kernel de cada maquina; so informar para forcar |
| `--module-repo-url URL` | Repositorio de onde baixar o modulo, se nao for pela pasta local |
| `--amide-repo-url`, `--amide-package` | Reservadas, sem efeito hoje |
| `-t`, `--target CAMINHO` | Arquivo do modulo que recebe o numero. Nao alterar |

**Registros**

| Opcao | O que faz |
| --- | --- |
| `--log-local ARQUIVO` | Log principal da execucao, no runner. Dar um nome por lote |
| `--log-efi ARQUIVO` | Log so do terceiro jeito de gravar |
| `--log-file ARQUIVO` | Log dentro de cada maquina. Padrao `/var/log/update_dmi_tag.log` |
| `-v`, `--verbose` | Mostra o andamento na tela, alem do log |
| `--csv` | So no uso local: devolve uma linha com valor antigo, do arquivo e novo |

**Depois da gravacao**

| Opcao | O que faz |
| --- | --- |
| `--production` | Depois de gravar, executa as acoes finais do equipamento: `reinstall-enable` e reinicio. Nao usada nos lotes de correcao |

**Ajuda**

| Opcao | O que faz |
| --- | --- |
| `-h`, `--help` | Lista as opcoes |
| `--version` | Mostra a versao |

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
| 4      | Erro de permissao (inclusive arquivo de `--acesso` sem `chmod 600` ou mal formado) |
| 5      | Erro de validacao do patrimonio |
| 6      | Todos os mecanismos de escrita falharam |
| 7      | Abortado por seguranca (Mecanismo 3, ver secao 17 do manual) |
| 10     | BEM_NUMERO pendente (vazio no arquivo de configuracao corporativo) |
| 99     | Erro nao mapeado |

Lista completa de flags, exemplos avancados (`--sudo-pass`, `--module-rpm-dir`,
`--allow-efi-fallback`, etc.) e detalhes de cada mecanismo estao no
[manual_operacao.md](manual_operacao.md).
