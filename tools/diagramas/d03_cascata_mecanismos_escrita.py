"""Gerador do diagrama 03_cascata_mecanismos_escrita do manual (SVG; PNG via gera_diagramas.py).

Recuperado em 15/10/2026 do historico da sessao de 17 a 20/07/2026.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.environ.get("DIAGRAMAS_SAIDA", ".")
from svg_helper import Diagrama, COR_INICIO_FIM, COR_ACAO, COR_OK, COR_ALERTA

W = 1080
d = Diagrama(W, 100, "Cascata de Mecanismos de Escrita (write_cascade.py)")
CX = W / 2
BW = 620
GAP = 26


def fn_box(y, funcao, modulo, desc, cor="#ffffff", max_chars=58):
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
            max_chars=18, box_w=280, box_font=11, dh=64, lw=300):
    lx = CX - lw / 2
    d.losango(lx, y, lw, dh, texto, max_chars=max_chars)
    tip_x, tip_y = lx + lw, y + dh / 2
    box_x = tip_x + 40
    d.caixa(box_x, tip_y - 26, box_w, 52, texto_lateral_box,
            cor=cor_lateral, max_chars=box_w // 9, font_size=box_font)
    d.linha_cotovelo([(tip_x, tip_y), (box_x, tip_y)])
    d.rotulo(tip_x + 10, tip_y - 8, texto_lateral, font_size=11, ancora="start")
    return y + dh


y = 55
y = fn_box(y, "tenta_escrever_tag_remoto(ip, tag, args, ...)", "write_cascade.py",
           "dry_run = not args.write. Recebe tag ja calculada (14 digitos) "
           "de host_processor.py.", cor=COR_INICIO_FIM)
seta_ate(y)

d.secao(CX - BW/2 - 15, y - 10, BW + 30, 330, "MECANISMO 1: amidelnx_64 (binario proprietario AMI)")
y += 12
y = fn_box(y, "executa_amidelnx_remoto(ip, tag, ...)", "bios_amidelnx.py",
           "Copia amidelnx_64 (se ausente) via scp e roda '<bin> /ca TAG' "
           "remotamente via sudo.")
seta_ate(y)

y2 = decisao(y, "dry_run?", "Sim", "return 'DRY-RUN' (nenhuma escrita "
             "real ocorreu)", "#e8e8e8", max_chars=10, dh=50)
d.rotulo(CX + 22, y2 + 14, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y2 = decisao(y, "sucesso na escrita?", "Sim", "return 'OK-amidelnx' "
             "(cascata encerra aqui)", COR_OK, max_chars=14, dh=54)
d.rotulo(CX + 22, y2 + 14, "Nao: guarda detalhe_amidelnx,\ntenta Mecanismo 2",
         font_size=10, ancora="start")
y = y2 + GAP + 14

d.seta(CX, y2, CX, y)

d.secao(CX - BW/2 - 15, y - 10, BW + 30, 330, "MECANISMO 2: amibios_dmi (modulo de kernel, via sysfs)")
y += 12
y = fn_box(y, "executa_amibios_remoto(ip, tag, ...)", "bios_sysfs.py",
           "Garante o modulo carregado (instala KMP via rpm se ausente) e "
           "grava em /sys/firmware/amibios/chassis/asset_tag (com sudo).")
seta_ate(y)

y2 = decisao(y, "dry_run?", "Sim", "return 'DRY-RUN'", "#e8e8e8",
             max_chars=10, dh=50)
d.rotulo(CX + 22, y2 + 14, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y2 = decisao(y, "sucesso na escrita?", "Sim", "return 'OK-amibios' "
             "(cascata encerra aqui)", COR_OK, max_chars=14, dh=54)
d.rotulo(CX + 22, y2 + 14, "Nao: guarda detalhe_amibios",
         font_size=10, ancora="start")
y = y2 + GAP + 14
d.seta(CX, y2, CX, y)

y = box(y, "Mecanismos 1 e 2 falharam. eh_incompatibilidade_firmware() "
        "(constants.py) analisa as mensagens de erro de ambos.",
        h=48, cor=COR_ACAO)
seta_ate(y)

y2 = decisao(y, "args.allow_efi_fallback\native?", "Sim",
             "MECANISMO 3: executa_boot_efi_remoto(...) (boot_efi.py). "
             "Ver diagramas dedicados (seguranca + execucao).",
             COR_ACAO, max_chars=18, dh=64, box_w=320)
d.rotulo(CX + 22, y2 + 16, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y2 = decisao(y, "ambos com assinatura de\nincompatibilidade de\nfirmware conhecida?",
             "Sim", "return 'INCOMPATIVEL-HW' (firmware nao "
             "implementa a interface AMI)", COR_ALERTA, max_chars=22, dh=76)
d.rotulo(CX + 22, y2 + 16, "Nao", font_size=11, ancora="start")
y = y2 + GAP
d.seta(CX, y2, CX, y)

y = box(y, "return 'FALHOU-todos' (falha generica/transitoria: rede, "
        "sudo, timeout)", h=42, cor=COR_ALERTA, negrito=True)

ALTURA_FINAL = int(y - GAP + 30)
d.altura = ALTURA_FINAL
svg = d.render()
with open(os.path.join(SAIDA, "03_cascata_mecanismos_escrita.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("altura final:", ALTURA_FINAL)
