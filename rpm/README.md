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

Desde 2026-07-21, a linha SLE 12 completa (SP1 a SP5) e coberta por um
segundo metodo, feito fora do OBS (ver "Como foram gerados os KMPs da
SLE 12" abaixo): o OBS publico so tem o kernel GA de cada SP da SLE 12,
e um eventual OBS interno corporativo pode nao ter canal de update
mirrorado para essa linha.

## Arquivos

Esta pasta tem hoje **163 KMPs** (um por versao de kernel) mais o RPM
userspace, agrupados por linha/SP:

| Linha/SP | Kernel(s) | Qtde KMPs | Origem |
|---|---|---|---|
| SLES 12 SP5 (GA) | `4.12.14-120` | 1 | OBS publico |
| SLES 12 SP5 (manutencao) | `4.12.14-122.7` a `4.12.14-122.231` | 60 | Mirror RMT + compilacao nativa (VM SLES 12 SP5 real) |
| SLES 12 SP4 | `4.12.14-95.3` a `4.12.14-95.54` | 14 | Mirror RMT + compilacao nativa |
| SLES 12 SP3 | `4.4.82-6.3` a `4.4.180-94.100` | 27 | Mirror RMT + compilacao nativa |
| SLES 12 SP2 | `4.4.21-81` a `4.4.120-92.70` | 20 | Mirror RMT + compilacao nativa |
| SLES 12 SP1 | `3.12.51-60.20` a `3.12.74-60.64.40` | 15 | Mirror RMT + compilacao nativa (requer tambem `kernel-xen-devel`, ver nota abaixo) |
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
historico do projeto). SLE 12 GA (kernel 3.12.x, anterior ao SP1) segue
de fora -- baixa prioridade.

**Nota sobre SLE 12 SP1**: o `kernel-syms` dessa era exige tambem
`kernel-xen-devel` da mesma versao instalado (dependencia do proprio
pacote, mesmo so usando o flavor `default`), e a maquina de compilacao
precisa estar livre de qualquer `kernel-default-devel`/`kernel-source`
mais novo instalado (um pacote mais novo pode ter uma declaracao
`Obsoletes` que bloqueia a instalacao do `kernel-xen-devel` antigo).

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
`zypper install --no-refresh <caminho-local>`, sem depender de nenhum
repositorio remoto/OBS estar acessivel a partir do host de destino.

**Fallback `rpm -i --nodeps` (2026-07-22)**: se o `zypper install`
falhar mesmo assim (bug real de campo: servico zypper corporativo
quebrado num host SLED 12 SP2, ou dependencia de infraestrutura ausente
no repositorio do host, ex. `suse-kernel-rpm-scriptlets`), o codigo
tenta `rpm -i --nodeps` antes de desistir. Seguro nesse ponto porque o
kernel ja foi confirmado exatamente compativel com o KMP antes de
chegar aqui -- o `--nodeps` so ignora a checagem administrativa de
dependencias, nao afeta o funcionamento do modulo.

**Confirmacao de kernel do pacote ja instalado (2026-07-22)**: antes de
aceitar "pacote ja instalado" (via `rpm -q`, que so confere o NOME),
`confirma_kmp_kernel_correto_remoto` le a `%{VERSION}` do pacote
instalado e confere se o kernel embutido nela bate com o kernel real do
host. Reconhece tanto o formato de versao dos builds manuais
(`1.0.0_k<kernel>`) quanto o dos builds publicados via OBS
(`1.0.0+git<data>_k<kernel>`) -- antes disso, pacotes do OBS caiam
sempre no ramo "formato inesperado" e a checagem de kernel era pulada
(assumia correto sem confirmar de fato, bug real constatado em campo
nos hosts que usam o pacote publicado via OBS). Se o kernel nao bater
(ex.: residuo de uma instalacao anterior malsucedida ou de um teste
manual), desinstala o pacote errado automaticamente e trata como
ausente, para o fluxo normal reinstalar o KMP certo -- sem isso, o
script ficaria "preso" tentando `modprobe` num pacote que nunca vai
carregar.

