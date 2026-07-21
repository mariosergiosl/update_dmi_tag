# RPMs do modulo amibios_dmi (Mecanismo 2)

Language / Idioma: English | Portugues

Estes `.rpm` sao o build empacotado do fork open-source
[mariosergiosl/amibios_dmi](https://github.com/mariosergiosl/amibios_dmi)
(GPLv2, baseado no trabalho original de Claudio Matsuoka). Diferente de
`amidelnx_64`/`AMIDEEFIx64.EFI`, este NAO e software sob NDA: pode ser
versionado e distribuido livremente junto com o projeto.

Desde 2026-07-20, o build da linha SLE 15 (e Leap) e feito no projeto
publico do OBS
[home:mariosergiosl:amibios_dmi](https://build.opensuse.org/project/show/home:mariosergiosl:amibios_dmi),
que compila o mesmo fonte contra varios kernels-alvo a partir de um
unico `.spec` (macro `%kernel_module_package`), sem precisar de VM/ISO
fisica para cada versao.

Desde 2026-07-21, a linha SLE 12 completa (SP2 a SP5) e coberta por um
segundo metodo, feito fora do OBS (ver "Como foram gerados os KMPs da
SLE 12" abaixo): o OBS publico so tem o kernel GA de cada SP da SLE 12,
e o OBS interno do BB nao tem canal de update mirrorado para essa linha.

## Arquivos

Esta pasta tem hoje **148 KMPs** (um por versao de kernel) mais o RPM
userspace, agrupados por linha/SP:

| Linha/SP | Kernel(s) | Qtde KMPs | Origem |
|---|---|---|---|
| SLES 12 SP5 (GA) | `4.12.14-120` | 1 | OBS publico |
| SLES 12 SP5 (manutencao) | `4.12.14-122.7` a `4.12.14-122.231` | 60 | Mirror RMT + compilacao nativa (VM SLES 12 SP5 real) |
| SLES 12 SP4 | `4.12.14-95.3` a `4.12.14-95.54` | 14 | Mirror RMT + compilacao nativa |
| SLES 12 SP3 | `4.4.82-6.3` a `4.4.180-94.100` | 27 | Mirror RMT + compilacao nativa |
| SLES 12 SP2 | `4.4.21-81` a `4.4.120-92.70` | 20 | Mirror RMT + compilacao nativa |
| SLES 15 SP1 | `4.12.14-195` | 1 | OBS publico |
| SLES 15 SP2 | `5.3.18-22` | 1 | OBS publico |
| SLES 15 SP5 | `5.14.21-150500.53` (GA) a `.55.88` (manutencao) | 20 | OBS publico (GA) + mirror RMT (19 patch-levels) |
| SLES 15 SP6 | `6.4.0-150600.21` | 1 | OBS publico |
| SLES 15 SP7 | `6.4.0-150700.51` | 1 | OBS publico |
| openSUSE Leap 15.3 | `5.3.18-57` | 1 | OBS publico |
| openSUSE Leap 15.4 | `5.14.21-150400.22` | 1 | OBS publico |
| `amibios-dmi-1.0.0.rpm` | Ferramentas userspace (sem dependencia externa; hoje so contem doc) | Nenhum (independente de kernel) | 1 |

Nomenclatura de cada arquivo: `amibios-dmi-kmp-default-<kernel-alvo>.rpm`,
onde `<kernel-alvo>` e exatamente o valor de `/proc/sys/kernel/osrelease`
do host, sem o sufixo `-default` (ex.: kernel `4.4.74-92.38-default` ->
arquivo `amibios-dmi-kmp-default-4.4.74-92.38.rpm`). Essa correspondencia
exata e o que `environment.py` usa para escolher o arquivo certo (ver
"Como o `update_dmi_tag` usa isso" abaixo).

SLES 11 SP4 continua sem KMP utilizavel: falha por incompatibilidade do
spec com o RPM antigo dessa versao (`%{buildroot}` nao expande, ver
historico do projeto). SLE 12 GA e SP1 (kernel 3.12.x) tambem ficaram de
fora: o `kernel-syms` dessa era exige tambem `kernel-xen-devel`
instalado (nao baixamos esse flavor, ja que so usamos `default`), e
nenhum host de campo roda kernel tao antigo -- baixa prioridade.

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

## Gerando um novo build para SLE 15/Leap (via OBS)

Se a frota tiver hosts em outra versao de SLES 15/openSUSE nao coberta
pelos repos atuais do projeto OBS, adicione um repositorio novo (ex.
`SUSE:SLE-15-SP4:GA`) em
[home:mariosergiosl:amibios_dmi](https://build.opensuse.org/project/show/home:mariosergiosl:amibios_dmi),
force o rebuild do pacote `amibios-dmi` e baixe o `.rpm` resultante
(`osc api /build/home:mariosergiosl:amibios_dmi/<repo>/x86_64/amibios-dmi/<arquivo>`),
renomeando para o padrao `amibios-dmi-kmp-default-<versao-do-kernel>.rpm`
antes de colocar aqui.

## Como foram gerados os KMPs da SLE 12 (mirror RMT, sem OBS)

O OBS (publico e o interno do BB) so tem o kernel **GA** de cada SP da
SLE 12 (nenhum canal de update mirrorado para essa linha). Os 121 KMPs
de manutencao da SLE 12 (SP2 a SP5) foram gerados em 2026-07-21 usando
o mirror RMT interno do BB (`zypper.intranet.bb.com.br`), que tem o
historico completo de patches de `kernel-default-devel`/`kernel-syms`/
`kernel-devel`, organizado em
`/var/lib/rmt/public/repo/SUSE/Updates/SLE-SERVER/<SP>/x86_64/update/`
(`kernel-default-devel`/`kernel-syms` em `.../update/x86_64/`,
`kernel-devel` (noarch) em `.../update/noarch/`).

**Por que nao dá pra compilar numa maquina SLE 15/SLED 15** (testado e
confirmado o erro): o `kernel-default-devel` da SLE 12 depende de
`libcrypto.so.1.0.0` (OpenSSL antigo, era da SLE 12), que a SLE 15 nao
tem instalado. **A compilacao precisa rodar numa maquina SLE 12 de
verdade** (usamos a VM de lab `sles12_1`, SLES 12 SP5, ver
`project_lab_vms_topologia` no historico do projeto).

Passo a passo (executado por SP, um de cada vez, para nao esgotar
disco/metadados do BTRFS numa VM pequena):

```bash
# 1. No servidor do mirror (via SSH), gerar um tar com os 3 pacotes de
#    cada versao de kernel disponivel para o SP desejado (exemplo: SP2).
#    O filtro '[0-9]*' exclui outros flavors (ex.: kernel-syms-azure-*).
ssh -q usuario@zypper.intranet.bb.com.br "
  mkdir /tmp/sp_kmp_src
  find /var/lib/rmt/public/repo/SUSE/Updates/SLE-SERVER/12-SP2/x86_64/update/ \
    -type f \( -name 'kernel-default-devel-[0-9]*.x86_64.rpm' \
            -o -name 'kernel-syms-[0-9]*.x86_64.rpm' \
            -o -name 'kernel-devel-[0-9]*.noarch.rpm' \) \
    -exec cp {} /tmp/sp_kmp_src/ \;
  cd /tmp && tar cf sp2_kernel_devel.tar sp_kmp_src
"

# 2. Trazer o tar para a maquina local e depois para a VM SLE 12 de
#    compilacao (evite gravar o tar inteiro no disco da VM se ela for
#    pequena; streaming direto poupa espaco):
scp usuario@zypper.intranet.bb.com.br:/tmp/sp2_kernel_devel.tar .
cat sp2_kernel_devel.tar | ssh usuario@vm-sles12 \
  "mkdir -p ~/rpms_sp2 && tar xf - -C ~/rpms_sp2 --strip-components=1"

# 3. Na VM SLE 12, para CADA versao de kernel encontrada, instalar,
#    compilar e DESINSTALAR antes de ir para a proxima (headers
#    instalados ocupam ~80-100MB cada; instalar todas de uma vez em VM
#    pequena esgota o disco/metadados do BTRFS mesmo com espaco "livre"
#    aparente -- ver nota abaixo):
cd ~/rpms_sp2
for f in kernel-default-devel-*.x86_64.rpm; do
  KV=$(echo "$f" | sed -E "s/^kernel-default-devel-(.+)\.[0-9]+\.x86_64\.rpm$/\1/")
  sudo rpm -ivh --oldpackage --replacepkgs \
    kernel-default-devel-${KV}.*.x86_64.rpm \
    kernel-syms-${KV}.*.x86_64.rpm \
    kernel-devel-${KV}.*.noarch.rpm
  sudo ln -sfn linux-$KV /usr/src/linux
  sudo ln -sfn ../../linux-$KV-obj/x86_64/default /usr/src/linux-obj/x86_64/default
  rpmbuild -ba ~/rpmbuild/SPECS/amibios-dmi.spec
  cp ~/rpmbuild/RPMS/x86_64/amibios-dmi-kmp-default-1.0.0_k*.rpm \
     ~/kmp_output/amibios-dmi-kmp-default-${KV}.rpm
  # nome exato dos pacotes instalados (para o erase nao ficar ambiguo
  # com outras versoes eventualmente presentes):
  PKGS=$(rpm -qa | grep -E "(default-devel|syms|devel)-${KV}[.-]")
  sudo rpm -e $PKGS
done
```

**Nota sobre "No space left on device" com espaco livre aparente**: em
VMs pequenas com BTRFS, instalar/desinstalar muitos pacotes pequenos
(as arvores de kernel-source tem dezenas de milhares de arquivos)
esgota o chunk de **metadados** do BTRFS mesmo com o chunk de **dados**
tendo espaco livre (`btrfs filesystem usage /` mostra "Device
unallocated: 0" quando isso acontece). O erase de todo pacote de kernel
apos cada build (passo 3 acima) evita esse problema; se acontecer mesmo
assim, libere espaco real (delete arquivos grandes, `zypper clean`) e
tente `btrfs balance start -dusage=50 /` para realocar chunks.

O `.spec` embute a versao do kernel automaticamente no nome do RPM
gerado (formato `amibios-dmi-kmp-default-1.0.0_k<kernel>-0.x86_64.rpm`);
o passo final de `cp` acima ja renomeia para o padrao simples usado
nesta pasta (`amibios-dmi-kmp-default-<kernel>.rpm`).

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
