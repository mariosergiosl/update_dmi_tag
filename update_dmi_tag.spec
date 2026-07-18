# ==============================================================================
# FILE: update_dmi_tag.spec
# DESCRIPTION: RPM spec file para o update_dmi_tag
# AUTHOR: Mario Luz
# ==============================================================================

Name:           update_dmi_tag
Version:        2.2.8
Release:        0
Summary:        Utilitario para validacao de patrimonio e gravacao do campo DMI Asset Tag

License:        GPL-3.0-only
URL:            https://github.com/mariosergiosl/update_dmi_tag
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

# Build Dependencies
BuildRequires:  python3

# Runtime Dependencies (stdlib apenas, sem pip)
Requires:       python3
Requires:       openssh

%description
Ferramenta para ler um numero de patrimonio (13 ou 14 digitos), validar
o digito verificador (Modulo 11) e gravar o valor no campo DMI Chassis
Asset Tag da BIOS AMI, via cascata de mecanismos (amidelnx_64,
amibios_dmi via sysfs, e o Mecanismo 3 experimental via boot EFI
temporario). Suporta execucao local (standalone) e remota em lote
(lista de hosts via SSH), sempre em modo Dry-Run por padrao.

Este pacote instala apenas o codigo aberto do projeto. Os binarios
proprietarios da AMI (amidelnx_64, AMIDEEFIx64.EFI), sob NDA, NAO
fazem parte do pacote; precisam ser obtidos pelo canal OEM e colocados
manualmente em /opt/update_dmi_tag apos a instalacao (ver
README.md/manual_operacao.md).

%prep
%setup -q

%build
# Nada para compilar, projeto Python puro (stdlib apenas).

%install
rm -rf %{buildroot}
install -d %{buildroot}/opt/%{name}
install -d %{buildroot}%{_bindir}

# Codigo principal
cp -a update_dmi_tag.py %{buildroot}/opt/%{name}/
cp -a update_dmi_tag %{buildroot}/opt/%{name}/
cp -a tools %{buildroot}/opt/%{name}/
cp -a efi_boot %{buildroot}/opt/%{name}/

# RPMs do KMP amibios_dmi (fork open-source mariosergiosl/amibios_dmi,
# GPLv2, NAO e NDA -- ver rpm/README.md), usados pela instalacao remota
# automatica do Mecanismo 2 (environment.py: instala_modulo_remoto).
cp -a rpm %{buildroot}/opt/%{name}/

# Documentacao, licenca e exemplos que o operador consulta junto do codigo
cp -a manual_operacao.md manual_operacao.pdf README.md LICENSE.md ErrCode.txt \
    survey_asset_tag.bash bb_repo.conf.example %{buildroot}/opt/%{name}/

# Imagens de marca (logo/banner) referenciadas pelo manual_operacao.md
cp -a assets %{buildroot}/opt/%{name}/

# Limpeza de artefatos de desenvolvimento que nao devem ir no pacote
find %{buildroot}/opt/%{name} -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find %{buildroot}/opt/%{name} -name "*.pyc" -delete

# Wrapper em /usr/bin, entra em /opt/update_dmi_tag antes de chamar o
# script para que os defaults do codigo (--amide-local-path,
# --efi-local-dir, leitura de bb_repo.conf) resolvam corretamente.
install -Dm755 packaging/update_dmi_tag-wrapper.sh %{buildroot}%{_bindir}/update_dmi_tag

%post
# Sticky bit no diretorio de trabalho: permite que operadores nao-root
# criem seus proprios logs em /opt/update_dmi_tag (o wrapper roda a
# partir dai) sem poderem apagar arquivos de outros usuarios nem o
# codigo. Ver caveats em packaging/README.md (log/.ssh_pass
# compartilhados) antes de escalar para muitos operadores.
chmod 1777 /opt/%{name} 2>/dev/null || true

%files
%license LICENSE.md
/opt/%{name}
%{_bindir}/update_dmi_tag

%changelog
* Fri Jul 17 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.8-0
- Trava global de seguranca: se a tag ja lida na BIOS (tag_antes) for
  igual a esperada, nenhum mecanismo e executado (sem escrita, sem
  reboot) e o resultado vira "OK-ja-correto". Evita reprocessar hosts
  ja corretos e, em especial, evita escalar ao Mecanismo 3 (reboot)
  sem necessidade. Vale so no modo de escrita real (--write sem
  --test-write).
- Resumo agregado passa a contabilizar e exibir o total "OK-ja-correto".
- Revisao de codigo: corrige a validacao redundante via CLI patrimonial
  (faltava --verbose, entao ela nunca retornava nada; e o parse
  descartava o "X" final de BEMs com DV=10). Remove chamada SSH
  duplicada em --production e ternario sem efeito na auditoria de RPMs.