**Remocao do pacote pre-existente antes de instalar (2026-07-22)**:
alem do KMP, `instala_modulo_remoto` agora remove qualquer versao
pre-existente do pacote userspace (`amibios-dmi`) antes de tentar
instalar (`zypper remove`, fallback `rpm -e --nodeps`). Bug real de
campo: um pacote userspace de build de outra Service Pack ja estava
instalado num host e bloqueava tanto o `zypper install` quanto o
fallback `rpm -i` (mesmo NOME+ARQUITETURA presente, release diferente
-- sem `--replacepkgs` o `rpm` recusa reinstalar por cima). A checagem
de kernel acima so cobria o KMP; o pacote userspace nunca era
conferido. Essa remocao previa garante que a instalacao seguinte sempre
comeca de um estado limpo, independente do que sobrou de execucoes
anteriores.

**Alvo sempre limpo ao final da execucao (2026-07-22)**: o KMP e o
pacote userspace so permanecem instalados no host apos a execucao se
ja estavam la, corretos, antes dela comecar. Se foi a propria execucao
que instalou o pacote (nada estava presente, ou o que estava presente
era da versao errada), nova funcao `desinstala_modulo_remoto` remove os
dois pacotes ao final (descarrega o modulo via `modprobe -r`, depois
`zypper remove` com o mesmo fallback `rpm -e --nodeps`), independente
do resultado da gravacao da tag. O host nunca acumula um KMP que nao
existia ali antes de rodarmos a ferramenta.

**`depmod -a` explicito apos instalar (2026-07-22)**: em hosts sem o
pacote `suse-kernel-rpm-scriptlets`, o pacote instalava com sucesso
(zypper ou o fallback `rpm -i --nodeps`), mas o `modprobe` seguinte
falhava com "Module not found". Esse pacote fornece o helper que os
scriptlets `%post` do KMP chamam para atualizar o cache do `depmod`
apos a instalacao; sem ele, o `.ko` fica no lugar certo, mas o
`modprobe` (que resolve nomes de modulo por esse cache, nao varrendo o
filesystem) nunca o encontra. O codigo agora roda `depmod -a`
explicitamente logo apos confirmar a instalacao, o que resolve isso sem
precisar desse pacote estar disponivel no repositorio do host --
inocuo quando os scriptlets ja rodaram certo (so recalcula o mesmo
cache de novo).

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

O OBS (publico e um eventual interno corporativo) so tem o kernel **GA**
de cada SP da SLE 12 (nenhum canal de update mirrorado para essa linha).
Os 136 KMPs de manutencao da SLE 12 (SP1 a SP5) foram gerados em
2026-07-21/22 usando um mirror RMT interno (`<host-do-mirror-interno>`),
que tem o historico completo de patches de `kernel-default-devel`/
`kernel-syms`/`kernel-devel`, organizado em
`/var/lib/rmt/public/repo/SUSE/Updates/SLE-SERVER/<SP>/x86_64/update/`
(`kernel-default-devel`/`kernel-syms` em `.../update/x86_64/`,
`kernel-devel` (noarch) em `.../update/noarch/`).

**Por que nao dá pra compilar numa maquina SLE 15/SLED 15** (testado e
confirmado o erro): o `kernel-default-devel` da SLE 12 depende de
`libcrypto.so.1.0.0` (OpenSSL antigo, era da SLE 12), que a SLE 15 nao
tem instalado. **A compilacao precisa rodar numa maquina SLE 12 de
verdade** (usamos a VM de lab `sles12_1`, SLES 12 SP5, ver
`project_lab_vms_topologia` no historico do projeto). A mesma maquina
SLE 12 SP5 compila para qualquer outro SP da linha 12 (o kernel-alvo vem
inteiramente dos pacotes de header instalados via symlink, nao da
versao do SO da VM).

### Pacotes que dependem do kernel-alvo (3 por versao, 4 no SP1)

Para compilar contra um kernel especifico, sao necessarios estes 3
pacotes dessa MESMA versao de kernel (nomes exatos, incluindo o
`-<numero>` de release do pacote, que pode diferir entre eles):

| Pacote | Papel | Onde fica no mirror |
|---|---|---|
| `kernel-default-devel-<kernel>.rpm` | Headers/Makefiles do flavor `default` (unico usado neste projeto); fornece `/usr/src/linux-<kernel>-obj/` | `.../<SP>/x86_64/update/x86_64/` |
| `kernel-syms-<kernel>.rpm` | Tabela de simbolos exportados (`Module.symvers`) daquele kernel exato; sem ela o `rpmbuild` nao resolve as dependencias `ksym(...)` do modulo | `.../<SP>/x86_64/update/x86_64/` |
| `kernel-devel-<kernel>.rpm` (noarch) | Arvore de source do kernel (`/usr/src/linux-<kernel>/`), usada pelo `Makefile` do modulo via `make -C` | `.../<SP>/x86_64/update/noarch/` |

