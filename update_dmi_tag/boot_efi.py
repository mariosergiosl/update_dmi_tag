# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: boot_efi.py
#
# DESCRIPTION: Mecanismo 3 (experimental): grava o Chassis Asset Tag em
#              pre-boot via AMIDEEFIx64.EFI rodando dentro de um UEFI
#              Shell temporario, contornando o bloqueio de WSMT que
#              impede os Mecanismos 1/2 em alguns modelos (Daten DH3UP,
#              H4U02PER, ver constants.py, bloco COMPATIBILITY).
#
#              So acionado explicitamente via --allow-efi-fallback,
#              independente de --write/--test-write, e so depois que os
#              Mecanismos 1 e 2 ja falharam de verdade (FALHOU-todos) na
#              tentativa real de gravacao. Nunca roda em --test-write:
#              o --test-write existe para ser 100% seguro e reversivel,
#              e este mecanismo reboota o equipamento, natureza de
#              risco incompativel com essa garantia.
#
#              Fluxo:
#                1. verifica_seguranca_efi_remoto, bateria de checagens
#                   READ-ONLY (nunca escreve nada se qualquer uma falhar):
#                   UEFI confirmado, efibootmgr presente, Secure Boot
#                   inativo, sem criptografia de disco selada em TPM,
#                   particao ESP montada/gravavel/com espaco livre,
#                   sem colisao com entrada de boot existente.
#                2. executa_boot_efi_remoto, so chamada se a checagem
#                   acima passar. Copia os binarios para a ESP, gera o
#                   startup.nsh com a tag real (so /CA, mesmo escopo do
#                   restante do script), cria a entrada de boot, marca
#                   BootNext, reinicia, espera o host voltar (timeout
#                   configuravel) e confirma o valor gravado. Sempre limpa
#                   a entrada de boot e os arquivos da ESP ao final,
#                   sucesso ou falha.
#
#              Tudo aqui e read-only ate o passo 2 comecar a copiar
#              arquivos, qualquer duvida de seguranca aborta ANTES de
#              tocar em NVRAM ou na particao EFI.
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.2.8
# REVISION: 2026-07-17 - v2.2.8 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.7 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.6 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-17 - v2.2.5 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.4 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.3 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-07-16 - v2.2.2 - host PERTOSA GA-H81M-S2PH (producao, BB)
#                        travou apos o reboot do Mecanismo 3, sem retornar
#                        via SSH (TRAVADO-POS-REBOOT), e o amide_debug.log
#                        nunca chegou a existir, entao nao deu para saber
#                        em que linha do startup.nsh o travamento ocorreu.
#                        Adiciona checkpoints de progresso permanentes no
#                        startup.nsh (MEC3-DEBUG: apos cada comando,
#                        gravados incrementalmente com ">>" em
#                        FS0:\amide_debug.log), para que, mesmo travando no
#                        meio, o log parcial ja gravado sobreviva a um
#                        reset fisico. Nao interfere na deteccao de
#                        incompatibilidade de firmware (comparacao por
#                        substring em eh_incompatibilidade_firmware, ver
#                        constants.py) nem no encoding (mesmo mecanismo de
#                        redirecionamento UTF-16LE do UEFI Shell usado pelo
#                        AMIDEEFIx64.EFI). Mantido permanentemente (nao e
#                        mais um bloco de debug temporario), decisao para
#                        ajudar na operacao em volume no parque completo.
# REVISION: 2026-07-16 - v2.2.1 - corrige bugs reais encontrados em
#                        incidente de producao (usuario SSH comum, nao
#                        root): (1) checagem de efibootmgr/mokutil
#                        testava so o $PATH da sessao, que em usuario
#                        comum normalmente nao inclui /usr/sbin;
#                        _garante_binario_remoto agora testa caminhos
#                        padrao tambem, com tentativa de instalacao via
#                        zypper se ausente; (2) bug de precedencia
#                        shell (&&/|| sem parenteses) fazia a busca de
#                        binario vazar todos os caminhos testados em
#                        vez de só o primeiro encontrado; (3) mokutil
#                        --sb-state rodava sem sudo, sem retorno claro
#                        em usuario comum (leitura de efivars exige
#                        privilegio); (4) o diretorio da ESP
#                        e criado com sudo (dono root, modo 755), mas
#                        os arquivos eram copiados via scp comum (sem
#                        sudo), sempre falhando com "Permissao negada"
#                        para qualquer usuario nao-root; nova funcao
#                        _copia_para_esp contorna isso (scp para o home
#                        do usuario, depois sudo mv para o destino
#                        final); (5) checagem "particao EFI gravavel"
#                        tambem passou a testar via sudo, coerente com
#                        o mecanismo real de copia. Adiciona marcadores
#                        INICIO/FIM ao redor da saida capturada do
#                        AMIDEEFIx64.EFI no log, a pedido do usuario.
#                        Validado em campo com usuario sudo nao-root
#                        real (VM de teste) e em 3 hosts PERTOSA/PERTO
#                        SA de producao (BB).
# REVISION: 2026-07-14 - v2.2.0 - corrige bug real encontrado em hardware
#                        (nao aparecia em VM): o shell inicia sem nenhum
#                        drive mapeado como atual ("Shell>", nao
#                        "FS0:\>"), entao o "cd" relativo falhava e o
#                        AMIDEEFIx64.EFI nunca era encontrado. Corrigido
#                        com "FS0:" explicito antes do cd. Adiciona
#                        captura da saida do AMIDEEFIx64.EFI no log
#                        (decodificada de UTF-16LE), deteccao de
#                        INCOMPATIVEL-efiboot via assinatura conhecida, e
#                        o bypass --force-efi-secureboot (PERIGOSO, teste
#                        de campo controlado). Corrige tambem uma linha
#                        de log fora do padrao quando mokutil retorna
#                        mais de uma linha ("Platform is in Setup Mode").
#                        Validado em campo: Dell Precision 5520, Dell
#                        Latitude 5320 (ver Docs_Test_boot/).
# CREATED: 2026-07-08
# REVISION: 2026-07-13 - v2.1.14 - renumeracao do mecanismo de boot EFI
#                        de "Mecanismo 4" para "Mecanismo 3" (elimina o
#                        buraco na numeracao; cascata agora 1, 2, 3). So
#                        exibicao (log/ajuda/docs); identificadores
#                        funcionais (status, flags, labels) inalterados.
# REVISION: 2026-07-09 - v2.1.13 - idempotencia: _limpa_sobra_anterior
#                        no inicio remove sobras nossas de execucao
#                        anterior anormal (kill/crash), evitando BLOQUEADO
#                        permanente na re-execucao. Na espera pos-reboot,
#                        usa log local-only (_log_local, sem SSH para o
#                        host reiniciando) no formato consolidado padrao,
#                        com heartbeat a cada ~30s. Corrige a duplicacao
#                        de linhas na tela: o log dedicado do MEC3 nao
#                        imprime mais no stdout. Nomenclatura: Mecanismos
#                        1 e 2 (nao "1/2/3"). Empacotamento RPM e usuario
#                        do SO no log (ver __main__.py).
# REVISION: 2026-07-09 - v2.1.12 - corrige startup.nsh do Mecanismo 3
#                        (faltava "cd" para o diretorio correto antes
#                        de chamar o AMIDEEFIx64.EFI) e corrige risco de
#                        loop de reboot infinito (efibootmgr --create
#                        inseria a entrada temporaria na BootOrder
#                        permanente, nao so no BootNext; agora a
#                        BootOrder original e restaurada logo apos a
#                        criacao da entrada). Validado em VM real, ver
#                        Docs_Test_boot/.
# REVISION: 2026-07-08 - v2.1.11 - criacao do modulo (Mecanismo 3,
#                        experimental). Primeira versao: checagens de
#                        seguranca + execucao completa do fluxo de boot
#                        temporario. Ainda nao validado em hardware real
#                        (aguardando testes em VM/equipamento fisico).
#
# =======================================================================

