# Empacotamento RPM

Arquivos usados para gerar o pacote RPM do `update_dmi_tag`. O formato
do `.spec` e do `_service` foi baseado no projeto irmao
[sys-inspector](https://github.com/mariosergiosl/sys-inspector) (mesmo
autor), so como referencia de estilo; nao ha nenhuma relacao funcional
entre os dois pacotes.

**Status atual: publicado no OBS.** Projeto `home:mariosergiosl`, pacote
`update_dmi_tag`, builds `succeeded` em dois repositorios
(`openSUSE_Leap_15.6` e `15.6`, este ultimo contra `SUSE:SLE-15-SP6:GA`).
Ver secao "Publicar/atualizar no OBS" abaixo para o fluxo de release.

## Arquivos

- `update_dmi_tag.spec` (na raiz do projeto, exigencia do OBS): spec
  do RPM.
- `_service` (na raiz do projeto): servico do OBS (`tar_scm`) que
  busca o codigo direto do GitHub, na tag indicada no campo
  `<revision>` (atualizada a cada release; hoje aponta para `v2.2.8`).
- `packaging/update_dmi_tag-wrapper.sh`: instalado como
  `/usr/bin/update_dmi_tag`, entra em `/opt/update_dmi_tag` antes de
  chamar o script (ver comentario no proprio arquivo).

## Onde tudo fica instalado

Todo o conteudo do projeto (codigo, `manual_operacao.md`, exemplos,
`efi_boot/dmi-atm/` open-source) vai para `/opt/update_dmi_tag/`. O
pacote **nao inclui** `amidelnx_64` nem `AMIDEEFIx64.EFI` (proprietarios
da AMI, sob NDA); apos instalar o RPM, e preciso obte-los pelo canal
OEM e colocar manualmente em `/opt/update_dmi_tag/`.

O comando `update_dmi_tag` (via `/usr/bin/update_dmi_tag`) e um atalho
que roda a partir dessa pasta, entao os defaults do codigo (ex:
`--amide-local-path`, `--efi-local-dir`, leitura de `bb_repo.conf`)
funcionam sem precisar de nenhuma mudanca de codigo.

O `%post` do RPM aplica `chmod 1777` (sticky bit, igual ao `/tmp`) em
`/opt/update_dmi_tag`, para que operadores nao-root consigam criar seus
proprios logs ali sem poderem apagar arquivos de outros usuarios nem o
codigo. Para identificar quem rodou cada execucao no log compartilhado,
o cabecalho de cada rodada registra o usuario do SO (linha `Operad:` /
`Operador (SO):`, desde a v2.1.13).

### Ressalvas do diretorio compartilhado (ler antes de escalar)

Como todos os operadores rodam a partir do mesmo `/opt/update_dmi_tag`:

- **Log compartilhado:** o log local default (`update_dmi_tag_remoto.log`)
  e um arquivo unico. Em modo append nao quebra e cada bloco de execucao
  fica carimbado com o usuario do SO, mas as rodadas de operadores
  diferentes se intercalam. Para separar, cada operador pode passar
  `--log-local ~/meu_log.log`.
- **`.ssh_pass` compartilhado:** **nao** coloque `.ssh_pass` em
  `/opt/update_dmi_tag` num ambiente multiusuario, a senha ficaria
  legivel por todos. Cada operador deve manter o proprio `.ssh_pass`
  na sua pasta e apontar via `--ssh-pass-file ~/.ssh_pass` (ou usar
  `SSH_PASS` no ambiente). Este e o motivo pelo qual, ao escalar para
  muitos operadores, o modelo natural continua sendo cada um rodar da
  propria pasta de trabalho.

## Build local (teste antes de publicar/atualizar no OBS)

```bash
# Cria o tarball fonte a partir da tag do release
git archive --format=tar.gz --prefix=update_dmi_tag-2.2.8/ \
  -o /tmp/update_dmi_tag-2.2.8.tar.gz v2.2.8

# Build com osc (requer osc instalado e configurado) ou rpmbuild direto:
rpmbuild -ta /tmp/update_dmi_tag-2.2.8.tar.gz
```

Recomendado antes de qualquer release: validar o build localmente (como
acima) antes de disparar o OBS, especialmente o `%changelog` do
`update_dmi_tag.spec` (RPM valida o dia da semana de cada data; uma data
errada derruba o build com "bogus date in %changelog").

## Publicar/atualizar no OBS (Open Build Service)

Projeto e pacote ja existem (`home:mariosergiosl` / `update_dmi_tag`,
cliente `osc` usado: venv em `D:\Ferramentas\osc` no Windows). Fluxo de
release para uma nova versao:

1. Criar e enviar a tag `vX.Y.Z` no GitHub (`git tag -a vX.Y.Z -m "..."`,
   `git push origin vX.Y.Z`).
2. Atualizar o campo `<revision>` do `_service` (na raiz do projeto) para
   a nova tag e enviar ao OBS:
   `osc api -T _service /source/home:mariosergiosl/update_dmi_tag/_service`
3. Disparar o servico remoto: `osc service remoterun home:mariosergiosl update_dmi_tag`
4. Conferir o resultado: `osc results home:mariosergiosl update_dmi_tag`
   (esperado: `succeeded` nos dois repositorios).

Repositorios configurados: `openSUSE_Leap_15.6` (contra
`openSUSE:Leap:15.6`) e `15.6` (contra `SUSE:SLE-15-SP6:GA`), ambos
x86_64/noarch. Pagina do pacote:
https://build.opensuse.org/package/show/home:mariosergiosl/update_dmi_tag

Depois de publicado, o operador instala/atualiza via:

```bash
# openSUSE Leap 15.6
zypper addrepo https://download.opensuse.org/repositories/home:/mariosergiosl/openSUSE_Leap_15.6/home:mariosergiosl.repo
# SUSE Linux Enterprise 15 SP6
zypper addrepo https://download.opensuse.org/repositories/home:/mariosergiosl/15.6/home:mariosergiosl.repo

zypper refresh
zypper install update_dmi_tag
```
