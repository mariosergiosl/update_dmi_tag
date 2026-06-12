# Manual de Operacao Completo -- update_dmi_tag.py v2.0.3

**Autor:** Mario Luz (mario.luz@suse.com)
**Versao do documento:** 2.0.3
**Data:** 2026-06-12
**Projeto:** Atualizacao Automatizada de DMI Asset Tag -- Frota de Equipamentos

---

## Resumo Executivo

Este documento descreve a solucao de automacao desenvolvida para atualizar o campo DMI
Asset Tag na BIOS AMI dos equipamentos em Linux (SLES).

O problema original: os equipamentos nao possuiam o numero patrimonial gravado no campo
DMI do firmware BIOS, impossibilitando auditoria de hardware independente do sistema
operacional. A gravacao manual equipamento a equipamento era inviavel na escala do
parque de equipamentos.

A solucao entregue e o script `update_dmi_tag.py` v2.0.3, que opera em dois modos:

- **Modo remoto**: o operador executa o script na sua maquina Linux e o script conecta
  via SSH em uma lista de hosts, realiza auditoria completa de ambiente, valida o numero
  patrimonial (Modulo 11) e grava o campo DMI Asset Tag automaticamente
- **Modo standalone**: o script roda diretamente no equipamento alvo, para futura
  distribuicao via ferramenta corporativa de gestao de endpoints, como parte do fluxo
  de provisionamento

A cascata de mecanismos de escrita resolve a heterogeneidade do parque: placas com
protecao WSMT no firmware (maioria) sao atendidas pelo `amidelnx_64`; placas legadas
sem WSMT sao atendidas pelo `amibios_dmi` via sysfs. O unico modelo ainda sem solucao
e o Daten DH3UP, cujo bloqueio e em nivel de firmware e requer abordagem pre-boot
via UEFI Shell (em avaliacao).

**Status atual:** script em uso operacional para os modelos compativeis. Investigacao
do DH3UP em andamento. Empacotamento como RPM para distribuicao automatizada previsto
como proximo passo.

---

## 1. Contexto do Projeto

### 1.1 Problema original

O campo DMI Asset Tag e um registro gravado no firmware BIOS/UEFI do equipamento,
especificamente na secao **Chassis** (campo `chassis-asset-tag`), que e o padrao de
mercado e o definido nos padroes do projeto para identificacao patrimonial de hardware.

E lido por `dmidecode` e serve como identificador de patrimonio do hardware,
independente do SO instalado. No parque de equipamentos, esse campo estava vazio ou
com valor padrao ("Default string"), sem o numero patrimonial de 14 digitos.

A gravacao exige ferramentas especificas do fabricante do BIOS -- o `dmidecode` e
somente leitura. O binario `amidelnx_64` (AMI oficial) foi obtido junto ao
fabricante da plataforma de hardware para uso operacional.

### 1.2 Historico de evolucao do script

| Versao | Data | Marco principal |
|---|---|---|
| 1.0 | 2026-05 | Concepcao inicial: leitura do BBconfig.conf + amibios_dmi sysfs |
| 1.4.0 | 2026-05 | Versao funcional com validacao Modulo 11 e modo standalone |
| 2.0.0 | 2026-06-05 | Reescrita completa: cascata amidelnx_64 + amibios_dmi, modo remoto SSH, log duplo, tabela de resumo |
| 2.0.1 | 2026-06-10 | Bootstrap SSH automatico (gera chave local, distribui via ssh-copy-id sob demanda; `--ssh-pass`, `SSH_PASS` env, `--ssh-pass-file`) |
| 2.0.2 | 2026-06-11 | Fix em `garante_amidelnx_remoto` (deteccao do binario remoto); `scp` agora reporta stderr em falhas; guarda do `resultado_escrita` antes de executar `reinstall-enable` e `reboot` em modo `--production` |
| 2.0.3 | 2026-06-12 | `le_arquivo_hosts` passou a ignorar linhas iniciadas com `#` e comentarios em fim de linha; log local consolidado deixou de ser truncado a cada execucao (modo append com separador entre rodadas) |

---

## 2. Arquitetura da Solucao

### 2.1 Composicao da pasta de trabalho

