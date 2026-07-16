# ==============================================================================
# FILE: update_dmi_tag.spec
# DESCRIPTION: RPM spec file para o update_dmi_tag
# AUTHOR: Mario Luz
# ==============================================================================

Name:           update_dmi_tag
Version:        2.2.1
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

# Documentacao, licenca e exemplos que o operador consulta junto do codigo
cp -a manual_operacao.md README.md LICENSE.md ErrCode.txt \
    survey_asset_tag.bash bb_repo.conf.example %{buildroot}/opt/%{name}/

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
* Thu Jul 16 2026 Mario Luz <mario.mssl@gmail.com> - 2.2.1-0
- Corrige bugs reais encontrados em incidente de producao com usuario SSH
  comum (nao root): checagem de efibootmgr/mokutil so testava o $PATH da
  sessao (nao inclui /usr/sbin para usuario comum), com tentativa de
  instalacao via zypper se ausente; bug de precedencia de shell (&&/||
  sem parenteses) vazava todos os caminhos testados no log; mokutil
  --sb-state rodava sem sudo, sem retorno claro.
- Corrige bug serio: o diretorio da ESP e criado com sudo (dono root,
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
* Sun Jul 13 2026 Mario Luz <mario.mssl@gmail.com> - 2.1.14-0
- Renumeracao do mecanismo de boot EFI de "Mecanismo 4" para
  "Mecanismo 3" (elimina o buraco na numeracao da cascata: 1, 2, 3). So
  exibicao (log/ajuda/docs); identificadores funcionais inalterados.
* Sun Jul 13 2026 Mario Luz <mario.mssl@gmail.com> - 2.1.13-0
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
