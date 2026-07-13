# Empacotamento RPM

Arquivos usados para gerar o pacote RPM do `update_dmi_tag`. O formato
do `.spec` e do `_service` foi baseado no projeto irmao
[sys-inspector](https://github.com/mariosergiosl/sys-inspector) (mesmo
autor), so como referencia de estilo; nao ha nenhuma relacao funcional
entre os dois pacotes.

**Status atual: nada disso foi publicado no OBS ainda.** Os arquivos
abaixo existem so aqui no repositorio git. Criar o projeto no OBS
(`build.opensuse.org`) e um passo manual, feito por voce diretamente
no site (ou via `osc`), ver secao "Publicar no OBS" abaixo.

## Arquivos

- `update_dmi_tag.spec` (na raiz do projeto, exigencia do OBS): spec
  do RPM.
- `_service` (na raiz do projeto): servico do OBS (`tar_scm`) que
  busca o codigo direto do GitHub, na tag indicada (`v2.1.13`).
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

## Build local (teste antes de publicar no OBS)

```bash
# Cria o tarball fonte a partir do HEAD atual
git archive --format=tar.gz --prefix=update_dmi_tag-2.1.13/ \
  -o /tmp/update_dmi_tag-2.1.13.tar.gz HEAD

# Build com osc (requer osc instalado e configurado) ou rpmbuild direto:
rpmbuild -ta /tmp/update_dmi_tag-2.1.13.tar.gz
```

## Publicar no OBS (Open Build Service): passo a passo manual, ainda pendente

1. Fazer login em [build.opensuse.org](https://build.opensuse.org) com
   a sua conta e criar um projeto novo chamado
   `home:mariosergiosl:update_dmi_tag` (nome sugerido, livre para
   trocar). Isso e feito direto na interface web do OBS, eu nao tenho
   acesso a sua conta para fazer isso por voce.
2. Dentro desse projeto, criar o pacote `update_dmi_tag`.
3. Fazer upload de `update_dmi_tag.spec` e `_service` (ou usar
   `osc service runall` para o OBS buscar do GitHub automaticamente
   via `_service`).
4. Cada nova tag `vX.Y.Z` no GitHub, seguida de um `osc service
   remoterun` (ou webhook equivalente), gera uma nova build.

Depois de publicado, o operador instala/atualiza via:

```bash
zypper addrepo https://download.opensuse.org/repositories/home:/mariosergiosl:/update_dmi_tag/<distro>/home:mariosergiosl:update_dmi_tag.repo
zypper refresh
zypper install update_dmi_tag
```
