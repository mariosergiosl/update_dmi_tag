# Update DMI Tag

Utilitario para validacao de patrimonio e gravacao do campo DMI Asset Tag na BIOS AMI.

## Visao Geral

O `update_dmi_tag.py` e uma ferramenta desenvolvida em Python para ler um numero de patrimonio de 13 ou 14 digitos (de arquivos locais ou remotos), validar o digito verificador usando o algoritmo de Modulo 11 e gravar o valor no campo DMI Asset Tag da BIOS.

A gravacao e feita em cascata de forma automatica:
1. **amidelnx_64**: Binario proprietario da AMI (tentativa inicial).
2. **amibios_dmi**: Modulo de kernel via sysfs (fallback para placas Gigabyte/sem WSMT). O desenvolvimento e detalhes deste modulo do kernel estao no projeto [amibios_dmi](https://github.com/mariosergiosl/amibios_dmi).

O utilitario suporta execucao local (standalone) e execucao remota em lote (lista de IPs via SSH). Oferece modo Dry-Run por padrao.

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

### 3. Setup dos Arquivos de Entrada
* **host.txt**: Insira os enderecos IP dos hosts alvos, um por linha.
* **.ssh_pass**: Insira a senha do seu usuario LDAP (utilizada para conexao SSH automatica).

---

## Documentacao Detalhada

Para informacoes completas sobre comandos, arquitetura, cenarios de teste e troubleshoot, consulte o [manual_operacao.md](manual_operacao.md).

---

## Resumo de Codigos de Retorno (Exit Codes)

* **0**: Sucesso (Tag gravada ou ja atualizada).
* **10**: Patrimonio pendente (BEM_NUMERO ausente ou vazio).
* **Outros**: Falha na execucao ou na gravacao BIOS.
