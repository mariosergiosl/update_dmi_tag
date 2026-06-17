# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: bbconfig.py
#
# DESCRIPTION: Leitura e sincronizacao do arquivo de configuracao
#              corporativo (BBconfig.conf). le_valor_configuracao e
#              le_valor_configuracao_remoto leem BEM_NUMERO local/remoto
#              (sempre logam, mesmo se a lista de hosts tiver
#              precedencia). sincroniza_bbconfig_remoto e
#              sincroniza_bbconfig_local atualizam BEM_NUMERO apos
#              gravacao bem-sucedida na BIOS (--write), com backup
#              imutavel (chattr +i, melhor esforco) e rollback em falha.
#
# AUTHOR: Mario Luz
# COMPANY: SUSE -- consultor BB
# VERSION: 2.1.8
# CREATED: 2026-06-12
# REVISION: 2026-06-12 - v2.1.2 - extraido de update_dmi_tag.py na
#                        modularizacao em pacote. Conteudo identico,
#                        apenas imports ajustados para o pacote.
#
# =======================================================================

import os
import subprocess
import time

from .constants import PatrimonioPendenteError, _detecta_usuario_sessao
from .logging_utils import gravar_log, gravar_log_remoto
from .ssh_utils import ssh_run, _filtra_banner


def le_valor_configuracao(caminho_config, nome_var, caminho_log, verbose,
                           suprime_tela, caminho_log_local=""):
    """
    NAME: le_valor_configuracao
    DESCRIPTION: Parsing manual e leve do arquivo de configuracao chave=valor.
                 Nao utiliza a biblioteca re para otimizacao de memoria e
                 portabilidade (Python 3.6+ stdlib puro). Ignora linhas
                 vazias e comentarios (# e ;). Remove aspas delimitadoras.
                 Levanta PatrimonioPendenteError se a variavel nao for
                 encontrada (estado pendente, nao falha de erro).
    PARAMETER: caminho_config    - caminho do arquivo de configuracao
               nome_var          - nome da variavel a extrair
               caminho_log       - log principal
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: str -- valor extraido
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    _log("DEBUG", "Iniciando leitura de {}...".format(caminho_config))

    if not os.path.exists(caminho_config):
        _log("ERROR", "Configuracao ausente: {}".format(caminho_config))
        raise FileNotFoundError(
            "Arquivo de configuracao nao encontrado: {}".format(caminho_config))

    with open(caminho_config, "r", encoding="utf-8", errors="ignore") as f:
        for linha in f:
            linha_limpa = linha.strip()
            if not linha_limpa or linha_limpa.startswith(("#", ";")):
                continue
            if "=" in linha_limpa:
                partes = linha_limpa.split("=", 1)
                chave = partes[0].strip()
                if chave == nome_var:
                    valor = partes[1].strip().strip("'\"")
                    _log("INFO", "Variavel '{}' extraida: {}".format(nome_var, valor))
                    return valor

    # Variavel ausente e estado pendente em producao (DBUS popula depois).
    raise PatrimonioPendenteError(
        "Variavel '{}' ausente em {}: provisionamento pendente, nada a gravar.".format(
            nome_var, caminho_config))


def le_valor_configuracao_remoto(ip, ssh_user, caminho_config, nome_var,
                                  caminho_log, caminho_log_local,
                                  verbose, suprime_tela, sudo_cmd=""):
    """
    NAME: le_valor_configuracao_remoto
    DESCRIPTION: Le o valor de uma variavel do arquivo de configuracao em
                 um host remoto via SSH. Sempre loga o que encontrou no
                 arquivo remoto, independentemente de o valor ser sobrescrito
                 pelo BEM_NUMERO da lista de hosts. Retorna string vazia se
                 a variavel nao for encontrada (estado pendente remoto).
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH
               caminho_config    - caminho do arquivo de configuracao remoto
               nome_var          - nome da variavel a extrair
               caminho_log       - log remoto
               caminho_log_local - log consolidado local
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               sudo_cmd          - prefixo sudo (opcional, para arquivos restritos)
    RETURNS: str -- valor encontrado no arquivo remoto ou string vazia
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    cmd = "grep '^{}=' {} 2>/dev/null | cut -d= -f2 | tr -d '\"'".format(
        nome_var, caminho_config)
    _, stdout, _ = ssh_run(ip, ssh_user, cmd, timeout=10)
    valor_remoto = stdout.strip()

    if valor_remoto:
        _log("INFO", "BBconfig remoto '{}': {}".format(nome_var, valor_remoto))
    else:
        _log("WARNING", "BBconfig remoto: '{}' ausente em {} (pendente)".format(
            nome_var, caminho_config))

    return valor_remoto