- Nova suite de regressao automatizada em tests/ (30 testes, stdlib
  pura, SSH mockado): python3 -m unittest discover tests.
- Documentacao: 5 diagramas novos (fluxo macro, fluxo de codigo,
  cascata, Mecanismo 3, arquitetura) em assets/diagramas, secao 2.4.
* Fri Jul 17 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.7-0
- Corrige bug real no digito verificador (Modulo 11): quando o DV dava
  10, a funcao retornava "0", mas o padrao BB usa "X" para DV=10
  (confirmado contra o utilitario oficial python3-patrimonial). Antes,
  cerca de 1 em 11 BEMs (os que caem em DV=10) recebiam a tag errada,
  terminando em 0 em vez de X. O DV=11 continua "0".
- Documenta a estrutura da base patrimonial: PPPP.AA.DDD.NNNN + DV
  (prefixo comprador, ano do contrato, dia do ano do range, serie).
* Fri Jul 17 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.6-0
- Corrige bug real de campo (host de producao PERTOSA GA-H81M-S2PH):
  com o modulo amibios_dmi carregado e usuario SSH comum (nao root), o
  Mecanismo 2 falhava na escrita e caia no Mecanismo 3 (reboot) sem
  necessidade. O sysfs da asset tag e root-only, mas a leitura (cat), a
  checagem de gravabilidade (test -w) e a auditoria rodavam sem sudo,
  como usuario comum, barrando o sudo tee que faria a escrita. Agora
  todos usam sudo, coerente com a escrita.
- Guarda de dry-run no Mecanismo 2: no caso de borda em que o Mecanismo
  1 esta indisponivel e a cascata cai no Mecanismo 2 sem --write, nao
  instala/carrega mais o modulo (dry-run e apenas leitura).
- instala_modulo_remoto remove do home do usuario os .rpm que copia,
  em qualquer desfecho, para nao deixar arquivos orfaos.
- Documentacao: exemplo de linha de comando usa python3 -m (nao
  python -m), evitando a chamada acidental do Python 2 em ambientes
  onde "python" aponta para o interpretador antigo.
* Fri Jul 17 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.5-0
- Corrige bug real de corrida entre threads: prepara_autenticacao_ssh
  checava e gerava a chave SSH local (recurso compartilhado entre
  todos os hosts) sem lock. Com --parallel > 1 e nenhuma chave local
  previa, duas threads podiam tentar gerar a mesma chave ao mesmo
  tempo; uma falhava por corrida, levando o host dessa thread a
  INACESSIVEL sem motivo real. Corrigido com threading.Lock.
- Validado em campo (--parallel 3, 3 hosts reais heterogeneos: 2 VMs
  clonadas e um notebook Dell, ambiente sem chave SSH local previa).
* Thu Jul 16 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.4-0
- Corrige layout do log: a saida de erro do zypper install (varias
  linhas) era passada inteira num unico registro de log, entao so a
  primeira linha recebia o prefixo padrao e o resto aparecia cru no
  arquivo. Agora loga linha a linha, cada uma com seu proprio prefixo.
- Adiciona pasta assets/ (logo/banner) e aplica layout de cabecalho
  padrao (autor, versao, data, status) no manual_operacao.md e no
  Docs_Test_boot/README.md.
- Adiciona evidencia fotografica e registro do incidente de producao
  (host PERTOSA GA-H81M-S2PH, 10.24.80.96) no Docs_Test_boot/README.md,
  incluindo a investigacao com o modulo amibios_dmi corrigido.
- Documenta, no manual_operacao.md, um exemplo completo de linha de
  comando com todas as opcoes relevantes explicadas uma a uma.
* Thu Jul 16 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.3-0
- Implementa de vez a instalacao remota automatica do KMP amibios_dmi
  (fork open-source mariosergiosl/amibios_dmi, GPLv2, nao e NDA):
  copia os .rpm de rpm/ via scp, confere SHA-256 da copia antes de
  instalar com sudo, instala via zypper install local (sem depender de
  nenhum host alcancar repositorio externo), e reconfirma via rpm -q.
  Nova flag --module-rpm-dir.
- Corrige BUG REAL pre-existente: a checagem de "interface SMI pronta"
  usava o rc de um comando composto (test -d X && echo ready || echo
  absent), sempre 0 -- fazia a instalacao automatica do modulo nunca
  ser exercitada, em nenhum host, em nenhuma execucao anterior.
- Corrige bug de duplicidade (padrao de busca do RPM userspace tambem
  casava com o nome do KMP) e bug de shlex.quote no "~/arquivo" que
  impedia a expansao do "~" pelo shell remoto (sha256sum/zypper
  procuravam um arquivo inexistente).
- Corrige mensagem de erro do modprobe descartada silenciosamente
  (2>&1 mesclava no stdout, so o stderr vazio era lido).
