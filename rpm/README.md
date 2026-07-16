# RPMs do modulo amibios_dmi (Mecanismo 2)

Language / Idioma: English | Portugues

Estes dois `.rpm` sao o build empacotado do fork open-source
[mariosergiosl/amibios_dmi](https://github.com/mariosergiosl/amibios_dmi)
(GPLv2, baseado no trabalho original de Claudio Matsuoka). Diferente de
`amidelnx_64`/`AMIDEEFIx64.EFI`, este NAO e software sob NDA: pode ser
versionado e distribuido livremente junto com o projeto.

## Arquivos

| Arquivo | Conteudo | Kernel-alvo |
|---|---|---|
| `amibios-dmi-1.0.0.rpm` | Ferramentas userspace (sem dependencia externa) | Nenhum (independente de kernel) |
| `amibios-dmi-kmp-default-6.4.0-150700.51.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `6.4.0-150700.51-default` (SLES 15 SP7) |

O KMP e compilado contra a tabela de simbolos exata (`ksym(...)`) de um
kernel especifico: nao carrega em nenhum outro build, mesmo que seja
uma versao proxima (confirmado em teste real: falha com
`nada fornece 'ksym(default:firmware_kobj) = ...'` quando o kernel do
host nao bate exatamente). Nao existe workaround (forcar a instalacao
com `--nodeps`/`rpm -ivh --nodeps` faz o pacote "aparecer" instalado no
banco de dados do rpm, mas o `.ko` fica no diretorio do kernel errado e
o `modprobe` continua falhando com "Module not found").

## Como o `update_dmi_tag` usa isso

`update_dmi_tag/environment.py` (`instala_modulo_remoto`) localiza os
arquivos aqui por padrao de nome (`amibios-dmi-kmp-default-*.rpm` e
`amibios-dmi-[0-9]*.rpm`), copia via `scp` para o host remoto, confere o
SHA-256 da copia antes de prosseguir, e instala via
`zypper install <caminho-local>`, sem depender de nenhum repositorio
remoto/OBS estar acessivel a partir do host de destino.

## Gerando um novo build para outro kernel/SP

Se a frota tiver hosts em outra versao de SLES/kernel, e preciso compilar
um novo KMP para aquele kernel especifico e adicionar aqui, mantendo o
padrao de nome `amibios-dmi-kmp-default-<versao-do-kernel>.rpm`:

```bash
git clone https://github.com/mariosergiosl/amibios_dmi.git
cd amibios_dmi
uname -r   # confirmar a versao exata do kernel-alvo
sudo zypper in -y kernel-default-devel kernel-syms kernel-source
cd /lib/modules/$(uname -r)/build
sudo make modules_prepare
cd /path/to/amibios_dmi
make clean && make
# empacotar como KMP (ver Makefile/spec do fork) e copiar o .rpm
# resultante para esta pasta
```

Ver o `README.md`/`README.pt-BR.md` do fork para detalhes completos de
compilacao e empacotamento.

---

# RPMs for the amibios_dmi module (Mechanism 2)

These two `.rpm` files are the packaged build of the open-source fork
[mariosergiosl/amibios_dmi](https://github.com/mariosergiosl/amibios_dmi)
(GPLv2, based on the original work by Claudio Matsuoka). Unlike
`amidelnx_64`/`AMIDEEFIx64.EFI`, this is NOT NDA-restricted software:
it can be freely versioned and distributed with the project.

See the section above for file listing, kernel-targeting details, how
`update_dmi_tag` uses these files, and how to build a new KMP for a
different kernel/SP if the fleet needs it.