# =======================================================================
# SINCRONIZACAO DO ARQUIVO DE CONFIGURACAO (BBconfig.conf)
#
# Apos a gravacao bem-sucedida da tag na BIOS (resultado_escrita
# comecando com "OK") e somente com --write, sincroniza o valor de
# BEM_NUMERO no arquivo de configuracao se ele divergir do valor usado
# para a gravacao. Faz backup do arquivo original antes de editar,
# marca o backup como imutavel (chattr +i, melhor esforco) e confirma
# o novo valor com grep. Em falha na edicao, tenta rollback a partir
# do backup.
# =======================================================================



def _nome_backup_bbconfig(caminho_config, identificador):
    """
    NAME: _nome_backup_bbconfig
    DESCRIPTION: Monta o nome do arquivo de backup do arquivo de
                 configuracao, no formato:
                   <caminho_config>.<YYYY-MM-DD_HHMMSS>_<identificador>.bak
                 O identificador (geralmente o usuario SSH ou usuario
                 local) permite auditar quem gerou o backup e quando.
    PARAMETER: caminho_config - caminho do arquivo original
               identificador  - usuario a incluir no nome (sem espacos)
    RETURNS: str -- caminho completo do arquivo de backup
    """
    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    ident = "".join(c for c in identificador if c.isalnum() or c in "._-") or "unknown"
    return "{}.{}_{}.bak".format(caminho_config, timestamp, ident)


