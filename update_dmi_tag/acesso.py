# -*- coding: utf-8 -*-

# =======================================================================
#
# FILE: acesso.py
#
# DESCRIPTION: Perfis de acesso SSH do modo remoto. Le o arquivo informado
#              em --acesso (formato INI, um perfil por secao, com usuario,
#              senha e senha_sudo opcional) e devolve a lista de perfis na
#              ordem do arquivo. Sem --acesso, monta um perfil unico a
#              partir de --ssh-user, da senha SSH efetiva e de --sudo-pass,
#              preservando o comportamento das versoes anteriores.
#
#              A ferramenta tenta os perfis na ordem, maquina a maquina, e
#              usa o primeiro que conseguir entrar. Isso permite um unico
#              lote misturar linhas com acesso pessoal do operador (SLE 12
#              e 15) e linhas acessadas como root com senha temporaria
#              (SLE 11).
#
#              O arquivo guarda senhas em texto puro: e recusado se outros
#              usuarios puderem le-lo (permissao diferente de 600).
#
# AUTHOR: Mario Luz mario.luz@suse.com
# COMPANY: SUSE
# VERSION: 2.3.5
# REVISION: 2026-10-02 - v2.3.5 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-10-02 - v2.3.4 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-09-28 - v2.3.3 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-09-28 - v2.3.2 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# REVISION: 2026-09-24 - v2.3.1 - atualizacao de numero de versao para
#                        consistencia com o restante do pacote; sem mudanca
#                        funcional neste arquivo.
# CREATED: 2026-09-23
# REVISION: 2026-09-23 - v2.3.0 - criado.
#
# =======================================================================

import collections
import configparser
import os
import stat

# Perfil de acesso a um host remoto.
#   nome        - nome da secao no arquivo (aparece no log e no resumo)
#   usuario     - usuario SSH
#   senha       - senha SSH, usada so para autorizar a chave (bootstrap)
#   senhas_sudo - senhas a tentar no sudo, em ordem, depois da tentativa
#                 sem senha (tupla, pode ser vazia)
Perfil = collections.namedtuple("Perfil", "nome usuario senha senhas_sudo")

CHAVES_ACEITAS = frozenset({"usuario", "senha", "senha_sudo"})


class ArquivoAcessoInvalido(Exception):
    """Arquivo de perfis de acesso ausente, inseguro ou mal formado."""


def _confere_permissao(caminho):
    """
    NAME: _confere_permissao
    DESCRIPTION: Recusa o arquivo se grupo ou outros usuarios tiverem
                 qualquer permissao sobre ele, do mesmo jeito que o ssh
                 recusa uma chave privada exposta. So vale em sistemas
                 POSIX, onde a ferramenta roda em modo remoto.
    PARAMETER: caminho - caminho do arquivo de acesso
    RETURNS: None; levanta ArquivoAcessoInvalido se a permissao for aberta
    """
    if os.name != "posix":
        return
    modo = stat.S_IMODE(os.stat(caminho).st_mode)
    if modo & 0o077:
        raise ArquivoAcessoInvalido(
            "arquivo de acesso '{}' tem permissao {:o}; contem senhas e "
            "precisa ser legivel so pelo dono. Corrija com: chmod 600 {}".format(
                caminho, modo, caminho))


def _senhas_sudo(senha_sudo, senha, senhas_root):
    """
    NAME: _senhas_sudo
    DESCRIPTION: Monta a ordem de senhas que o sudo vai tentar depois da
                 tentativa sem senha. Com senha_sudo preenchida, usa so
                 ela. Vazia, tenta a senha do proprio perfil (padrao do
                 sudo) e depois as senhas dos perfis de root (padrao SUSE,
                 'Defaults targetpw'). Remove vazias e repetidas.
    PARAMETER: senha_sudo  - valor de senha_sudo do perfil
               senha       - senha SSH do perfil
               senhas_root - senhas dos perfis cujo usuario e root
    RETURNS: tuple of str
    """
    if senha_sudo:
        return (senha_sudo,)
    ordem = []
    for s in [senha] + list(senhas_root):
        if s and s not in ordem:
            ordem.append(s)
    return tuple(ordem)


