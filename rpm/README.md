# RPMs do modulo amibios_dmi (Mecanismo 2)

Language / Idioma: English | Portugues

Estes `.rpm` sao o build empacotado do fork open-source
[mariosergiosl/amibios_dmi](https://github.com/mariosergiosl/amibios_dmi)
(GPLv2, baseado no trabalho original de Claudio Matsuoka). Diferente de
`amidelnx_64`/`AMIDEEFIx64.EFI`, este NAO e software sob NDA: pode ser
versionado e distribuido livremente junto com o projeto.

Desde 2026-07-20, o build e feito no projeto publico do OBS
[home:mariosergiosl:amibios_dmi](https://build.opensuse.org/project/show/home:mariosergiosl:amibios_dmi),
que compila o mesmo fonte contra varios kernels-alvo a partir de um
unico `.spec` (macro `%kernel_module_package`), sem precisar de VM/ISO
fisica para cada versao.

## Arquivos

| Arquivo | Conteudo | Kernel-alvo |
|---|---|---|
| `amibios-dmi-1.0.0.rpm` | Ferramentas userspace (sem dependencia externa; hoje so contem doc) | Nenhum (independente de kernel) |
| `amibios-dmi-kmp-default-4.12.14-120.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `4.12.14-120-default` (SLES 12 SP5, kernel GA, compilado no OBS) |
| `amibios-dmi-kmp-default-4.12.14-122.231.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `4.12.14-122.231-default` (SLES 12 SP5, kernel de manutencao posterior ao GA; compilado manualmente numa VM real registrada via SCC, ja que o OBS, publico ou interno, so tem o kernel GA acima disponivel) |
| `amibios-dmi-kmp-default-4.12.14-195.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `4.12.14-195-default` (SLES 15 SP1) |
| `amibios-dmi-kmp-default-5.3.18-22.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `5.3.18-22-default` (SLES 15 SP2) |
| `amibios-dmi-kmp-default-5.3.18-57.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `5.3.18-57-default` (openSUSE Leap 15.3) |
| `amibios-dmi-kmp-default-5.14.21-150400.22.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `5.14.21-150400.22-default` (openSUSE Leap 15.4) |
| `amibios-dmi-kmp-default-5.14.21-150500.53.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `5.14.21-150500.53-default` (SLES 15 SP5) |
| `amibios-dmi-kmp-default-6.4.0-150600.21.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `6.4.0-150600.21-default` (SLES 15 SP6) |
| `amibios-dmi-kmp-default-6.4.0-150700.51.rpm` | Modulo de kernel (`amibios_dmi.ko`) | `6.4.0-150700.51-default` (SLES 15 SP7) |

SLES 11 SP4 e SLED/SLES 12 SP2 tambem tem repositorio configurado no
projeto OBS, mas sem KMP utilizavel: SLE 11 SP4 falha por
incompatibilidade do spec com o RPM antigo dessa versao (`%{buildroot}`
nao expande, ver historico do projeto); SLES 12 SP2 so tem o kernel GA
disponivel para build (nem no OBS publico nem no interno do BB tem o
kernel de manutencao real desses hosts em campo), sem solucao no
momento.

O KMP e compilado contra a tabela de simbolos exata (`ksym(...)`) de um
kernel especifico: nao carrega em nenhum outro build, mesmo que seja
uma versao proxima (confirmado em teste real: falha com
`nada fornece 'ksym(default:firmware_kobj) = ...'` quando o kernel do
host nao bate exatamente). Nao existe workaround (forcar a instalacao
com `--nodeps`/`rpm -ivh --nodeps` faz o pacote "aparecer" instalado no
banco de dados do rpm, mas o `.ko` fica no diretorio do kernel errado e
o `modprobe` continua falhando com "Module not found"). Por isso agora
mantemos um KMP por SP nesta pasta, em vez de um unico arquivo.

## Como o `update_dmi_tag` usa isso

`update_dmi_tag/environment.py` (`instala_modulo_remoto`) localiza os
candidatos a KMP aqui por padrao de nome (`amibios-dmi-kmp-default-*.rpm`),
le o kernel real do host remoto (`/proc/sys/kernel/osrelease` via SSH) e
escolhe apenas o arquivo cujo nome contem esse kernel exato. Se nenhum
candidato bater, para com um erro claro no log em vez de tentar
zypper/modprobe (que falhariam de qualquer forma). O `amibios-dmi-[0-9]*.rpm`
userspace, se presente, e copiado junto. Ambos vao via `scp` para o host
remoto, tem o SHA-256 conferido antes de prosseguir, e sao instalados via
`zypper install <caminho-local>`, sem depender de nenhum repositorio
remoto/OBS estar acessivel a partir do host de destino.

## Gerando um novo build para outro kernel/SP

Se a frota tiver hosts em outra versao de SLES/kernel nao coberta pelos
repos atuais do projeto OBS, adicione um repositorio novo (ex.
`SUSE:SLE-15-SP4:GA`) em
[home:mariosergiosl:amibios_dmi](https://build.opensuse.org/project/show/home:mariosergiosl:amibios_dmi),
force o rebuild do pacote `amibios-dmi` e baixe o `.rpm` resultante
(`osc api /build/home:mariosergiosl:amibios_dmi/<repo>/x86_64/amibios-dmi/<arquivo>`),
renomeando para o padrao `amibios-dmi-kmp-default-<versao-do-kernel>.rpm`
antes de colocar aqui.

Alternativa manual (sem OBS), caso precise validar um kernel fora dos
repos publicos do SUSE:

```bash
git clone https://github.com/mariosergiosl/amibios_dmi.git
cd amibios_dmi
uname -r   # confirmar a versao exata do kernel-alvo
sudo zypper in -y kernel-default-devel kernel-syms kernel-source
cd /lib/modules/$(uname -r)/build
sudo make modules_prepare
cd /path/to/amibios_dmi
make clean && make
# empacotar como KMP (ver amibios-dmi.spec no repo) e copiar o .rpm
# resultante para esta pasta
```

Ver o `README.md`/`README.pt-BR.md` do fork para detalhes completos do
driver.

---

# RPMs for the amibios_dmi module (Mechanism 2)

These `.rpm` files are the packaged build of the open-source fork
[mariosergiosl/amibios_dmi](https://github.com/mariosergiosl/amibios_dmi)
(GPLv2, based on the original work by Claudio Matsuoka). Unlike
`amidelnx_64`/`AMIDEEFIx64.EFI`, this is NOT NDA-restricted software:
it can be freely versioned and distributed with the project.

Since 2026-07-20, builds run on the public OBS project
[home:mariosergiosl:amibios_dmi](https://build.opensuse.org/project/show/home:mariosergiosl:amibios_dmi),
which compiles the same source against several target kernels from a
single `.spec` (`%kernel_module_package` macro), with no need for a
physical/virtual machine per kernel version.

See the section above for file listing, kernel-targeting details, how
`update_dmi_tag` uses these files, and how to build a new KMP for a
different kernel/SP if the fleet needs it.