import os
import shlex
import time

from .constants import (
    SegurancaEfiBloqueadaError,
    DEFAULT_EFI_REMOTE_SUBDIR,
    DEFAULT_ESP_MOUNT_POINT,
    DEFAULT_EFI_BOOT_LABEL,
    DEFAULT_EFI_MIN_FREE_KB,
    DEFAULT_EFI_REBOOT_TIMEOUT,
    eh_incompatibilidade_firmware,
)
from .logging_utils import gravar_log, gravar_log_remoto, gravar_log_local_consolidado
from .ssh_utils import ssh_run, testa_porta_ssh, testa_conexao_ssh, _scp_arquivo_com_erro


def _fabrica_log(ip, ssh_user, sudo_cmd, caminho_log_remoto, caminho_log_local,
                  caminho_log_efi, verbose, suprime_tela):
    """
    NAME: _fabrica_log
    DESCRIPTION: Cria a funcao _log usada por este modulo. Grava no log
                 remoto do host + log local consolidado (via
                 gravar_log_remoto, igual ao resto do pacote) e, se
                 caminho_log_efi for informado, grava tambem nesse
                 terceiro log dedicado ao Mecanismo 3, exigencia
                 explicita de manter o resultado desse mecanismo visivel
                 num arquivo proprio, alem dos logs normais.
    PARAMETER: ip, ssh_user, sudo_cmd, caminho_log_remoto, caminho_log_local,
               caminho_log_efi, verbose, suprime_tela - ver assinatura das
               funcoes publicas deste modulo
    RETURNS: function, _log(nivel, msg)
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                          nivel, msg, caminho_log_local, verbose, suprime_tela)
        if caminho_log_efi:
            # Grava so no arquivo dedicado do Mecanismo 3; nao imprime no
            # stdout de novo (o gravar_log_remoto acima ja imprimiu esta
            # linha), senao cada evento do MEC3 apareceria duplicado na
            # tela, e a segunda copia num formato diferente.
            gravar_log(caminho_log_efi, nivel, "[{}] {}".format(ip, msg),
                       False, True)
    return _log


# Caminhos onde binarios administrativos costumam ficar, fora do $PATH
# padrao de um usuario comum (normalmente so /usr/sbin e /sbin, que ficam
# no $PATH do root mas nao do login SSH de um usuario sem privilegio).
_CAMINHOS_SBIN_PADRAO = ("/usr/sbin", "/sbin", "/usr/bin", "/bin")


def _garante_binario_remoto(ip, ssh_user, sudo_cmd, nome_binario, nome_pacote, _log):
    """
    NAME: _garante_binario_remoto
    DESCRIPTION: Verifica se um binario administrativo (ex: efibootmgr,
                 mokutil) esta disponivel no host, sem depender so do
                 $PATH da sessao SSH -- constatado em campo (2026-07-15)
                 que o $PATH padrao de um usuario comum (nao-root) costuma
                 nao incluir /usr/sbin (onde esses binarios normalmente
                 ficam), causando falso-negativo mesmo com o binario
                 instalado e executavel. Testa via "command -v" e depois
                 os caminhos padrao de _CAMINHOS_SBIN_PADRAO. Se ainda
                 assim nao encontrar, tenta instalar via zypper (repos
                 ja configurados no host, pacote de SO padrao, sem
                 repositorio extra) e testa de novo.
    PARAMETER: ip, ssh_user, sudo_cmd - identificacao/privilegio no host
               nome_binario           - nome do executavel (ex: "efibootmgr")
               nome_pacote            - nome do pacote zypper correspondente
               _log                   - funcao de log ja fechada sobre o host
    RETURNS: str, caminho completo do binario se encontrado (ou disponivel
             apos instalacao), string vazia se nao foi possivel garantir
    """
    def _ssh(cmd, timeout=15):
        rc, stdout, stderr = ssh_run(ip, ssh_user, cmd, timeout=timeout)
        return rc, stdout.strip(), stderr.strip()

    def _procura():
        # Cada teste fica entre parenteses de proposito: sem eles, && e ||
        # tem a mesma precedencia (avaliados em sequencia, esquerda para
        # direita), entao assim que QUALQUER teste anterior desse "certo"
        # (rc=0), todo "&& echo" seguinte roda em cascata, imprimindo
        # todos os caminhos, nao so o primeiro encontrado (bug constatado
        # em campo, 2026-07-16, vazando linhas soltas sem prefixo no log).
        testes = ["(command -v {} 2>/dev/null)".format(nome_binario)]
        for caminho in _CAMINHOS_SBIN_PADRAO:
            testes.append(
                "(test -x {0}/{1} && echo {0}/{1})".format(caminho, nome_binario))
        cmd = " || ".join(testes)
        rc, out, _ = _ssh(cmd)
        # Defesa extra: mesmo com os parenteses, fica so com a primeira
        # linha (ex: se o binario aparecer duplicado por symlink/usr-merge).
        primeira_linha = out.splitlines()[0].strip() if out else ""
        return primeira_linha if (rc == 0 and primeira_linha) else ""

    encontrado = _procura()
    if encontrado:
        return encontrado

    _log("WARNING",
         "[MEC3] {} nao encontrado (nem via $PATH, nem nos caminhos "
         "padrao de administracao); tentando instalar via zypper...".format(
             nome_binario))
    rc, _, stderr = _ssh(
        "{} zypper --non-interactive install {}".format(sudo_cmd, nome_pacote),
        timeout=120)
    if rc != 0:
        _log("WARNING",
             "[MEC3] Instalacao de '{}' via zypper falhou (rc={}): {}".format(
                 nome_pacote, rc, stderr[:200]))
        return ""

    encontrado = _procura()
    if encontrado:
        _log("INFO", "[MEC3] {} instalado com sucesso via zypper.".format(nome_pacote))
    return encontrado


def _copia_para_esp(ip, ssh_user, sudo_cmd, caminho_local, caminho_remoto_final):
    """
    NAME: _copia_para_esp
    DESCRIPTION: Copia um arquivo local para dentro da ESP no host remoto,
                 contornando a falta de permissao de escrita direta de um
                 usuario comum no diretorio da ESP criado com sudo.
                 Constatado em campo (2026-07-16, usuario nao-root): o
                 "mkdir -p" com sudo cria o diretorio dono root, modo 755
                 (sem escrita para outros), entao um scp direto como
                 ssh_user (sem sudo -- scp nao tem como usar sudo na
                 escrita remota) falhava com "Permissao negada". Copia
                 primeiro para um arquivo temporario no home do proprio
                 ssh_user (scp comum, sem sudo, sempre permitido), depois
                 move para o destino final na ESP via sudo (mv, roda como
                 root, sem problema de permissao).
    PARAMETER: ip, ssh_user, sudo_cmd  - identificacao/privilegio no host
               caminho_local           - arquivo local a copiar
               caminho_remoto_final    - caminho completo de destino na ESP
    RETURNS: tuple(bool, str), (sucesso, mensagem de erro se houver)
    """
    def _ssh(cmd, timeout=15):
        rc, stdout, stderr = ssh_run(ip, ssh_user, cmd, timeout=timeout)
        return rc, stdout.strip(), stderr.strip()

    nome_temp = "~/.update_dmi_tag_tmp_{}".format(os.path.basename(caminho_remoto_final))
    sucesso, erro = _scp_arquivo_com_erro(ip, ssh_user, caminho_local, nome_temp)
    if not sucesso:
        return False, "falha no scp para {}: {}".format(nome_temp, erro)

    # "~" nao e citado de proposito: precisa ser expandido pelo shell do
    # login SSH antes do sudo ver o argumento (dentro de aspas simples o
    # shell nao expande "~").
    rc, _, stderr = _ssh("{} mv {} {}".format(
        sudo_cmd, nome_temp, shlex.quote(caminho_remoto_final)))
    if rc != 0:
        return False, "falha ao mover {} para {} via sudo: {}".format(
            nome_temp, caminho_remoto_final, stderr.strip())
    return True, ""


def verifica_seguranca_efi_remoto(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                                    caminho_log_local, caminho_log_efi,
                                    verbose, suprime_tela,
                                    esp_mount_point=DEFAULT_ESP_MOUNT_POINT,
                                    boot_label=DEFAULT_EFI_BOOT_LABEL,
                                    min_free_kb=DEFAULT_EFI_MIN_FREE_KB,
                                    force_secureboot=False):
    """
    NAME: verifica_seguranca_efi_remoto
    DESCRIPTION: Bateria de checagens READ-ONLY que decide se e seguro
                 tentar o Mecanismo 3 neste host. Nao escreve nada no
                 host, todos os comandos remotos aqui sao leitura pura
                 (ls, test -w, df, lsblk, mokutil, efibootmgr sem flags
                 de escrita). Levanta SegurancaEfiBloqueadaError na
                 primeira checagem que falhar, com o motivo especifico na
                 mensagem; o chamador (host_processor/executa_boot_efi_remoto)
                 captura e trata como "nao tentado por seguranca", nao
                 como falha de mecanismo.
    PARAMETER: ip, ssh_user, sudo_cmd    - identificacao/privilegio no host
               caminho_log_remoto        - log remoto do host
               caminho_log_local         - log local consolidado
               caminho_log_efi           - log dedicado do Mecanismo 3
               verbose, suprime_tela      - controle de saida
               esp_mount_point            - ponto de montagem da ESP (default /boot/efi)
               boot_label                 - label usado para checar colisao de entrada
               min_free_kb                - espaco livre minimo exigido na ESP (KB)
               force_secureboot           - PERIGOSO. Se True, pula o bloqueio de
                                            Secure Boot ativo (ver --force-efi-
                                            secureboot em __main__.py). Uso
                                            restrito a teste de campo controlado,
                                            com alguem fisicamente presente.
    RETURNS: None, levanta SegurancaEfiBloqueadaError se qualquer
             checagem falhar. Retorno normal (sem excecao) significa
             seguro para prosseguir.
    """
    _log = _fabrica_log(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                        caminho_log_local, caminho_log_efi, verbose, suprime_tela)

    def _ssh(cmd, timeout=15):
        rc, stdout, stderr = ssh_run(ip, ssh_user, cmd, timeout=timeout)
        return rc, stdout.strip(), stderr.strip()

    _log("INFO", "[MEC3] Iniciando checagem de seguranca do Mecanismo 3 (boot EFI).")

    # 1. UEFI confirmado, sem UEFI, nao ha NVRAM de boot para usar.
    rc, out, _ = _ssh("ls /sys/firmware/efi/efivars/ 2>/dev/null | head -1")
    if rc != 0 or not out:
        motivo = "Host nao esta em modo UEFI (Legacy BIOS); Mecanismo 3 nao se aplica."
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)
    _log("INFO", "[MEC3] UEFI confirmado.")

    # 2. efibootmgr precisa existir no host para criar/gerenciar a entrada.
    # Verifica alem do $PATH da sessao (ver _garante_binario_remoto) e
    # tenta instalar via zypper se ausente, antes de bloquear de vez.
    # Caminho resolvido e reaproveitado no passo 7 (checagem de colisao),
    # que tambem chamava "efibootmgr" bare, com o mesmo problema de $PATH.
    efibootmgr_path = _garante_binario_remoto(ip, ssh_user, sudo_cmd, "efibootmgr", "efibootmgr", _log)
    if not efibootmgr_path:
        motivo = "Binario efibootmgr nao encontrado no host (nem apos tentativa de instalacao via zypper)."
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)
    _log("INFO", "[MEC3] efibootmgr disponivel em: {}".format(efibootmgr_path))

    # 3. Secure Boot, maior risco conhecido. O AMIDEEFIx64.EFI/bootx64.efi
    # nao sao assinados por uma cadeia de confianca reconhecida pelo host;
    # com Secure Boot ativo, o firmware recusa executa-los. Nao ha
    # alternativa segura e remota para contornar isso (MOK exige
    # confirmacao fisica na tela, ver manual_operacao.md).
    # mokutil tem o mesmo problema de deteccao do efibootmgr (ver
    # _garante_binario_remoto acima): garante que esta disponivel (e tenta
    # instalar via zypper se ausente) antes de invocar pelo caminho
    # completo, ja que o $PATH da sessao SSH pode nao incluir /usr/sbin.
    mokutil_path = _garante_binario_remoto(ip, ssh_user, sudo_cmd, "mokutil", "mokutil", _log)
    if not mokutil_path:
        motivo = ("Binario mokutil nao encontrado no host (nem apos tentativa de "
                  "instalacao via zypper). Verificacao manual do Secure Boot "
                  "necessaria antes de tentar o Mecanismo 3.")
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)

    # sudo necessario: ler o estado do Secure Boot exige acesso as efivars,
    # normalmente restrito a root (constatado em campo, 2026-07-16, com
    # usuario comum via SSH: sem sudo, mokutil nao da retorno claro e a
    # checagem bloqueava por motivo errado, nao por Secure Boot de fato).
    rc, out, _ = _ssh("{} {} --sb-state 2>/dev/null".format(sudo_cmd, mokutil_path))
    if rc == 0 and out:
        if "enabled" in out.lower():
            if force_secureboot:
                _log("WARNING",
                     "[MEC3] *** --force-efi-secureboot ATIVO *** Secure Boot "
                     "esta habilitado, mas o bloqueio foi pulado via flag "
                     "explicita. A firmware pode recusar o binario nao "
                     "assinado e exigir intervencao fisica para prosseguir "
                     "(tela de Secure Boot Violation).")
            else:
                motivo = "Secure Boot ativo, binario EFI nao assinado seria recusado pelo firmware."
                _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
                raise SegurancaEfiBloqueadaError(motivo)
        # mokutil pode retornar mais de uma linha (ex: "SecureBoot disabled"
        # + "Platform is in Setup Mode", visto em campo na VM de teste).
        # Sem tratar, a 2a linha vaza no log sem timestamp/prefixo (fora do
        # padrao). Junta em uma linha so, igual ao resto do pacote (ver
        # bios_amidelnx.py, free_out).
        _log("INFO", "[MEC3] Secure Boot: {}".format(out.replace("\n", " | ")))
    else:
        # mokutil esta presente (confirmado acima) mas nao deu retorno claro
        # (ex: --sb-state nao suportado nesta versao/hardware). Nao assume
        # seguranca por omissao. Aborta e exige verificacao manual.
        motivo = ("mokutil esta instalado mas nao deu retorno claro para "
                  "--sb-state. Verificacao manual do Secure Boot necessaria "
                  "antes de tentar o Mecanismo 3 neste host.")
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)

    # 4. TPM + criptografia de disco selada, o risco real nao e o TPM
    # existir, e a chave de desbloqueio estar vinculada a medicoes de boot
    # (PCR) que uma entrada de boot temporaria poderia alterar.
    rc, out, _ = _ssh("ls /sys/class/tpm/ 2>/dev/null")
    tpm_presente = (rc == 0 and bool(out))
    _log("INFO", "[MEC3] TPM presente: {}".format("Sim" if tpm_presente else "Nao"))

    if tpm_presente:
        rc, out, _ = _ssh("lsblk -f 2>/dev/null | grep -i crypto_luks")
        luks_presente = (rc == 0 and bool(out))
        rc2, out2, _ = _ssh("grep -i tpm /etc/crypttab 2>/dev/null")
        crypttab_tpm = (rc2 == 0 and bool(out2))
        rc3, out3, _ = _ssh(
            "command -v clevis >/dev/null 2>&1 && clevis luks list -d "
            "$(lsblk -lnpo NAME,FSTYPE 2>/dev/null | awk '$2==\"crypto_LUKS\"{print $1; exit}') "
            "2>/dev/null")
        clevis_tpm = (rc3 == 0 and "tpm2" in out3.lower())

        if luks_presente and (crypttab_tpm or clevis_tpm):
            motivo = ("Disco com criptografia LUKS aparentemente selada em TPM "
                      "(crypttab/clevis tpm2). Alterar o boot pode impedir o "
                      "desbloqueio do disco. Verificacao manual necessaria.")
            _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
            raise SegurancaEfiBloqueadaError(motivo)
        if luks_presente:
            _log("WARNING",
                 "[MEC3] LUKS presente mas sem indicio de selagem em TPM "
                 "(crypttab/clevis), prosseguindo, mas registre esta checagem.")

    # 5. ESP montada e gravavel.
    rc, out, _ = _ssh("mountpoint -q {} && echo MONTADA".format(shlex.quote(esp_mount_point)))
    if rc != 0 or "MONTADA" not in out:
        motivo = "Particao EFI ({}) nao esta montada.".format(esp_mount_point)
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)

    # Testa gravacao via sudo, nao como o usuario comum: a copia real dos
    # arquivos (_copia_para_esp) usa sudo mv para o destino final, entao
    # testar "test -w" sem sudo aqui checa a coisa errada -- constatado em
    # campo (2026-07-16) que isso bloqueava mesmo quando a copia real
    # funcionaria normal (ESP so e gravavel para root, o que e o esperado
    # e ja contornado pela copia via sudo).
    rc, out, _ = _ssh("{} test -w {} && echo GRAVAVEL".format(
        sudo_cmd, shlex.quote(esp_mount_point)))
    if rc != 0 or "GRAVAVEL" not in out:
        motivo = "Particao EFI ({}) nao esta gravavel (nem com sudo).".format(esp_mount_point)
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)
    _log("INFO", "[MEC3] Particao EFI ({}) montada e gravavel (via sudo).".format(esp_mount_point))

    # 6. Espaco livre suficiente na ESP.
    rc, out, _ = _ssh("df --output=avail -k {} 2>/dev/null | tail -1".format(
        shlex.quote(esp_mount_point)))
    try:
        livre_kb = int(out.strip())
    except (ValueError, AttributeError):
        motivo = "Nao foi possivel determinar o espaco livre na particao EFI."
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)

    if livre_kb < min_free_kb:
        motivo = "Espaco livre na particao EFI insuficiente: {} KB livres, minimo exigido {} KB.".format(
            livre_kb, min_free_kb)
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)
    _log("INFO", "[MEC3] Espaco livre na ESP: {} KB (minimo exigido: {} KB).".format(
        livre_kb, min_free_kb))

    # 7. Sem colisao com entrada de boot ja existente com o mesmo label
    # (por exemplo, sobra de uma execucao anterior que nao limpou direito).
    # sudo + caminho completo (ver efibootmgr_path no passo 2): sem os
    # dois, "efibootmgr" bare pode falhar tanto por $PATH quanto por
    # permissao (leitura de NVRAM normalmente exige root), dando falso
    # negativo (nao acusa colisao que na verdade existe).
    rc, out, _ = _ssh("{} {} 2>/dev/null | grep -F {}".format(
        sudo_cmd, efibootmgr_path, shlex.quote(boot_label)))
    if rc == 0 and out:
        motivo = ("Ja existe uma entrada de boot chamada '{}' na NVRAM deste host "
                  "(possivel sobra de execucao anterior). Verifique manualmente "
                  "com 'efibootmgr -v' antes de tentar de novo.").format(boot_label)
        _log("ERROR", "[MEC3] BLOQUEADO -- {}".format(motivo))
        raise SegurancaEfiBloqueadaError(motivo)

    _log("INFO", "[MEC3] Checagem de seguranca APROVADA -- host elegivel para o Mecanismo 3.")


def _detecta_disco_e_particao_esp(ip, ssh_user, esp_mount_point):
    """
    NAME: _detecta_disco_e_particao_esp
    DESCRIPTION: Descobre o disco fisico e o numero da particao da ESP,
                 nos formatos que efibootmgr --disk/--part exigem. Usa
                 /sys/class/block/<particao>/partition para o numero
                 (robusto contra qualquer esquema de nomenclatura --
                 sda1, nvme0n1p1, etc., ao contrario de tentar extrair
                 o numero do nome via regex).
    PARAMETER: ip, ssh_user     - identificacao do host
               esp_mount_point   - ponto de montagem da ESP
    RETURNS: tuple(str, str), (disco, particao), ou (None, None) se nao
             foi possivel determinar.
    """
    cmd = (
        "ESP_SRC=$(findmnt -n -o SOURCE {esp}) && "
        "ESP_BASE=$(basename \"$ESP_SRC\") && "
        "DISK=$(lsblk -no pkname \"$ESP_SRC\" 2>/dev/null) && "
        "PARTNUM=$(cat /sys/class/block/\"$ESP_BASE\"/partition 2>/dev/null) && "
        "echo \"/dev/$DISK $PARTNUM\""
    ).format(esp=shlex.quote(esp_mount_point))
    rc, out, _ = ssh_run(ip, ssh_user, cmd, timeout=15)
    if rc != 0 or not out.strip():
        return None, None
    partes = out.strip().split()
    if len(partes) != 2:
        return None, None
    return partes[0], partes[1]


def executa_boot_efi_remoto(ip, ssh_user, sudo_cmd, tag, args,
                             caminho_log_remoto, caminho_log_local,
                             caminho_log_efi):
    """
    NAME: executa_boot_efi_remoto
    DESCRIPTION: Executa o Mecanismo 3 completo: checagem de seguranca,
                 copia dos binarios para a ESP, geracao do startup.nsh
                 (so /CA, mesmo escopo do restante do script), criacao
                 da entrada de boot temporaria, reboot, espera pelo
                 retorno do host (timeout configuravel) e confirmacao do
                 valor gravado. Sempre tenta limpar a entrada de boot e os
                 arquivos copiados na ESP ao final, em sucesso ou falha
                 (a excecao e o caso TRAVADO-POS-REBOOT, onde a limpeza
                 remota e impossivel por definicao).
    PARAMETER: ip, ssh_user, sudo_cmd - identificacao/privilegio no host
               tag                    - valor de 14 digitos a gravar (Chassis Asset Tag)
               args                   - namespace do argparse (efi_local_dir,
                                        efi_timeout, verbose, csv)
               caminho_log_remoto     - log remoto do host
               caminho_log_local      - log local consolidado
               caminho_log_efi        - log dedicado do Mecanismo 3
    RETURNS: str, "OK-efiboot", "BLOQUEADO-<motivo>" (seguranca reprovou,
             nada foi tocado no host), "FALHOU-efiboot" (host voltou mas a
             tag nao confere) ou "TRAVADO-POS-REBOOT" (host nao respondeu
             via SSH dentro do timeout, requer intervencao fisica).
    """
    _log = _fabrica_log(ip, ssh_user, sudo_cmd, caminho_log_remoto,
                        caminho_log_local, caminho_log_efi,
                        args.verbose, args.csv)

    def _log_local(nivel, msg):
        # Log local-only (sem SSH para o host): usado na janela de reboot,
        # quando o host esta inacessivel por definicao. Evita gastar o
        # timeout do SSH tentando gravar no host que esta reiniciando.
        # Escreve no log consolidado no MESMO formato das demais linhas
        # (ts - [IP] - NIVEL - msg), no log dedicado do MEC3 e no stdout
        # (se verbose), uma unica vez.
        gravar_log_local_consolidado(ip, nivel, msg, caminho_log_local,
                                     args.verbose, args.csv)
        if caminho_log_efi:
            gravar_log(caminho_log_efi, nivel, "[{}] {}".format(ip, msg),
                       False, True)

    def _ssh(cmd, timeout=15):
        return ssh_run(ip, ssh_user, cmd, timeout=timeout)

    esp = DEFAULT_ESP_MOUNT_POINT
    label = DEFAULT_EFI_BOOT_LABEL
    subdir = DEFAULT_EFI_REMOTE_SUBDIR
    remoto_dir = "{}/EFI/{}".format(esp, subdir)

    # 0. Idempotencia: remove sobras nossas de uma execucao anterior que
    # terminou de forma anormal (kill, crash, queda de energia) e nao
    # chegou a limpar. Sem isso, a re-execucao contra o mesmo host ficaria
    # BLOQUEADO para sempre pela colisao de label. So mexe em artefatos
    # nossos (label UPDATE_DMI_TAG_TEMP e diretorio EFI/UPDATEDMITAG),
    # nunca na configuracao de boot real do host.
    _limpa_sobra_anterior(ip, ssh_user, sudo_cmd, label, remoto_dir, _log)

    # 1. Checagem de seguranca, aborta ANTES de tocar em qualquer coisa
    # se qualquer condicao nao for segura. (A colisao de label so
    # bloquearia agora se a limpeza acima tiver falhado, defesa extra.)
    try:
        verifica_seguranca_efi_remoto(
            ip, ssh_user, sudo_cmd, caminho_log_remoto, caminho_log_local,
            caminho_log_efi, args.verbose, args.csv,
            esp_mount_point=esp, boot_label=label,
            force_secureboot=getattr(args, "force_efi_secureboot", False))
    except SegurancaEfiBloqueadaError as e:
        return "BLOQUEADO-{}".format(str(e)[:60])

    amide_local = os.path.join(args.efi_local_dir, "AMIDEEFIx64.EFI")
    shell_local = os.path.join(args.efi_local_dir, "bootx64.efi")

    if not os.path.isfile(amide_local) or not os.path.isfile(shell_local):
        motivo = "Binarios do Mecanismo 3 nao encontrados em {}.".format(args.efi_local_dir)
        _log("ERROR", "[MEC3] {}".format(motivo))
        return "BLOQUEADO-{}".format(motivo[:60])

    # 2. Cria o diretorio remoto e copia os binarios + startup.nsh gerado
    # dinamicamente (so /CA, com a tag real deste host).
    _log("INFO", "[MEC3] Preparando particao EFI remota em {}.".format(remoto_dir))
    rc, _, stderr = _ssh("{} mkdir -p {}".format(sudo_cmd, shlex.quote(remoto_dir)))
    if rc != 0:
        motivo = "Falha ao criar diretorio remoto na ESP: {}".format(stderr.strip())
        _log("ERROR", "[MEC3] {}".format(motivo))
        return "FALHOU-efiboot"

    sucesso, erro = _copia_para_esp(
        ip, ssh_user, sudo_cmd, amide_local, "{}/AMIDEEFIx64.EFI".format(remoto_dir))
    if not sucesso:
        _log("ERROR", "[MEC3] Falha ao copiar AMIDEEFIx64.EFI: {}".format(erro))
        return "FALHOU-efiboot"

    sucesso, erro = _copia_para_esp(
        ip, ssh_user, sudo_cmd, shell_local, "{}/bootx64.efi".format(remoto_dir))
    if not sucesso:
        _log("ERROR", "[MEC3] Falha ao copiar bootx64.efi: {}".format(erro))
        return "FALHOU-efiboot"

    # startup.nsh gerado dinamicamente, so /CA, mesmo escopo do restante
    # do script (amidelnx_64/amibios_dmi tambem so tocam o Chassis Asset Tag).
    # O "cd" e necessario porque o shell auto-executa o startup.nsh com o
    # diretorio atual em FS0:\ (raiz da ESP), nao no diretorio onde o
    # proprio startup.nsh esta (validado em VM real, ver Docs_Test_boot/).
    # FS0: selecionado explicitamente antes do cd -- constatado em teste
    # real (Precision 5520, 2026-07-14) que o shell inicia sem nenhum
    # drive mapeado como atual (prompt "Shell>", nao "FS0:\>"), entao
    # "cd \caminho" relativo falhava com "Current directory not
    # specified" e o AMIDEEFIx64.EFI nunca era encontrado (%lasterror%
    # = 0xE, Not Found). Corrigido definitivamente aqui.
    # BLOCO DE DEBUG PERMANENTE (Precision 5520, 2026-07-14): a saida do
    # AMIDEEFIx64.EFI e redirecionada para FS0:\amide_debug.log (fora de
    # remoto_dir, de proposito -- _limpa_entrada_e_arquivos faz rm -rf no
    # remoto_dir logo apos o reboot, e apagaria o log antes de conseguirmos
    # ler). Lido via SSH e anexado ao log local mais abaixo. Mantido de
    # forma definitiva (nao e mais para reverter), decisao tomada apos o
    # incidente de travamento abaixo, para ajudar na operacao em volume.
    # Checkpoints de progresso (campo, 2026-07-16): host PERTOSA GA-H81M-S2PH
    # travou apos o reboot sem retornar via SSH (incidente TM7984020398,
    # 10.24.80.96) e o amide_debug.log nunca chegou a existir, entao nao
    # deu para saber em qual linha do startup.nsh o travamento ocorreu.
    # Cada linha grava seu proprio checkpoint em FS0:\amide_debug.log antes
    # do proximo comando rodar (">" so na primeira, ">>" nas seguintes), para
    # que, mesmo travando no meio, o log parcial ja gravado sobreviva a um
    # reset fisico e possa ser lido depois via SSH.
    conteudo_nsh = (
        "echo -off\n"
        "echo MEC3-DEBUG: startup.nsh iniciado > FS0:\\amide_debug.log\n"
        "FS0:\n"
        "echo MEC3-DEBUG: apos FS0: >> FS0:\\amide_debug.log\n"
        "cd \\EFI\\{0}\n"
        "echo MEC3-DEBUG: apos cd EFI\\{0} >> FS0:\\amide_debug.log\n"
        "echo MEC3-DEBUG: antes de executar AMIDEEFIx64.EFI >> FS0:\\amide_debug.log\n"
        "AMIDEEFIx64.EFI /CA \"{1}\" >> FS0:\\amide_debug.log\n"
        "echo MEC3-DEBUG: apos AMIDEEFIx64.EFI, lasterror=%lasterror% >> FS0:\\amide_debug.log\n"
        "reset\n"
    ).format(subdir, tag)
    caminho_nsh_tmp = "{}.nsh_tmp_{}".format(caminho_log_local or "efi_boot", ip)
    try:
        with open(caminho_nsh_tmp, "w", encoding="ascii") as f:
            f.write(conteudo_nsh)
        sucesso, erro = _copia_para_esp(
            ip, ssh_user, sudo_cmd, caminho_nsh_tmp, "{}/startup.nsh".format(remoto_dir))
    finally:
        if os.path.isfile(caminho_nsh_tmp):
            os.remove(caminho_nsh_tmp)
    if not sucesso:
        _log("ERROR", "[MEC3] Falha ao copiar startup.nsh: {}".format(erro))
        return "FALHOU-efiboot"

    _log("INFO", "[MEC3] Arquivos copiados para a ESP com sucesso.")

    # 3. Descobre disco/particao da ESP e cria a entrada de boot.
    disco, particao = _detecta_disco_e_particao_esp(ip, ssh_user, esp)
    if not disco or not particao:
        _log("ERROR", "[MEC3] Nao foi possivel determinar disco/particao da ESP.")
        return "FALHOU-efiboot"
    _log("INFO", "[MEC3] ESP em {} particao {}.".format(disco, particao))

    # BootOrder original, capturada ANTES de criar a entrada temporaria,
    # para restaurar logo em seguida (ver comentario abaixo sobre o
    # risco de loop de reboot).
    ordem_original = None
    rc, out_ordem, _ = _ssh("{} efibootmgr".format(sudo_cmd))
    if rc == 0:
        for linha in out_ordem.splitlines():
            if linha.strip().startswith("BootOrder:"):
                ordem_original = linha.split(":", 1)[1].strip()
                break

    loader = r"\EFI\{}\bootx64.efi".format(subdir)
    cmd_create = "{} efibootmgr --create --disk {} --part {} --label {} --loader '{}'".format(
        sudo_cmd, shlex.quote(disco), shlex.quote(particao),
        shlex.quote(label), loader)
    rc, out, stderr = _ssh(cmd_create)
    if rc != 0:
        _log("ERROR", "[MEC3] Falha ao criar entrada de boot: {}".format(stderr.strip()))
        return "FALHOU-efiboot"

    boot_num = None
    for linha in out.splitlines():
        if label in linha and linha.strip().startswith("Boot"):
            boot_num = linha.strip()[4:8]
            break
    if not boot_num:
        _log("ERROR", "[MEC3] Entrada de boot criada, mas nao foi possivel identificar o numero (BootXXXX).")
        _ssh("{} efibootmgr | grep -F {}".format(sudo_cmd, shlex.quote(label)))
        return "FALHOU-efiboot"
    _log("INFO", "[MEC3] Entrada de boot criada: Boot{}.".format(boot_num))

    # IMPORTANTE: "efibootmgr --create" tambem insere a entrada nova na
    # BootOrder (nao so no BootNext, que e de uso unico). Se a entrada
    # ficar na BootOrder, QUALQUER reboot seguinte a este (inclusive o
    # "reset" do proprio startup.nsh, independente de sucesso ou falha
    # do AMIDEEFIx64.EFI) vai cair de novo nela, gerando um loop de
    # reboot que nunca deixa o SO subir, entao o SSH nunca volta e a
    # limpeza automatica (abaixo) nunca roda. Restaurar a BootOrder
    # original aqui, sem a entrada nova, garante que so ESTE boot (via
    # BootNext) use a entrada temporaria; qualquer reboot seguinte,
    # por qualquer motivo, vai direto para o SO normal, mesmo que a
    # limpeza nunca chegue a rodar. Validado em VM real (ver
    # Docs_Test_boot/).
    if ordem_original:
        rc, _, stderr = _ssh("{} efibootmgr --bootorder {}".format(sudo_cmd, ordem_original))
        if rc != 0:
            _log("WARNING",
                 "[MEC3] Nao foi possivel restaurar a BootOrder original ({}): {}. "
                 "Risco de loop de reboot se a limpeza automatica falhar.".format(
                     ordem_original, stderr.strip()))
    else:
        _log("WARNING",
             "[MEC3] Nao foi possivel capturar a BootOrder original antes da "
             "criacao da entrada. Risco de loop de reboot se a limpeza "
             "automatica falhar.")

    rc, _, stderr = _ssh("{} efibootmgr --bootnext {}".format(sudo_cmd, boot_num))
    if rc != 0:
        _log("ERROR", "[MEC3] Falha ao definir BootNext: {}".format(stderr.strip()))
        _limpa_entrada_e_arquivos(ip, ssh_user, sudo_cmd, boot_num, remoto_dir, _log)
        return "FALHOU-efiboot"
    _log("INFO", "[MEC3] BootNext definido para Boot{}. Reiniciando o host...".format(boot_num))

    # 4. Reinicia. A conexao SSH cai junto, isso e esperado, nao e erro.
    _ssh("{} reboot".format(sudo_cmd), timeout=5)

    # 5. Espera o host voltar, com timeout configuravel. Toda a
    # comunicacao aqui e via _log_local (nunca _log/SSH remoto), porque
    # o host esta reiniciando e inacessivel: tentar gravar log nele
    # gastaria o timeout do SSH a cada linha.
    timeout = getattr(args, "efi_timeout", DEFAULT_EFI_REBOOT_TIMEOUT)
    _log_local("INFO", "[MEC3] Aguardando o host voltar (timeout: {} s)...".format(timeout))
    inicio = time.time()
    voltou = False
    proximo_heartbeat = 30
    # Da uma folga inicial para o host realmente cair antes de comecar a
    # tentar reconectar (evita falso-positivo testando a conexao antiga).
    time.sleep(15)
    while time.time() - inicio < timeout:
        if testa_porta_ssh(ip, timeout=3.0) and testa_conexao_ssh(ip, ssh_user):
            voltou = True
            break
        # Heartbeat na tela/log local a cada ~30s, para deixar claro que
        # a ferramenta esta viva e aguardando (nao travada).
        decorrido = int(time.time() - inicio)
        if decorrido >= proximo_heartbeat:
            _log_local("INFO",
                       "[MEC3] ...ainda aguardando o host voltar "
                       "({} s de {} s decorridos).".format(decorrido, timeout))
            proximo_heartbeat = decorrido + 30
        time.sleep(10)

    if not voltou:
        # Host nao respondeu: por definicao esta inacessivel, entao o log
        # e local-only (tentar gravar nele so gastaria o timeout do SSH).
        _log_local("ERROR",
                   "[MEC3] ATENCAO, host nao respondeu via SSH em {} s apos o reboot. "
                   "Pode ter ficado preso no EFI Shell (BootNext nao consumido ou "
                   "startup.nsh travado). REQUER INTERVENCAO FISICA para verificar "
                   "e, se necessario, forcar o boot normal.".format(timeout))
        return "TRAVADO-POS-REBOOT"

    _log("INFO", "[MEC3] Host respondeu via SSH novamente apos o reboot.")

    # Le o log de saida do AMIDEEFIx64.EFI (gravado em FS0:\amide_debug.log
    # pelo startup.nsh, fora de remoto_dir de proposito -- ver comentario na
    # geracao do startup.nsh, acima), anexa ao log local/efi, depois apaga o
    # arquivo do ESP. O UEFI Shell grava a saida redirecionada (">") em
    # UTF-16LE com BOM; decodifica antes de logar e de checar assinaturas de
    # incompatibilidade, senao o texto fica ilegivel ("F a i l   t o ...").
    saida_dbg_limpa = ""
    rc_dbg, saida_dbg, _ = _ssh("{} cat /boot/efi/amide_debug.log 2>/dev/null".format(sudo_cmd))
    if rc_dbg == 0 and saida_dbg.strip():
        # ssh_run decodifica o stdout byte-a-byte (locale padrao, ver
        # subprocess.run com universal_newlines=True em ssh_utils.py), entao
        # saida_dbg preserva 1:1 os bytes originais do arquivo. Reencode com
        # latin-1 (bijetivo para 0-255) para recuperar os bytes crus, depois
        # decodifica como UTF-16LE de verdade (o UEFI Shell grava a saida
        # redirecionada ">" nesse formato, com BOM FF FE no inicio).
        try:
            saida_dbg_limpa = saida_dbg.encode("latin-1", errors="ignore").decode(
                "utf-16-le", errors="ignore")
        except (UnicodeDecodeError, UnicodeEncodeError):
            saida_dbg_limpa = saida_dbg
        saida_dbg_limpa = saida_dbg_limpa.lstrip(chr(0xFEFF)).strip()
        _log("INFO", "[MEC3][DEBUG] Saida do AMIDEEFIx64.EFI capturada no boot:")
        _log("INFO", "[MEC3][DEBUG]   +----------------------------------- INICIO ----------------------------------------+")
        for linha_dbg in saida_dbg_limpa.splitlines():
            linha_dbg = linha_dbg.strip()
            if linha_dbg:
                _log("INFO", "[MEC3][DEBUG]   {}".format(linha_dbg))
        _log("INFO", "[MEC3][DEBUG]   +------------------------------------- FIM ------------------------------------------+")
        _ssh("{} rm -f /boot/efi/amide_debug.log".format(sudo_cmd))
    else:
        _log("WARNING", "[MEC3][DEBUG] amide_debug.log nao encontrado ou vazio na ESP.")

    # 6. Confirma o valor gravado e limpa a entrada de boot + arquivos da ESP.
    rc, tag_lida, _ = _ssh("{} dmidecode -s chassis-asset-tag 2>/dev/null".format(sudo_cmd))
    tag_lida = tag_lida.strip()
    _limpa_entrada_e_arquivos(ip, ssh_user, sudo_cmd, boot_num, remoto_dir, _log)

    if rc == 0 and tag_lida == tag:
        _log("INFO", "[MEC3] Tag confirmada apos reboot: '{}'.".format(tag_lida))
        return "OK-efiboot"

    # Assinatura conhecida de incompatibilidade de firmware na propria
    # saida do AMIDEEFIx64.EFI (ver constants.SINAIS_INCOMPATIBILIDADE_HW),
    # constatado em campo (Dell Precision 5520, 2026-07-14): "Fail to
    # initialize SMBIOS" / "DMI Data write failed", rodando em pre-boot,
    # sem SO/kernel envolvido -- rejeicao da propria firmware, nao um
    # problema transitorio do Mecanismo 3 em si.
    if eh_incompatibilidade_firmware(saida_dbg_limpa):
        _log("ERROR",
             "[MEC3] Tag apos reboot ('{}') nao confere com o esperado ('{}'). "
             "Assinatura de incompatibilidade de firmware detectada na saida "
             "do AMIDEEFIx64.EFI (ver [MEC3][DEBUG] acima).".format(tag_lida, tag))
        return "INCOMPATIVEL-efiboot"

    _log("ERROR", "[MEC3] Tag apos reboot ('{}') nao confere com o esperado ('{}').".format(
        tag_lida, tag))
    return "FALHOU-efiboot"


def _limpa_sobra_anterior(ip, ssh_user, sudo_cmd, label, remoto_dir, _log):
    """
    NAME: _limpa_sobra_anterior
    DESCRIPTION: Torna o Mecanismo 3 idempotente. Remove sobras de uma
                 execucao anterior que terminou de forma anormal (kill,
                 crash, queda de energia) e nao chegou a limpar: entradas
                 de boot na NVRAM com o NOSSO label e o NOSSO diretorio na
                 ESP. Sem isso, uma re-execucao contra o mesmo host ficaria
                 BLOQUEADA para sempre pela colisao de label. So mexe em
                 artefatos criados por esta ferramenta (label
                 UPDATE_DMI_TAG_TEMP, dir EFI/UPDATEDMITAG); nunca toca na
                 configuracao de boot real do host. Melhor esforco: falhas
                 sao logadas mas nao interrompem o fluxo (a checagem de
                 seguranca seguinte ainda bloqueia se a sobra persistir).
    PARAMETER: ip, ssh_user, sudo_cmd - identificacao/privilegio no host
               label                   - label das entradas a remover
               remoto_dir              - diretorio nosso na ESP a remover
               _log                    - funcao de log ja fechada sobre o host
    RETURNS: None
    """
    rc, out, _ = ssh_run(ip, ssh_user, "{} efibootmgr".format(sudo_cmd), timeout=15)
    if rc == 0:
        numeros = []
        for linha in out.splitlines():
            # Linhas do tipo "Boot0001* UPDATE_DMI_TAG_TEMP  HD(...)".
            if label in linha and linha.strip().startswith("Boot"):
                numeros.append(linha.strip()[4:8])
        for num in numeros:
            r, _, err = ssh_run(
                ip, ssh_user, "{} efibootmgr -b {} -B".format(sudo_cmd, num), timeout=15)
            if r == 0:
                _log("WARNING",
                     "[MEC3] Sobra de execucao anterior removida: entrada de boot "
                     "Boot{} ({}).".format(num, label))
            else:
                _log("WARNING",
                     "[MEC3] Nao foi possivel remover a sobra Boot{}: {}.".format(
                         num, err.strip()))

    ssh_run(ip, ssh_user, "{} rm -rf {}".format(sudo_cmd, shlex.quote(remoto_dir)),
            timeout=15)


def _limpa_entrada_e_arquivos(ip, ssh_user, sudo_cmd, boot_num, remoto_dir, _log):
    """
    NAME: _limpa_entrada_e_arquivos
    DESCRIPTION: Remove a entrada de boot temporaria da NVRAM e os
                 arquivos copiados para a ESP. Melhor esforco, loga
                 falhas mas nao interrompe o fluxo (o resultado principal
                 do Mecanismo 3 ja foi decidido antes desta chamada).
    PARAMETER: ip, ssh_user, sudo_cmd - identificacao/privilegio no host
               boot_num                - numero da entrada (ex: "0005")
               remoto_dir              - diretorio criado na ESP
               _log                    - funcao de log ja fechada sobre o host
    RETURNS: None
    """
    if boot_num:
        rc, _, stderr = ssh_run(
            ip, ssh_user, "{} efibootmgr -b {} -B".format(sudo_cmd, boot_num), timeout=15)
        if rc != 0:
            _log("WARNING",
                 "[MEC3] Nao foi possivel remover a entrada de boot Boot{} "
                 "automaticamente: {}. Remova manualmente com 'efibootmgr -b {} -B'.".format(
                     boot_num, stderr.strip(), boot_num))
        else:
            _log("INFO", "[MEC3] Entrada de boot Boot{} removida.".format(boot_num))

    rc, _, stderr = ssh_run(
        ip, ssh_user, "{} rm -rf {}".format(sudo_cmd, shlex.quote(remoto_dir)), timeout=15)
    if rc != 0:
        _log("WARNING",
             "[MEC3] Nao foi possivel remover {} da ESP automaticamente: {}.".format(
                 remoto_dir, stderr.strip()))
    else:
        _log("INFO", "[MEC3] Arquivos temporarios removidos da ESP.")