Todos os arquivos devem estar na mesma pasta (por exemplo `asset_tag_bios/`):

| Arquivo | Obrigatorio | Descricao |
|---|---|---|
| `update_dmi_tag.py` | Sim | Script principal (Python 3.6+, stdlib-only) |
| `amidelnx_64` | Sim | Binario AMI (ELF 64-bit Linux x86_64) |
| `hosts_<cenario>.txt` | Sim (modo remoto) | Lista de hosts (nome livre por cenario) |
| `.ssh_pass` | Recomendado | Arquivo com senha SSH (ver secao 3) |
| `ErrCode.txt` | Recomendado | Tabela de codigos de erro do AMIDE |
| `manual_operacao.md` | Recomendado | Este documento |
| `requirements.txt` | Nao | Somente para desenvolvimento (flake8, black, pytest) |

**Nota importante:** O `amidelnx_64` e um binario ELF 64-bit para Linux x86_64.
Nao e executavel em Windows, mas pode ser mantido na pasta e e copiado automaticamente
pelo script via `scp` para cada host remoto durante a execucao.

**Nao e necessario instalar nenhum modulo Python via pip.** O script usa exclusivamente
a stdlib do Python 3.6+.

### 2.2 Cascata de mecanismos de escrita

O script tenta gravar o Asset Tag por dois mecanismos em sequencia:

```
Mecanismo 1: amidelnx_64 (binario AMI -- tenta primeiro)
  - Copiado via scp para ~/amidelnx_64 no host remoto
  - Executado com sudo
  - Funciona em placas com WSMT presente (maioria do parque atual)
  - Resultado "Done" = sucesso; "Error: N" = falha com codigo especifico

Mecanismo 2: amibios_dmi via sysfs (fallback)
  - Requer modulo kernel amibios-dmi-kmp-default instalado no host
  - Escreve em /sys/firmware/amibios/chassis/asset_tag
  - Funciona somente em placas SEM WSMT (modelos legados)
  - Falha com "SMI error 0x84" em placas com WSMT

[Em avaliacao] Mecanismo 3: AMIDEEFIx64.EFI via UEFI Shell
  - Unica via viavel para Daten DH3UP
  - Pendente de teste e implementacao
```

### 2.3 Requisitos por ambiente

**Na maquina do operador (modo remoto):**
- Python 3.6 ou superior
- `ssh`, `scp`, `ssh-keygen`, `ssh-copy-id` disponiveis no PATH
- Binario `amidelnx_64` no mesmo diretorio do script
- Acesso de rede SSH (porta 22) aos hosts alvo

**Nos hosts alvo:**
- SLED/SLES 15 SP5 a SP7
- Pacote `python3-patrimonial` (opcional, validacao redundante do Modulo 11)
- Pacote `amibios-dmi-kmp-default` (opcional, mecanismo 2)
- Usuario com acesso `sudo` (com ou sem senha)

---

## 3. Autenticacao SSH -- Bootstrap Automatico

Funcionalidade central do v2.0.1, adicionada para eliminar o prerequisito de
configuracao manual de chaves SSH antes do uso.

### 3.1 Fluxo de bootstrap (executado por host, antes do processamento)

```
1. Verifica se existe chave SSH local (~/.ssh/id_rsa ou ~/.ssh/id_ed25519)
2. Se nao existir --> gera id_ed25519 via ssh-keygen (sem passphrase, nao interativo)
3. Tenta conexao SSH com BatchMode=yes (chave ja distribuida)
   --> Caminho feliz: segue processamento normal. Silencioso, sem log extra.
4. Se falhar (chave ainda nao distribuida):
   a. Senha SSH disponivel --> executa ssh-copy-id via pty (confinado nessa funcao)
   b. Sem senha disponivel --> loga ERROR, marca host como INACESSIVEL
5. Apos ssh-copy-id, reconecta e confirma via BatchMode=yes
```

O modulo `pty` (pseudo-terminal, necessario para alimentar a senha no ssh-copy-id)
fica isolado exclusivamente na funcao `_ssh_copy_id_com_senha`. Nenhuma outra parte
do script usa `pty`. Apos o bootstrap, todo o fluxo principal usa `BatchMode=yes`.

