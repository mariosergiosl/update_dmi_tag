# Update DMI Tag

Utilitario para validacao de patrimonio e gravacao do campo DMI Asset Tag na BIOS AMI.

## Visao Geral

O `update_dmi_tag.py` e uma ferramenta desenvolvida em Python para ler um numero de patrimonio de 13 ou 14 digitos (de arquivos locais ou remotos), validar o digito verificador usando o algoritmo de Modulo 11 (Banco do Brasil) e gravar o valor no campo DMI Asset Tag da BIOS.

A gravacao e feita em cascata de forma automatica:
1. **amidelnx_64**: Binario proprietario da AMI (tentativa inicial).
2. **amibios_dmi**: Modulo de kernel via sysfs (fallback para placas Gigabyte/sem WSMT).

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

### 1. Execucao Local (Dry-Run de seguranca por padrao)
```bash
python3 update_dmi_tag.py
```

### 2. Execucao Local Gravando na BIOS
```bash
python3 update_dmi_tag.py --production
```

### 3. Execucao Remota em lote de hosts
```bash
python3 update_dmi_tag.py --hosts hosts.txt
```

---

## Resumo de Codigos de Retorno (Exit Codes)

* **0**: Sucesso (Tag gravada ou ja atualizada).
* **10**: Patrimonio pendente (BEM_NUMERO ausente ou vazio).
* **Outros**: Falha na execucao ou na gravacao BIOS.
