# ==============================================================================
# FILE: update_dmi_tag.spec
# DESCRIPTION: RPM spec file para o update_dmi_tag
# AUTHOR: Mario Luz
# ==============================================================================

Name:           update_dmi_tag
Version:        2.1.13
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
amibios_dmi via sysfs, e o Mecanismo 4 experimental via boot EFI
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
* Thu Jul 09 2026 Mario Luz <mario.mssl@gmail.com> - 2.1.13-0
- Corrige travamento do Mecanismo 4 (timeout no SSH de gravar_log_remoto;
  antes, logar apos o reboot pendurava a ferramenta para sempre).
- Espera pos-reboot com heartbeat na tela; corrige duplicacao de linhas
  do Mecanismo 4 no stdout.
- Adiciona o usuario do SO ao cabecalho do log (rastreabilidade quando
  varios operadores compartilham a mesma instalacao).
- Primeira versao empacotada como RPM (instalacao em /opt/update_dmi_tag,
  wrapper em /usr/bin/update_dmi_tag).
* Thu Jul 09 2026 Mario Luz <mario.mssl@gmail.com> - 2.1.12-0
- Validacao do Mecanismo 4 em VM real e correcoes de seguranca.