**Comportamento nas proximas execucoes:** apos a chave estar distribuida em um host,
o bootstrap detecta isso no passo 3 (caminho feliz) e nao usa mais a senha SSH.
A senha so e necessaria na primeira execucao para cada host novo.

### 3.2 Tres formas de fornecer a senha SSH

Precedencia: `--ssh-pass` > variavel `SSH_PASS` > `--ssh-pass-file`

A forma **recomendada** e a do arquivo com permissao restrita (`--ssh-pass-file`),
detalhada na secao 6. As outras duas formas existem como alternativas e tem implicacoes
de seguranca discutidas la.

### 3.3 Diferenca entre --ssh-pass e --sudo-pass

| Argumento | Finalidade | Quando e usada |
|---|---|---|
| `--ssh-pass` | Senha para CONECTAR via SSH | Apenas no bootstrap (ssh-copy-id) |
| `--sudo-pass` | Senha do sudo dentro do host | Em cada comando privilegiado remoto |

Geralmente sao a mesma senha de rede do operador, mas sao tecnicamente independentes
e servem a propositos diferentes.

---

## 4. Arquivo de Hosts

### 4.1 Formato

A partir da v2.0.3 sao aceitos comentarios iniciados com `#`, tanto em linha
inteira quanto em fim de linha. Linhas em branco continuam ignoradas.

```
# comentario inteiro (linha ignorada)
IP
IP,BEM_NUMERO
IP # comentario trailing apos o IP
IP,BEM_NUMERO # comentario trailing apos o BEM
```

**Exemplos:**
```
# Equipamentos sem BEM na lista -- usa valor do arquivo de configuracao local
192.168.1.10
192.168.1.20 # equip-recepcao

# Equipamentos com BEM fornecido explicitamente na lista
192.168.1.11,9905260010001
192.168.1.21,9905260010002 # equip-financeiro
```

### 4.2 Regra de precedencia do BEM_NUMERO

**Com `IP,BEM_NUMERO` na linha:**
- O valor da lista tem prioridade absoluta
- E gravado na BIOS e atualizado no arquivo de configuracao corporativo remoto
- O valor anterior presente no arquivo de configuracao e registrado no log para auditoria

**Com apenas `IP`:**
- O script le o `BEM_NUMERO` do arquivo de configuracao corporativo no host remoto
- Se ausente ou vazio, o host e marcado como `PENDENTE` (rc=10, estado normal
  de pre-provisionamento)

O nome do arquivo de hosts e livre -- voce pode ter varios arquivos para cenarios
diferentes (`hosts_producao.txt`, `hosts_teste.txt`, `hosts_auditoria.txt`, etc.).

> **Nota sobre nomes:** os identificadores `BBconfig.conf` e `BEM_NUMERO` mencionados
> neste documento refletem os defaults do codigo na versao atual (`DEFAULT_CONFIG_FILE`
> e `DEFAULT_VAR_NAME`). Ambos sao sobrescriviveis em tempo de execucao via `--config`
> e `--var`. Em uma versao futura essas referencias serao genericadas no proprio codigo.

---

## 5. Validacao do Patrimonio -- Modulo 11

O numero patrimonial tem 14 digitos: 13 de base mais 1 digito verificador (DV)
calculado por Modulo 11.

**Multiplicadores (esquerda para direita):** 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2

**Regra:** se o resultado for 10 ou 11, o DV e 0.

O script aceita valores de 13 ou 14 digitos:
- 13 digitos: calcula e anexa o DV automaticamente
- 14 digitos: verifica o DV fornecido e loga discrepancia se diferente

**Nota sobre tamanho:** a versao atual grava sempre 14 digitos (13 base + DV). Caso
o padrao definido para o projeto seja de 13 digitos, essa logica pode ser ajustada via
parametro em versao futura.

Validacao redundante via pacote `python3-patrimonial` (quando instalado no host remoto).

---

## 6. Linhas de Comando -- Referencia Completa

O fluxo recomendado e em **tres etapas**, todas usando o mesmo arquivo de senha SSH
preparado uma unica vez. Cada etapa deve ser conferida no log antes de avancar para
a proxima.