def carrega_perfis_acesso(caminho):
    """
    NAME: carrega_perfis_acesso
    DESCRIPTION: Le o arquivo de perfis de acesso. Cada secao e um perfil;
                 a ordem das secoes e a ordem de tentativa. Comentarios so
                 em linha inteira (# ou ;): tudo o que vem depois do '='
                 e o valor, inclusive '#' e ';', porque senhas geradas
                 costumam conter esses caracteres. Sem interpolacao, pelo
                 mesmo motivo ('%' e literal).
    PARAMETER: caminho - caminho do arquivo de acesso
    RETURNS: list of Perfil, na ordem do arquivo
    """
    if not os.path.isfile(caminho):
        raise ArquivoAcessoInvalido(
            "arquivo de acesso nao encontrado: {}".format(caminho))
    _confere_permissao(caminho)

    parser = configparser.ConfigParser(
        interpolation=None,
        delimiters=("=",),
        comment_prefixes=("#", ";"),
        inline_comment_prefixes=None,
        strict=True,
        default_section="__nenhuma__",
    )
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            parser.read_file(f)
    except (configparser.Error, UnicodeDecodeError) as e:
        raise ArquivoAcessoInvalido(
            "arquivo de acesso '{}' mal formado: {}".format(caminho, e))

    secoes = parser.sections()
    if not secoes:
        raise ArquivoAcessoInvalido(
            "arquivo de acesso '{}' nao tem nenhum perfil ([nome])".format(
                caminho))

    brutos = []
    for nome in secoes:
        chaves = set(parser[nome].keys())
        desconhecidas = sorted(chaves - CHAVES_ACEITAS)
        if desconhecidas:
            raise ArquivoAcessoInvalido(
                "perfil [{}]: chave(s) desconhecida(s): {} (aceitas: {})".format(
                    nome, ", ".join(desconhecidas),
                    ", ".join(sorted(CHAVES_ACEITAS))))
        usuario = parser[nome].get("usuario", "").strip()
        if not usuario:
            raise ArquivoAcessoInvalido(
                "perfil [{}]: 'usuario' ausente ou vazio".format(nome))
        brutos.append((nome, usuario,
                       parser[nome].get("senha", ""),
                       parser[nome].get("senha_sudo", "")))

    senhas_root = [senha for _, usuario, senha, _ in brutos
                   if usuario == "root" and senha]
    return [Perfil(nome, usuario, senha,
                   _senhas_sudo(senha_sudo, senha, senhas_root))
            for nome, usuario, senha, senha_sudo in brutos]


def perfil_da_linha_de_comando(args):
    """
    NAME: perfil_da_linha_de_comando
    DESCRIPTION: Perfil unico equivalente ao comportamento anterior a
                 v2.3.0: usuario de --ssh-user, senha SSH efetiva
                 (--ssh-pass, SSH_PASS ou --ssh-pass-file) e, no sudo, so
                 a senha de --sudo-pass, se informada.
    PARAMETER: args - namespace do argparse
    RETURNS: list of Perfil, com um unico elemento
    """
    sudo_pass = getattr(args, "sudo_pass", "") or ""
    return [Perfil("linha-de-comando",
                   getattr(args, "ssh_user", ""),
                   getattr(args, "ssh_pass_efetiva", "") or "",
                   (sudo_pass,) if sudo_pass else ())]


def descreve_perfis(perfis):
    """
    NAME: descreve_perfis
    DESCRIPTION: Texto de uma linha para o cabecalho do log, sem senhas.
    PARAMETER: perfis - lista de Perfil
    RETURNS: str, ex.: "operador (f4683594), root (root)"
    """
    return ", ".join("{} ({})".format(p.nome, p.usuario) for p in perfis)