def sincroniza_bbconfig_remoto(ip, ssh_user, sudo_cmd, caminho_config, nome_var,
                                bem_conf, bem_usado,
                                caminho_log, caminho_log_local,
                                verbose, suprime_tela):
    """
    NAME: sincroniza_bbconfig_remoto
    DESCRIPTION: Sincroniza BEM_NUMERO no arquivo de configuracao remoto
                 quando o valor usado para gravar a tag (bem_usado)
                 difere do valor atualmente presente no arquivo
                 (bem_conf). Fluxo:
                   1. Se bem_conf == bem_usado: nada a fazer (IGUAL).
                   2. Verifica existencia do arquivo remoto.
                   3. Gera nome de backup com timestamp + ssh_user.
                   4. sudo cp -p <config> <backup>
                   5. sudo chattr +i <backup> (melhor esforco; falha
                      nao impede a sincronizacao, apenas gera WARNING).
                   6. sudo sed -i 's/^VAR=.*/VAR="novo"/' <config>
                   7. Confirma com grep que o novo valor esta presente.
                   8. Em falha do passo 6/7, tenta rollback: chattr -i
                      no backup + cp do backup de volta ao original.
                 Todas as etapas sao logadas com prefixo [IP]. O nome
                 do backup gerado e sempre logado quando criado, mesmo
                 se passos posteriores falharem (para permitir limpeza
                 manual).
    PARAMETER: ip                - endereco IP do host remoto
               ssh_user          - usuario SSH (tambem usado no nome
                                    do backup)
               sudo_cmd          - prefixo sudo no host remoto
               caminho_config    - caminho do arquivo de configuracao
               nome_var          - nome da variavel (ex: BEM_NUMERO)
               bem_conf          - valor atual no arquivo ("PENDENTE"
                                    se ausente)
               bem_usado         - valor usado para gravar a tag
               caminho_log       - log remoto
               caminho_log_local - log consolidado local
               verbose           - modo verbose
               suprime_tela      - suprime stdout
    RETURNS: dict -- {"sincronizado": bool, "backup": str ou None,
                       "motivo": str}
             motivo e um codigo curto: "IGUAL", "OK", "SEM-ARQUIVO",
             "FALHOU-backup", "FALHOU-chattr-ok-mesmo-assim",
             "FALHOU-sed-rollback-ok", "FALHOU-sed-rollback-falhou",
             "FALHOU-confirmacao".
    """
    def _log(nivel, msg):
        gravar_log_remoto(ip, ssh_user, sudo_cmd, caminho_log, nivel, msg,
                          caminho_log_local, verbose, suprime_tela)

    # 1. Ja sincronizado -- nada a fazer
    if bem_conf and bem_conf == bem_usado:
        _log("DEBUG", "BBconfig.conf ja sincronizado ({}={}).".format(
            nome_var, bem_usado))
        return {"sincronizado": True, "backup": None, "motivo": "IGUAL"}

    # 2. Verifica existencia do arquivo remoto
    rc_test, _, _ = ssh_run(
        ip, ssh_user, "{} test -f {}".format(sudo_cmd, caminho_config),
        timeout=10)
    if rc_test != 0:
        _log("WARNING",
             "BBconfig.conf nao encontrado em {}: sincronizacao pulada.".format(
                 caminho_config))
        return {"sincronizado": False, "backup": None, "motivo": "SEM-ARQUIVO"}

    # 3. Nome do backup
    backup_path = _nome_backup_bbconfig(caminho_config, ssh_user)

    # 4. Backup (cp -p preserva permissoes e timestamps)
    rc_cp, _, err_cp = ssh_run(
        ip, ssh_user,
        "{} cp -p {} {}".format(sudo_cmd, caminho_config, backup_path),
        timeout=15)
    err_cp_limpo = _filtra_banner(err_cp or "").strip()
    if rc_cp != 0:
        _log("ERROR",
             "Falha ao criar backup de {} em {}: {}".format(
                 caminho_config, backup_path, err_cp_limpo or "sem detalhe"))
        return {"sincronizado": False, "backup": None, "motivo": "FALHOU-backup"}

    _log("INFO", "Backup de {} criado: {}".format(caminho_config, backup_path))

    # 5. Imutabilidade do backup (melhor esforco)
    rc_chattr, _, err_chattr = ssh_run(
        ip, ssh_user,
        "{} chattr +i {}".format(sudo_cmd, backup_path),
        timeout=10)
    chattr_ok = (rc_chattr == 0)
    if not chattr_ok:
        _log("WARNING",
             "chattr +i falhou em {} (sistema de arquivos pode nao suportar): {}".format(
                 backup_path, _filtra_banner(err_chattr or "").strip()))

    # 5.5 Verifica se o arquivo original tem chattr +i e remove antes de editar.
    # Em alguns hosts o BBconfig.conf e marcado como imutavel por automacoes
    # anteriores (ex: Puppet, BigFix). O sed -i falha silenciosamente com
    # "nao foi possivel renomear /etc/sedXXXX" se o arquivo for imutavel.
    rc_lsattr, out_lsattr, _ = ssh_run(
        ip, ssh_user,
        "lsattr {} 2>/dev/null | head -1".format(caminho_config),
        timeout=10)
    original_imutavel = (rc_lsattr == 0 and "i" in out_lsattr.split()[0]
                         if out_lsattr.strip() else False)
    if original_imutavel:
        _log("WARNING",
             "BBconfig.conf tem chattr +i (imutavel). Removendo temporariamente "
             "para sincronizacao.")
        ssh_run(ip, ssh_user,
                "{} chattr -i {}".format(sudo_cmd, caminho_config),
                timeout=10)

    # 6. Edita o arquivo original via sed -i
    # Usa aspas simples no shell remoto; nome_var e bem_usado sao
    # numericos/identificadores sem caracteres especiais de sed.
    sed_expr = "s/^{0}=.*/{0}=\"{1}\"/".format(nome_var, bem_usado)
    rc_sed, _, err_sed = ssh_run(
        ip, ssh_user,
        "{} sed -i '{}' {}".format(sudo_cmd, sed_expr, caminho_config),
        timeout=15)
    err_sed_limpo = _filtra_banner(err_sed or "").strip()

    # Se o arquivo era imutavel, restaura o atributo independente do resultado
    if original_imutavel:
        ssh_run(ip, ssh_user,
                "{} chattr +i {}".format(sudo_cmd, caminho_config),
                timeout=10)
        _log("DEBUG", "chattr +i restaurado em {}.".format(caminho_config))

    if rc_sed != 0:
        _log("ERROR",
             "sed -i falhou em {}: {}. Tentando rollback a partir do backup.".format(
                 caminho_config, err_sed_limpo or "sem detalhe"))
        return _rollback_bbconfig(
            ip, ssh_user, sudo_cmd, caminho_config, backup_path,
            chattr_ok, "FALHOU-sed", _log)

    # 7. Confirma o novo valor
    cmd_confirma = "grep '^{}=' {} 2>/dev/null | cut -d= -f2 | tr -d '\"'".format(
        nome_var, caminho_config)
    _, stdout_confirma, _ = ssh_run(ip, ssh_user, cmd_confirma, timeout=10)
    valor_confirmado = stdout_confirma.strip()

    if valor_confirmado != bem_usado:
        _log("ERROR",
             "Confirmacao pos-sed falhou: esperado '{}', encontrado '{}'. "
             "Tentando rollback.".format(bem_usado, valor_confirmado))
        return _rollback_bbconfig(
            ip, ssh_user, sudo_cmd, caminho_config, backup_path,
            chattr_ok, "FALHOU-confirmacao", _log)

    _log("INFO",
         "BBconfig.conf atualizado: {}={} -> {}={}. Backup: {}".format(
             nome_var, bem_conf or "PENDENTE", nome_var, bem_usado, backup_path))

    return {"sincronizado": True, "backup": backup_path, "motivo": "OK"}