### 6.0 Setup inicial -- Arquivo de senha SSH (uma vez por operador)

Cria o arquivo de senha com permissao restrita ao dono. O `umask 077` garante que o
arquivo nasca com modo 600. Substitua `SENHA_REDE` pela sua senha de rede:

```bash
cd ~/asset_tag_bios
umask 077
echo 'SENHA_REDE' > .ssh_pass
chmod 600 .ssh_pass
```

Apos este passo, a senha **nao aparece** no historico do shell nem em `ps auxf`, e
fica protegida pelo filesystem.

### 6.1 Etapa 1 -- Dry-run com verbose (auditoria, sem alterar nada)

Conecta nos hosts, executa toda a auditoria de ambiente e simula o calculo do tag,
mas **nao grava nada** na BIOS. Use sempre antes de qualquer gravacao real.

```bash
python3 ~/asset_tag_bios/update_dmi_tag.py \
  --hosts ~/asset_tag_bios/hosts.txt \
  --amide-local-path ~/asset_tag_bios/amidelnx_64 \
  --log-local ~/asset_tag_bios/update_dmi_tag_remoto.log \
  --ssh-pass-file ~/asset_tag_bios/.ssh_pass \
  --sudo-pass SENHA_REDE \
  --verbose
```

Conferir no log:
- Cada host com `INFO - sudo detectado:` (com ou sem senha)
- Linha `WARNING - [DRY-RUN]` mostrando o valor que **seria** gravado
- Tabela de resumo ao final sem `FALHOU-todos`

### 6.2 Etapa 2 -- Gravacao real (sem reboot)

So execute apos conferir a Etapa 1. Acrescenta a flag `-w` para habilitar a gravacao
fisica na BIOS. O equipamento **nao reinicia** ao final.

```bash
python3 ~/asset_tag_bios/update_dmi_tag.py \
  --hosts ~/asset_tag_bios/hosts.txt \
  --amide-local-path ~/asset_tag_bios/amidelnx_64 \
  --log-local ~/asset_tag_bios/update_dmi_tag_remoto.log \
  --ssh-pass-file ~/asset_tag_bios/.ssh_pass \
  --sudo-pass SENHA_REDE \
  --write \
  --verbose
```

Conferir no log:
- Cada host com resultado `OK-amidelnx` ou `OK-amibios` na tabela de resumo
- Hosts com `FALHOU-todos` devem ser tratados manualmente antes da Etapa 3

### 6.3 Etapa 3 -- Gravacao real + reinstall-enable + reboot

Use **apenas em janela operacional planejada**. Acrescenta `--production`, que
dispara `reinstall-enable` e `reboot` apos a gravacao bem-sucedida. Desde a v2.0.2,
hosts com falha de gravacao **nao** sao reiniciados (a flag e ignorada para esses
hosts e o motivo fica logado).

```bash
python3 ~/asset_tag_bios/update_dmi_tag.py \
  --hosts ~/asset_tag_bios/hosts.txt \
  --amide-local-path ~/asset_tag_bios/amidelnx_64 \
  --log-local ~/asset_tag_bios/update_dmi_tag_remoto.log \
  --ssh-pass-file ~/asset_tag_bios/.ssh_pass \
  --sudo-pass SENHA_REDE \
  --write \
  --production \
  --verbose
```

### 6.4 Modo standalone (no proprio equipamento, sem SSH)

Para execucao local no equipamento alvo, sem lista de hosts:

```bash
sudo python3 update_dmi_tag.py --write --verbose
```

### 6.5 Alternativas para fornecer a senha SSH (uso esporadico)

As duas formas a seguir existem como alternativas, mas tem implicacoes de seguranca
e nao sao recomendadas para uso rotineiro.

**Alternativa A -- variavel de ambiente:**

A senha nao aparece em `ps auxf`, mas fica no ambiente do shell ate o `unset`. Para
nao registrar no historico, prefixe com espaco (requer `HISTCONTROL=ignorespace`):