Repare que `kernel-devel` e `kernel-syms` sao pacotes DIFERENTES do
`kernel-default-devel`, apesar do nome parecido -- os 3 sao necessarios
juntos, nenhum substitui o outro.

**SLES 12 SP1 (kernel 3.12.x) precisa de um 4o pacote**,
`kernel-xen-devel-<kernel>.rpm` -- so como dependencia do `kernel-syms`
dessa era, mesmo compilando apenas o flavor `default`. Ver a secao
"Variacao para SLES 12 SP1" mais abaixo para o passo a passo completo
e uma pegadinha de conflito de pacotes.

Passo a passo (executado por SP, um de cada vez, para nao esgotar
disco/metadados do BTRFS numa VM pequena):

```bash
# 1. No servidor do mirror (via SSH), gerar um tar com os 3 pacotes de
#    cada versao de kernel disponivel para o SP desejado (exemplo: SP2).
#    O filtro '[0-9]*' exclui outros flavors (ex.: kernel-syms-azure-*).
ssh -q usuario@<host-do-mirror-interno> "
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
scp usuario@<host-do-mirror-interno>:/tmp/sp2_kernel_devel.tar .
cat sp2_kernel_devel.tar | ssh usuario@vm-sles12 \
  "mkdir -p ~/rpms_sp2 && tar xf - -C ~/rpms_sp2 --strip-components=1"

# 3. Na VM SLE 12, para CADA versao de kernel encontrada: LIMPAR o
#    diretorio de saida do rpmbuild antes de compilar (passo critico,
#    ver nota abaixo), instalar, compilar, VERIFICAR o resultado antes
#    de aceitar, e so entao DESINSTALAR antes de ir para a proxima
#    (headers instalados ocupam ~80-100MB cada; instalar todas de uma
#    vez em VM pequena esgota o disco/metadados do BTRFS mesmo com
#    espaco "livre" aparente -- ver nota mais abaixo):
mkdir -p ~/kmp_output
cd ~/rpms_sp2
for f in kernel-default-devel-*.x86_64.rpm; do
  KV=$(echo "$f" | sed -E "s/^kernel-default-devel-(.+)\.[0-9]+\.x86_64\.rpm$/\1/")

  sudo rpm -ivh --oldpackage --replacepkgs \
    kernel-default-devel-${KV}.*.x86_64.rpm \
    kernel-syms-${KV}.*.x86_64.rpm \
    kernel-devel-${KV}.*.noarch.rpm

  sudo ln -sfn linux-$KV /usr/src/linux
  sudo ln -sfn ../../linux-$KV-obj/x86_64/default /usr/src/linux-obj/x86_64/default

  # IMPORTANTE: limpar o diretorio de saida ANTES de compilar. O
  # rpmbuild nao apaga builds anteriores, e como todos os KMPs tem o
  # MESMO nome de pacote (so a versao muda), um comando que pegue "o
  # arquivo mais recente" por ordenacao alfabetica pode escolher um
  # build de OUTRA versao que ainda esteja no diretorio.
  rm -f ~/rpmbuild/RPMS/x86_64/amibios-dmi-kmp-default-1.0.0_k*.rpm

  rpmbuild -ba ~/rpmbuild/SPECS/amibios-dmi.spec

  # Com o diretorio limpo antes, so deve existir UM arquivo casando com
  # o padrao abaixo -- se existir mais de um, algo no passo anterior
  # falhou silenciosamente.
  OUT=$(ls ~/rpmbuild/RPMS/x86_64/amibios-dmi-kmp-default-1.0.0_k*.rpm)

  # VERIFICACAO OBRIGATORIA: confirma que a versao embutida no pacote
  # (formato "1.0.0_k<versao>_<build>") bate com o kernel-alvo desta
  # iteracao ANTES de renomear/aceitar o arquivo. Sem isso, um build
  # que silenciosamente compilou contra o kernel errado (ex.: symlink
  # nao trocou a tempo) passaria despercebido com o nome do arquivo
  # errado.
  VERSAO_REAL=$(rpm -qp --qf "%{VERSION}" "$OUT")
  VERSAO_ESPERADA="1.0.0_k$(echo $KV | sed 's/-/_/')"
  if [ "$VERSAO_REAL" != "$VERSAO_ESPERADA" ]; then
    echo "ERRO: build de $KV saiu com versao '$VERSAO_REAL' (esperado '$VERSAO_ESPERADA'). NAO copiando."
  else
    cp "$OUT" ~/kmp_output/amibios-dmi-kmp-default-${KV}.rpm
    echo "OK: $KV -> $VERSAO_REAL"
  fi

  # nome exato dos pacotes instalados (para o erase nao ficar ambiguo
  # com outras versoes eventualmente presentes):
  PKGS=$(rpm -qa | grep -E "(default-devel|syms|devel)-${KV}[.-]")
  sudo rpm -e $PKGS
done
```