def _rollback_bbconfig(ip, ssh_user, sudo_cmd, caminho_config, backup_path,
                       chattr_ok, motivo_base, _log):
    """
    NAME: _rollback_bbconfig
    DESCRIPTION: Restaura o arquivo de configuracao remoto a partir do
                 backup apos falha na edicao. Remove a imutabilidade do
                 backup (se havia sido aplicada) antes de copiar de
                 volta, e a reaplica em seguida para preservar o
                 backup intacto para auditoria posterior.
    PARAMETER: ip, ssh_user, sudo_cmd, caminho_config, backup_path -
               mesmos significados de sincroniza_bbconfig_remoto
               chattr_ok    - se o chattr +i do backup havia funcionado
               motivo_base  - prefixo do motivo de falha original
               _log         - funcao de log fechada sobre o contexto
    RETURNS: dict -- {"sincronizado": False, "backup": backup_path,
                       "motivo": "<motivo_base>-rollback-ok"
                                  ou "<motivo_base>-rollback-falhou"}
    """
    if chattr_ok:
        ssh_run(ip, ssh_user, "{} chattr -i {}".format(sudo_cmd, backup_path),
                timeout=10)

    rc_restore, _, err_restore = ssh_run(
        ip, ssh_user,
        "{} cp -p {} {}".format(sudo_cmd, backup_path, caminho_config),
        timeout=15)

    # Reaplica imutabilidade no backup para preservar evidencia
    if chattr_ok:
        ssh_run(ip, ssh_user, "{} chattr +i {}".format(sudo_cmd, backup_path),
                timeout=10)

    if rc_restore == 0:
        _log("WARNING",
             "Rollback de {} a partir do backup {} concluido.".format(
                 caminho_config, backup_path))
        return {"sincronizado": False, "backup": backup_path,
                "motivo": "{}-rollback-ok".format(motivo_base)}

    _log("ERROR",
         "Rollback de {} FALHOU: {}. Arquivo pode estar em estado "
         "inconsistente. Backup preservado em {}.".format(
             caminho_config,
             _filtra_banner(err_restore or "").strip() or "sem detalhe",
             backup_path))
    return {"sincronizado": False, "backup": backup_path,
            "motivo": "{}-rollback-falhou".format(motivo_base)}