```bash
 export SSH_PASS='SENHA_REDE'
python3 ~/asset_tag_bios/update_dmi_tag.py \
  --hosts ~/asset_tag_bios/hosts.txt \
  --amide-local-path ~/asset_tag_bios/amidelnx_64 \
  --log-local ~/asset_tag_bios/update_dmi_tag_remoto.log \
  --sudo-pass SENHA_REDE \
  --verbose
unset SSH_PASS
```

**Alternativa B -- senha na linha de comando (NAO recomendada):**

A senha fica visivel em `ps auxf` enquanto o comando roda **e** no historico do shell.
Use apenas em ambiente isolado de teste:

```bash
python3 ~/asset_tag_bios/update_dmi_tag.py \
  --hosts ~/asset_tag_bios/hosts.txt \
  --amide-local-path ~/asset_tag_bios/amidelnx_64 \
  --log-local ~/asset_tag_bios/update_dmi_tag_remoto.log \
  --ssh-pass SENHA_REDE \
  --sudo-pass SENHA_REDE \
  --verbose
```

### 6.6 Comparativo de seguranca das tres formas

| Forma | Visivel em `ps` | Fica no historico | Persiste no shell | Recomendacao |
|---|---|---|---|---|
| Arquivo (`--ssh-pass-file`) | Nao | Nao | Nao | **Recomendada** |
| Variavel `SSH_PASS` | Nao | So se nao usar espaco antes | Ate `unset` | Esporadica |
| `--ssh-pass SENHA` | **Sim** | **Sim** | Nao | Apenas teste |

---

## 7. Todos os Argumentos

| Argumento | Padrao | Descricao |
|---|---|---|
| `--hosts` | -- | Arquivo de hosts. Ativa modo remoto. |
| `--ssh-user` | usuario da sessao | Usuario SSH para conexao remota |
| `--ssh-pass` | -- | Senha SSH para bootstrap/ssh-copy-id |
| `--ssh-pass-file` | -- | Arquivo com senha SSH na 1a linha |
| `--sudo-pass` | -- | Senha do sudo nos hosts remotos |
| `-c`, `--config` | `/etc/BBconfig.conf` | Caminho do arquivo de configuracao corporativo |
| `-s`, `--var` | `BEM_NUMERO` | Nome da variavel no arquivo de configuracao |
| `--amide-local-path` | `./amidelnx_64` | Caminho local do binario (para scp) |
| `--amide-remote-path` | `~/amidelnx_64` | Caminho do binario no host remoto |
| `--log-file` | `/var/log/update_dmi_tag.log` | Log no host alvo (standalone) |
| `--log-local` | `./update_dmi_tag_remoto.log` | Log local consolidado (modo remoto) |
| `-v`, `--verbose` | False | Exibe mensagens de log no terminal |
| `-w`, `--write` | False | Habilita gravacao fisica. Sem esta flag: Dry Run |
| `--csv` | False | (Standalone) Retorna linha CSV: antigo,config,novo |
| `--production` | False | Executa reinstall-enable e reboot apos gravacao bem-sucedida |
| `--version` | -- | Exibe a versao do script |

**Regras criticas:**
- Sem `--write`: dry-run absoluto, nada e gravado na BIOS
- Sem `--production`: o equipamento nao reinicia apos a gravacao
- `--production` com falha de gravacao: as acoes finais NAO sao executadas (desde v2.0.2)
- `--csv` e incompativel com `--hosts` (modo remoto)
- `--production` sem `--write` nao tem efeito de gravacao

---

## 8. Logs Gerados

### 8.1 Log local consolidado (modo remoto)

- **Arquivo:** `update_dmi_tag_remoto.log` (configuravel via `--log-local`)
- **Local:** maquina do operador, no diretorio de trabalho
- **Conteudo:** historico de todos os hosts, prefixo `[IP]` em cada linha
- **Persistencia:** a partir da v2.0.3, o arquivo e aberto em modo append e
  **nunca e truncado**. Cada execucao acrescenta um bloco novo separado por
  linha em branco do anterior. Se voce quiser arquivar uma rodada antes da
  proxima, mova o arquivo manualmente.

Filtrar por host especifico:
```bash
grep "192.168.1.11" update_dmi_tag_remoto.log
```

### 8.2 Log de alvos (modo remoto)

