"""Gerador do diagrama 02_fluxo_codigo_funcoes_decisoes do manual (SVG; PNG via gera_diagramas.py).

Recuperado em 15/10/2026 do historico da sessao de 17 a 20/07/2026.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.environ.get("DIAGRAMAS_SAIDA", ".")
from svg_helper import Diagrama, COR_INICIO_FIM, COR_ACAO, COR_OK, COR_ALERTA

W = 1040
d = Diagrama(W, 100, "Fluxo de Codigo: Funcoes e Pontos de Decisao (processa_host_remoto)")
CX = W / 2
BW = 660
GAP = 26


def fn_box(y, funcao, modulo, desc, cor="#ffffff", max_chars=56):
    _, _, _, h = d.caixa_fn(CX - BW/2, y, BW, funcao, modulo, desc,
                             cor=cor, max_chars=max_chars)
    return y + h + GAP


def box(y, texto, h=40, cor="#ffffff", max_chars=58, negrito=False):
    _, _, _, h_real = d.caixa(CX - BW/2, y, BW, h, texto, cor=cor,
                               max_chars=max_chars, negrito=negrito)
    return y + h_real + GAP


def seta_ate(y_novo):
    d.seta(CX, y_novo - GAP, CX, y_novo)


def decisao(y, texto, texto_lateral, texto_lateral_box, cor_lateral,
            max_chars=20, box_w=300, box_font=11, dh=74, lw=340):
    lx = CX - lw / 2
    d.losango(lx, y, lw, dh, texto, max_chars=max_chars)
    tip_x, tip_y = lx + lw, y + dh / 2
    box_x = tip_x + 45
    _, _, _, box_h_real = d.caixa(box_x, tip_y - 26, box_w, 52, texto_lateral_box,
                                   cor=cor_lateral, max_chars=box_w // 9, font_size=box_font)
    # recentraliza verticalmente caso a caixa tenha crescido
    d.linha_cotovelo([(tip_x, tip_y), (box_x, tip_y)])
    d.rotulo(tip_x + 10, tip_y - 8, texto_lateral, font_size=11, ancora="start")
    return y + dh


y = 55
y = box(y, "__main__.py: parse_args() + perfis de acesso: carrega_perfis_acesso(--acesso) "
        "ou perfil_da_linha_de_comando() (acesso.py, v2.3.0)",
        h=50, cor=COR_INICIO_FIM, max_chars=58, negrito=True)
seta_ate(y)

y = fn_box(y, "le_arquivo_hosts(caminho)", "hosts.py",
           "Le hosts.txt; ignora vazias/comentarios; retorna [(ip, bem), ...]")
seta_ate(y)

y = fn_box(y, "triagem_hosts_remotos(hosts, args, log)", "host_processor.py",
           "Fase 1: testa_porta_ssh() (2 s) + testa_conexao_ssh() perfil a perfil "
           "(ssh_utils.py, ate --ssh-timeout). OFFLINE = rede, NEGADO = acesso. "
           "Separa hosts_validos x descartados.")
seta_ate(y)

y = box(y, "Loop principal: sequencial ou ThreadPoolExecutor(--parallel N)",
        h=40, cor=COR_ACAO)
seta_ate(y)

y = fn_box(y, "processa_host_remoto(ip, bem, args, ...)", "host_processor.py",
           "Passo 1: conectividade.")
seta_ate(y)

y2 = decisao(y, "chave_ja_validada?\n(Fase 1 confirmou)", "Nao",
             "testa_porta_ssh() (fechada: INACESSIVEL rede) e "
             "prepara_autenticacao_ssh() perfil a perfil (ssh_bootstrap.py; "
             "nenhum entra: INACESSIVEL acesso)", COR_ALERTA, max_chars=20, dh=104)
d.rotulo(CX + 22, y2 + 16, "Sim (pula retest)", font_size=10.5, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y = fn_box(y, "_detecta_sudo_perfil(ip, perfil)", "host_processor.py",
           "Passo 2: sudo sem senha, com a senha do usuario ou a do root; sem sudo, "
           "tenta o proximo perfil (v2.3.1); nenhum: so coleta dados.")
seta_ate(y)

y = fn_box(y, "coletar_dados_ambiente_remoto(...)", "environment.py",
           "Passo 3: kernel, placa, BIOS, SMBIOS, WSMT, UEFI, tag_antes "
           "(dmidecode), MAC.")
seta_ate(y)

y = box(y, "Passo 4: loop ssh_run('rpm -q PACOTE') para 4 pacotes (log DEBUG)",
        h=42)
seta_ate(y)

y = fn_box(y, "le_valor_configuracao_remoto(...)", "bbconfig.py",
           "Passo 5: le BEM_NUMERO de /etc/BBconfig.conf remoto.")
seta_ate(y)

y2 = decisao(y, "bem_numero_lista\n(hosts.txt) fornecido?", "Nao",
             "Usa bem_conf do BBconfig; se tambem ausente -> return PENDENTE",
             COR_ALERTA, max_chars=20, dh=64)
d.rotulo(CX + 22, y2 + 16, "Sim: usa da lista", font_size=10.5, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y = fn_box(y, "valida_e_calcula_tag(bem_usar)", "patrimonio.py",
           "Passo 7: valida formato (13/14 digitos); calcula_dv_modulo11() "
           "(Modulo 11, DV=10 vira 'X'); levanta ValueError se invalido.")
seta_ate(y)

y2 = decisao(y, "ValueError na\nvalidacao?", "Sim",
             "except ValueError: registro['resultado']='INVALIDO'; "
             "return registro", COR_ALERTA, max_chars=16, dh=64)
d.rotulo(CX + 22, y2 + 16, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y2 = decisao(y, "not sudo_confirmado\nE (args.write ou\nargs.test_write)?", "Sim",
             "return registro['resultado']='SEM-SUDO' (escrita abortada)",
             COR_ALERTA, max_chars=22, dh=74)
d.rotulo(CX + 22, y2 + 16, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y2 = decisao(y, "args.write E not\nargs.test_write E\ntag_antes == tag_esperada?",
             "Sim", "resultado_escrita = 'OK-ja-correto' (nenhum mecanismo "
             "chamado)", COR_OK, max_chars=24, dh=78)
d.rotulo(CX + 22, y2 + 16, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y = fn_box(y, "tenta_escrever_tag_remoto(ip, tag, args, ...)", "write_cascade.py",
           "Passo 8: cascata Mecanismo 1 -> 2 -> 3. Ver diagrama dedicado da "
           "cascata.", cor=COR_ACAO)
seta_ate(y)

y2 = decisao(y, "str(resultado_escrita)\n.startswith('OK')\nE args.write?", "Sim",
             "sincroniza_bbconfig_remoto(...) (bbconfig.py): backup + "
             "atualiza BEM_NUMERO", COR_ACAO, max_chars=22, dh=78)
d.rotulo(CX + 22, y2 + 16, "Nao: bbconfig_sync=N/A", font_size=10.5, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y2 = decisao(y, "args.test_write\native?", "Sim",
             "tenta_teste_escrita_remoto(...) (write_cascade.py): rewrite "
             "no-op, restaura tag virgem se aplicavel", COR_ACAO,
             max_chars=16, dh=66)
d.rotulo(CX + 22, y2 + 16, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y2 = decisao(y, "args.production\native?", "Sim",
             "Se resultado OK: _executa_acoes_production() -> "
             "reinstall-enable + reboot. Senao: WARNING, nada executado.",
             COR_ACAO, max_chars=16, dh=70)
d.rotulo(CX + 22, y2 + 16, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y = box(y, "return registro (dict completo para a linha de resumo)",
        h=42, cor=COR_INICIO_FIM, negrito=True)
seta_ate(y)

y = fn_box(y, "monta_tabela_resumo(registros)", "summary.py",
           "Apos todos os hosts: tabela detalhada + sumario agregado por "
           "codigo de resultado (OK-*, FALHOU-*, INVALIDO, etc.)",
           cor=COR_INICIO_FIM)
seta_ate(y)

y = fn_box(y, "grava_inacessiveis_por_motivo(registros, hosts, log)", "hosts.py",
           "v2.3.6: <log>_inacessiveis_rede.txt e <log>_inacessiveis_acesso.txt, "
           "pelo campo motivo_inacessivel do registro (formato do --hosts)",
           cor=COR_ACAO)

ALTURA_FINAL = int(y - GAP + 30)
d.altura = ALTURA_FINAL
svg = d.render()
with open(os.path.join(SAIDA, "02_fluxo_codigo_funcoes_decisoes.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("altura final:", ALTURA_FINAL)