- Adiciona rpm/README.md e inclui a pasta rpm/ no pacote RPM.
- Validado em campo: instalacao/carregamento/gravacao com persistencia
  confirmada apos reboot no host de producao (10.24.80.96, PERTOSA
  GA-H81M-S2PH); fluxo completo (deteccao, copia, checksum, tentativa
  de instalacao, diagnostico de falha, Mecanismo 3 com reboot real)
  validado ponta a ponta em VM de teste.
* Thu Jul 16 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.2-0
- Adiciona checkpoints de progresso permanentes no startup.nsh do
  Mecanismo 3 (MEC3-DEBUG: apos cada comando, gravados incrementalmente
  em FS0:\amide_debug.log), motivado por host PERTOSA GA-H81M-S2PH
  (producao) que travou apos o reboot sem retornar via SSH
  (TRAVADO-POS-REBOOT) e sem log algum para diagnostico, ja que o
  arquivo so era criado ao final da execucao do AMIDEEFIx64.EFI.
- Nao interfere na deteccao de incompatibilidade de firmware nem no
  encoding UTF-16LE ja usado pelo UEFI Shell.
* Thu Jul 16 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.1-0
- Corrige bugs reais encontrados em incidente de producao com usuario SSH
  comum (nao root): checagem de efibootmgr/mokutil so testava o $PATH da
  sessao (nao inclui /usr/sbin para usuario comum), com tentativa de
  instalacao via zypper se ausente; bug de precedencia de shell (&&/||
  sem parenteses) vazava todos os caminhos testados no log; mokutil
  --sb-state rodava sem sudo, sem retorno claro.
- Corrige bug: o diretorio da ESP e criado com sudo (dono root,
  modo 755), mas os arquivos eram copiados via scp comum, falhando
  sempre com "Permissao negada" para qualquer usuario nao-root. Nova
  funcao _copia_para_esp contorna isso (scp para o home do usuario,
  depois sudo mv para o destino final).
- Adiciona marcadores INICIO/FIM ao redor da saida capturada do
  AMIDEEFIx64.EFI no log.
- Validado em campo com usuario sudo nao-root real e em hosts PERTOSA/
  PERTO SA de producao.
* Tue Jul 14 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.0-0
- Execucao paralela (--parallel N, EXPERIMENTAL): pool de threads, log
  isolado por host em logs/<timestamp>/hosts/, ticker de progresso no
  stdout, merge no consolidado ao final na ordem do arquivo de hosts.
  --parallel 1 (padrao) mantem o comportamento sequencial de sempre.
- Corrige bug real do Mecanismo 3 em hardware fisico (nao aparecia em
  VM): faltava selecionar o drive "FS0:" antes do "cd" no startup.nsh,
  entao o AMIDEEFIx64.EFI nunca era encontrado.
- Detecta automaticamente uma assinatura de incompatibilidade de
  firmware (confirmada em campo em dois notebooks Dell) nos 3
  mecanismos, reportando INCOMPATIVEL-HW/INCOMPATIVEL-efiboot em vez do
  FALHOU generico.
- Adiciona --force-efi-secureboot (PERIGOSO, teste de campo controlado):
  pula o bloqueio de Secure Boot do Mecanismo 3 mediante dupla
  confirmacao interativa.
- Corrige um crash nao tratado (OSError) na escrita local do sysfs
  (Mecanismo 2, modo standalone).
* Mon Jul 13 2026 Mario Luz <mario.mssl@gmail.com> - 2.1.14-0
- Renumeracao do mecanismo de boot EFI de "Mecanismo 4" para
  "Mecanismo 3" (elimina o buraco na numeracao da cascata: 1, 2, 3). So
  exibicao (log/ajuda/docs); identificadores funcionais inalterados.
* Mon Jul 13 2026 Mario Luz <mario.mssl@gmail.com> - 2.1.13-0
- Corrige travamento do Mecanismo 3 (timeout no SSH de gravar_log_remoto;
  antes, logar apos o reboot pendurava a ferramenta para sempre).
- Idempotencia do Mecanismo 3: re-execucao apos termino anormal se
  autolimpa em vez de ficar bloqueada.
- Espera pos-reboot com heartbeat na tela; corrige duplicacao de linhas
  do Mecanismo 3 no stdout.
- Adiciona o usuario do SO ao cabecalho do log (rastreabilidade quando
  varios operadores compartilham a mesma instalacao).
- Primeira versao empacotada como RPM (instalacao em /opt/update_dmi_tag,
  wrapper em /usr/bin/update_dmi_tag).
* Thu Jul 09 2026 Mario Luz <mario.mssl@gmail.com> - 2.1.12-0
- Validacao do Mecanismo 3 em VM real e correcoes de seguranca.