- **Arquivo:** `update_dmi_tag_alvo.log` (no diretorio de trabalho)
- **Conteudo:** detalhamento por host alvo, gerado localmente

### 8.3 Log remoto (em cada host alvo)

- **Arquivo:** `/var/log/update_dmi_tag.log` (em cada maquina remota)
- **Conteudo:** historico daquele equipamento especifico

### 8.4 Exemplo de saida verbose (dry-run)

```
2026-06-12 10:29:16 - INFO - update_dmi_tag.py v2.0.3 -- MODO REMOTO
2026-06-11 10:29:16 - INFO - Modo  : DRY-RUN (simulacao)
2026-06-11 10:29:36 - [192.168.1.10] - INFO - Hostname   : equip-exemplo-01
2026-06-11 10:29:37 - [192.168.1.10] - INFO - Placa-Mae  : PERTO SA H310M M.2
2026-06-11 10:29:38 - [192.168.1.10] - INFO - BIOS Info  : American Megatrends Inc. F13 PT
2026-06-11 10:29:39 - [192.168.1.10] - INFO - SMBIOS Ver : 3.1.1
2026-06-11 10:29:40 - [192.168.1.10] - INFO - WSMT       : Presente
2026-06-11 10:29:44 - [192.168.1.10] - INFO - Tag atual  : Default String
2026-06-11 10:29:55 - [192.168.1.10] - WARNING - Arquivo de configuracao remoto: BEM_NUMERO ausente (PENDENTE)
2026-06-11 10:29:56 - [192.168.1.10] - INFO - BEM_NUMERO em uso (fonte: lista de hosts): 9905260010001
2026-06-11 10:29:57 - [192.168.1.10] - INFO - Valor possui 13 digitos. DV calculado: 7 (Tag: 99052600100017)
2026-06-11 10:30:03 - [192.168.1.10] - WARNING - [DRY-RUN] valor que seria gravado: 99052600100017
2026-06-11 10:30:04 - [192.168.1.10] - WARNING - [DRY-RUN] Para gravar, passe -w ou --write.
2026-06-11 10:30:05 - [192.168.1.10] - INFO - ====== Fim do processamento: 192.168.1.10 -- DRY-RUN ======
```

### 8.5 Tabela de resumo ao final da execucao

```
| IP           | Hostname         | Placa              | SMBIOS | WSMT    | Tag Antes      | BEM conf | BEM usado     | Tag Depois     | Resultado |
| 192.168.1.10 | equip-exemplo-01 | PERTO SA H310M M.2 | 3.1.1  | Present | Default String | PENDENTE | 9905260010001 | 99052600100017 | DRY-RUN   |
```

> O campo **BEM conf = PENDENTE** indica que o arquivo de configuracao corporativo da
> maquina remota ainda nao tem o `BEM_NUMERO` preenchido. O valor foi fornecido pela
> lista de hosts, que e o comportamento esperado nesse cenario de provisionamento inicial.

---

## 9. Codigos de Resultado na Tabela de Resumo

| Resultado | Significado |
|---|---|
| `OK-amidelnx` | Tag gravada com sucesso via binario AMI |
| `OK-amibios` | Tag gravada com sucesso via sysfs amibios_dmi |
| `DRY-RUN` | Simulacao executada, nenhuma gravacao realizada |
| `FALHOU-todos` | Ambos os mecanismos falharam |
| `PENDENTE` | BEM_NUMERO vazio ou ausente no arquivo de configuracao corporativo |
| `INACESSIVEL` | Host nao respondeu ao SSH ou bootstrap de autenticacao falhou |
| `INVALIDO` | Formato do BEM_NUMERO invalido |

---

## 10. Codigos de Saida do Script

| Codigo | Significado |
|---|---|
| 0 | Sucesso ou Dry Run |
| 1 | Modo remoto: um ou mais hosts falharam |
| 2 | Standalone: falha de integridade pos-escrita |
| 3 | Arquivo nao encontrado |
| 4 | Erro de permissao |
| 5 | Erro de validacao do patrimonio |
| 6 | Todos os mecanismos de escrita falharam |
| 10 | BEM_NUMERO pendente (vazio no arquivo de configuracao corporativo -- estado normal pre-provisionamento) |
| 99 | Erro nao mapeado |