def sincroniza_bbconfig_local(caminho_config, nome_var, bem_conf, bem_usado,
                               caminho_log, verbose, suprime_tela,
                               caminho_log_local=""):
    """
    NAME: sincroniza_bbconfig_local
    DESCRIPTION: Equivalente local (modo standalone) de
                 sincroniza_bbconfig_remoto. Mesma logica de backup com
                 timestamp + usuario local, chattr +i no backup, sed -i
                 no original e confirmacao via grep, com rollback em
                 falha. Todos os comandos sao executados localmente via
                 subprocess com sudo.
    PARAMETER: caminho_config    - caminho do arquivo de configuracao
               nome_var          - nome da variavel (ex: BEM_NUMERO)
               bem_conf          - valor atual no arquivo
               bem_usado         - valor usado para gravar a tag
               caminho_log       - log principal (standalone)
               verbose           - modo verbose
               suprime_tela      - suprime stdout
               caminho_log_local - log consolidado (opcional)
    RETURNS: dict -- mesmo formato de sincroniza_bbconfig_remoto
    """
    def _log(nivel, msg):
        gravar_log(caminho_log, nivel, msg, verbose, suprime_tela,
                   caminho_log_local)

    if bem_conf and bem_conf == bem_usado:
        _log("DEBUG", "BBconfig.conf ja sincronizado ({}={}).".format(
            nome_var, bem_usado))
        return {"sincronizado": True, "backup": None, "motivo": "IGUAL"}

    if not os.path.isfile(caminho_config):
        _log("WARNING",
             "BBconfig.conf nao encontrado em {}: sincronizacao pulada.".format(
                 caminho_config))
        return {"sincronizado": False, "backup": None, "motivo": "SEM-ARQUIVO"}

    identificador = _detecta_usuario_sessao()
    backup_path = _nome_backup_bbconfig(caminho_config, identificador)

    def _run(cmd_lista, timeout=15):
        try:
            r = subprocess.run(cmd_lista, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=timeout,
                                check=False)
            return r.returncode, r.stdout, r.stderr
        except Exception as e:
            return 1, "", str(e)

    rc_cp, _, err_cp = _run(["sudo", "cp", "-p", caminho_config, backup_path])
    if rc_cp != 0:
        _log("ERROR", "Falha ao criar backup de {} em {}: {}".format(
            caminho_config, backup_path, (err_cp or "").strip()))
        return {"sincronizado": False, "backup": None, "motivo": "FALHOU-backup"}

    _log("INFO", "Backup de {} criado: {}".format(caminho_config, backup_path))

    rc_chattr, _, err_chattr = _run(["sudo", "chattr", "+i", backup_path], timeout=10)
    chattr_ok = (rc_chattr == 0)
    if not chattr_ok:
        _log("WARNING",
             "chattr +i falhou em {} (sistema de arquivos pode nao suportar): {}".format(
                 backup_path, (err_chattr or "").strip()))

    sed_expr = "s/^{0}=.*/{0}=\"{1}\"/".format(nome_var, bem_usado)
    rc_sed, _, err_sed = _run(["sudo", "sed", "-i", sed_expr, caminho_config])

    def _rollback_local(motivo_base):
        if chattr_ok:
            _run(["sudo", "chattr", "-i", backup_path], timeout=10)
        rc_restore, _, err_restore = _run(["sudo", "cp", "-p", backup_path, caminho_config])
        if chattr_ok:
            _run(["sudo", "chattr", "+i", backup_path], timeout=10)
        if rc_restore == 0:
            _log("WARNING", "Rollback de {} a partir do backup {} concluido.".format(
                caminho_config, backup_path))
            return {"sincronizado": False, "backup": backup_path,
                    "motivo": "{}-rollback-ok".format(motivo_base)}
        _log("ERROR",
             "Rollback de {} FALHOU: {}. Backup preservado em {}.".format(
                 caminho_config, (err_restore or "").strip(), backup_path))
        return {"sincronizado": False, "backup": backup_path,
                "motivo": "{}-rollback-falhou".format(motivo_base)}

    if rc_sed != 0:
        _log("ERROR", "sed -i falhou em {}: {}. Tentando rollback.".format(
            caminho_config, (err_sed or "").strip()))
        return _rollback_local("FALHOU-sed")

    # Confirma
    try:
        with open(caminho_config, "r", encoding="utf-8", errors="ignore") as f:
            valor_confirmado = ""
            for linha in f:
                linha_l = linha.strip()
                if linha_l.startswith("{}=".format(nome_var)):
                    valor_confirmado = linha_l.split("=", 1)[1].strip().strip("'\"")
                    break
    except Exception as e:
        _log("ERROR", "Falha ao reabrir {} para confirmacao: {}. Tentando rollback.".format(
            caminho_config, e))
        return _rollback_local("FALHOU-confirmacao")

    if valor_confirmado != bem_usado:
        _log("ERROR",
             "Confirmacao pos-sed falhou: esperado '{}', encontrado '{}'. "
             "Tentando rollback.".format(bem_usado, valor_confirmado))
        return _rollback_local("FALHOU-confirmacao")

    _log("INFO",
         "BBconfig.conf atualizado: {}={} -> {}={}. Backup: {}".format(
             nome_var, bem_conf or "PENDENTE", nome_var, bem_usado, backup_path))

    return {"sincronizado": True, "backup": backup_path, "motivo": "OK"}