Depois de trazer os `.rpm` gerados de volta (ex.: `scp`), confira mais
uma vez, agora fora da VM, que o nome de cada arquivo bate com a versao
interna do pacote, antes de colocar na pasta `rpm/` do projeto:

```bash
for f in *.rpm; do
  KV_NOME=$(echo "$f" | sed -E 's/^amibios-dmi-kmp-default-(.+)\.rpm$/\1/')
  VERSAO_REAL=$(rpm -qp --qf "%{VERSION}" "$f")
  KV_REAL=$(echo "$VERSAO_REAL" | sed -E 's/^1\.0\.0_k(.+)_([^_]+)$/\1-\2/')
  if [ "$KV_NOME" != "$KV_REAL" ]; then
    echo "MISMATCH: $f (nome diz $KV_NOME, conteudo e $KV_REAL)"
  fi
done
```

### Variacao para SLES 12 SP1 (e mais antigo): pacote extra `kernel-xen-devel`

A partir do SP2 em diante, os 3 pacotes acima (`kernel-default-devel`,
`kernel-syms`, `kernel-devel`) bastam. **No SP1 (kernel 3.12.x), o
`kernel-syms` dessa era exige tambem `kernel-xen-devel` da MESMA
versao instalado** (dependencia do proprio pacote, mesmo compilando so
o flavor `default`):

```
error: Failed dependencies:
	kernel-xen-devel = 3.12.51-60.20 is needed by kernel-syms-3.12.51-60.20.1.x86_64
```

O `kernel-xen-devel` fica no MESMO diretorio do `kernel-default-devel`
no mirror (`.../<SP>/x86_64/update/x86_64/kernel-xen-devel-<kernel>.rpm`).
Baixe e instale junto com os outros 3:

```bash
sudo rpm -ivh --oldpackage --replacepkgs \
  kernel-default-devel-${KV}.*.x86_64.rpm \
  kernel-syms-${KV}.*.x86_64.rpm \
  kernel-devel-${KV}.*.noarch.rpm \
  kernel-xen-devel-${KV}.*.x86_64.rpm
```

**Pegadinha adicional**: se a VM de compilacao ja tiver algum
`kernel-default-devel`/`kernel-source` MAIS NOVO instalado (ex.: o
usado para compilar outras SPs antes), a instalacao do
`kernel-xen-devel` antigo pode falhar com um erro diferente:

```
error: Failed dependencies:
	kernel-xen-devel <= 4.4 is obsoleted by (installed) kernel-default-devel-4.12.14-122.231.1.x86_64
```

Isso acontece porque pacotes `kernel-default-devel` de kernels mais
novos (linha 4.x) tem uma declaracao `Obsoletes: kernel-xen-devel <=
4.4`, que colide com a instalacao paralela de qualquer
`kernel-xen-devel` da era 3.12.x. Solucao: desinstale TODOS os pacotes
`kernel-default-devel`/`kernel-syms`/`kernel-devel`/`kernel-source` que
estiverem instalados na VM antes de comecar o lote da SP1 (nenhum deles
e necessario durante a compilacao da SP1 em si, e podem ser
reinstalados depois se precisar deles de novo):

```bash
rpm -qa | grep -E 'kernel-(default-devel|syms|devel|source)-'
sudo rpm -e <pacotes-listados-acima>
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