---

## 11. Contexto Tecnico -- WSMT e os Mecanismos de Escrita

### 11.1 O que e a WSMT

A WSMT (Windows SMM Security Mitigation Table) e uma tabela ACPI presente em firmwares
mais novos que ativa protecoes de seguranca no modo SMM (System Management Mode).

O flag `FIXED_COMM_BUFFERS` (bit 0 dos flags `0x07`) impede que enderecos fisicos
arbitrarios passados pelo SO em tempo de execucao sejam aceitos pelo handler SMI da AMI.

### 11.2 Por que o amibios_dmi falha com WSMT presente

O `amibios_dmi` e um modulo kernel open-source (fork de Claudio Matsuoka, 2013) com
melhorias aplicadas pelo autor:
- Suporte SMBIOS 2.0 a 3.x
- Substituicao de `strcpy` por `memcpy` para conformidade com `FORTIFY_SOURCE`
- Correcoes no Makefile

O modulo escreve via sysfs (`/sys/firmware/amibios/chassis/asset_tag`), que internamente
usa o handler SMI da AMI. Com WSMT ativo, o firmware rejeita a chamada com
`SMI error 0x84 (Invalid parameter)`.

Durante a investigacao foram testadas tres zonas de alocacao de buffer (DMA < 16MB,
DMA32 < 4GB, memoria normal) -- todas retornam `0x84` identicamente. O bloqueio e
na camada do handler SMI, nao no buffer.

### 11.3 Por que o amidelnx_64 funciona com WSMT

O `amidelnx_64` e o binario oficial da AMI, obtido junto ao fabricante da plataforma
de hardware. Ele usa um caminho de escrita diferente do modulo kernel open-source,
que nao passa pelo ponto bloqueado pela WSMT. Por isso funciona nos modelos com
WSMT presente.

### 11.4 O caso especial Daten DH3UP

Este modelo apresenta bloqueio em multiplas camadas:

- WSMT ativa bloqueia a camada SMI (amibios_dmi falha com 0x84)
- `CONFIG_STRICT_DEVMEM=y` bloqueia `/dev/mem`
- Kernel lockdown em modo `integrity` (EFI Secure Boot ativo) bloqueia `ioremap`
  e carregamento de modulos nao assinados
- Sem IPMI/BMC presente
- Variaveis `efivarfs` SMBIOS sao ponteiros somente leitura
- `amidelnx_64` retorna `Error 24: Problem allocating BIOS buffer` (bloqueio BIOS)

**Solucao em avaliacao:** `AMIDEEFIx64.EFI` via UEFI Shell pre-boot. O UEFI Shell
executa antes da WSMT entrar em vigor. Fluxo planejado:
1. Copiar `AMIDEEFIx64.EFI` e `shellx64.efi` para a particao EFI
2. Criar `startup.nsh` com o comando de gravacao + `reset`
3. Registrar entrada de boot via `efibootmgr --bootnext` (execucao unica)
4. Reiniciar -- o equipamento retorna ao boot normal automaticamente

### 11.5 Sobre o amidelnx_64 -- e open-source?

Nao existe equivalente open-source funcional. O `amidelnx_64` e proprietario da AMI
Aptio, distribuido somente a parceiros OEM/ODM. Alternativas open-source existentes:

| Ferramenta | Tipo | Escreve DMI? | Observacao |
|---|---|---|---|
| `dmidecode` | Open source (GPL) | Nao | Somente leitura |
| `efivar` / `efibootmgr` | Open source | Nao | Vars EFI genericas |
| `fwupd` / LVFS | Open source | Nao | Firmware updates |
| EDK2 (gnu-efi) | Open source (BSD) | Potencial | Framework UEFI customizado |

O caminho open-source viavel de longo prazo e um aplicativo UEFI desenvolvido com EDK2
usando o `EFI_SMBIOS_PROTOCOL` nativo para escrever o asset tag em pre-boot.

---

## 12. Compatibilidade por Modelo de Placa-Mae

Resultados de testes reais em equipamentos do parque (atualizado em 2026-06-12):

| Modelo | BIOS | SMBIOS | WSMT | amidelnx_64 | amibios_dmi | Status |
|---|---|---|---|---|---|---|
| Gigabyte GA-H110TN-M | AMI Aptio V | 3.0.0 | Ausente | OK | OK | **Funciona** |
| PERTO SA H310M M.2 | AMI Aptio V | 3.1.1 | Presente | OK | SMI 0x84 | **Funciona** |
| ASUS PRIME H610M-E D4 | AMI Aptio V | 3.4.0 | Presente | OK | SMI 0x84 | **Funciona** |
| Daten DH4UP | AMI Aptio V | --- | Presente | OK | SMI 0x84 | **Funciona** |
| Daten DH3UP | AMI Aptio V | 3.1.1 | Presente | Erro 24 | SMI 0x84 | **Nao funciona** |
| Daten H4U02PER | AMI Aptio V | 3.2.0 | Presente | Erro 24 | erro escrita | **Nao funciona** |

**Resumo:**
- **4 modelos funcionam** (Gigabyte GA-H110TN-M, PERTO SA H310M M.2, ASUS PRIME H610M-E D4, Daten DH4UP), todos pela cascata automatica do script. O `amidelnx_64` resolve todos os casos, o `amibios_dmi` funciona apenas na Gigabyte (unico modelo sem WSMT).
- **2 modelos nao funcionam** (Daten DH3UP e Daten H4U02PER). Ambos apresentam `Error 24: Problem allocating BIOS buffer` no `amidelnx_64` e falha de escrita no `amibios_dmi`. Causa raiz unica: combinacao WSMT + `CONFIG_STRICT_DEVMEM=y` + kernel lockdown em modo `integrity` (Secure Boot ativo) impede a alocacao de buffer fisico necessario ao handler SMI. Sem solucao via SO; em avaliacao via `AMIDEEFIx64.EFI` por UEFI Shell pre-boot (detalhes na secao 11.4).

---

## 13. Sudo Remoto -- Comportamento

O script detecta automaticamente o tipo de sudo de cada host:

1. Tenta `sudo -n true` (sem senha)
2. Se falhar e `--sudo-pass` fornecido, testa `echo SENHA | sudo -S true`
3. Loga o resultado: `sudo detectado: sem senha` ou `sudo detectado: com senha`

O banner corporativo exibido no login SSH e filtrado de toda saida de comandos
antes do processamento, via funcao interna `_filtra_banner()`.

---

## 14. Auditoria Pos-Gravacao

Apos a gravacao bem-sucedida, o valor novo so e visivel via `dmidecode` ou pelo
sysfs **apos o proximo reboot** do equipamento. Isso porque tanto `dmidecode` quanto
`/sys/class/dmi/id/chassis_asset_tag` sao snapshots da tabela SMBIOS carregada no boot.

Para conferencia **imediata** (antes do reboot), use o proprio binario AMI lendo direto
do chip:

```bash
sudo ~/amidelnx_64 /AT
```

Para conferencia **apos reboot**:

```bash
sudo dmidecode -s chassis-asset-tag
cat /sys/class/dmi/id/chassis_asset_tag
```

Os dois devem retornar o mesmo valor de 14 digitos.

---

## 15. Proximos Passos

| Item | Prioridade | Status |
|---|---|---|
| Validacao do AMIDEEFIx64.EFI no Daten DH3UP | Alta | Em avaliacao |
| Alinhamento sobre tamanho do campo: 13 ou 14 digitos | Alta | Em discussao |
| Empacotamento como RPM para distribuicao automatizada | Media | Planejado |
| Modo standalone via ferramenta corporativa em producao | Media | Planejado |
| Generacao das constantes `DEFAULT_CONFIG_FILE` e `DEFAULT_VAR_NAME` no codigo | Media | Planejado |
| Avaliacao de aplicativo UEFI open-source (EDK2) | Baixa | Conceitual |

---

## 16. Referencia de Arquivos por Versao do Script

| Arquivo | Versao atual |
|---|---|
| `update_dmi_tag.py` | 2.0.3 (2026-06-12) |
| `survey_asset_tag.bash` | 1.3.0 (script de auditoria de parque) |
| `manual_operacao.md` | Este documento (2026-06-12) |
