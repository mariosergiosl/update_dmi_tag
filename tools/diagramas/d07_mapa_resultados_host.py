"""Gerador do diagrama 07_mapa_resultados_host do manual (SVG; PNG via gera_diagramas.py).

Recuperado em 15/10/2026 do historico da sessao de 17 a 20/07/2026.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.environ.get("DIAGRAMAS_SAIDA", ".")
from svg_helper import Diagrama, COR_INICIO_FIM, COR_ACAO, COR_OK, COR_ALERTA, COR_DECISAO

W = 1180
d = Diagrama(W, 100, "Mapa de Resultados: todos os desfechos possiveis de um host")
CX = 330
GAP = 20

d.rotulo(W/2, 46, "Visao condensada de referencia (complementa os diagramas 1-4, que mostram o "
         "passo a passo). Cada host termina em EXATAMENTE um destes resultados.",
         font_size=11.5, ancora="middle", cor="#555555")

y = 75
_, _, _, h = d.caixa(CX - 260, y, 520, 38, "Host entra na Fase 1 (triagem)",
                     cor=COR_INICIO_FIM, negrito=True, max_chars=44)
y += h + GAP


def spine(y, texto, max_chars=26, dh=52, lw=340):
    d.seta(CX, y - GAP, CX, y)
    lx = CX - lw / 2
    d.losango(lx, y, lw, dh, texto, max_chars=max_chars, font_size=11.5)
    return y + dh


def ramo(y_gate, dh, alvo_x, alvo_y, cor, texto, max_chars=26, w=300, h=40,
         rotulo=""):
    tip_y = y_gate + dh / 2
    tip_x = CX + 170
    d.linha_cotovelo([(tip_x, tip_y), (alvo_x, alvo_y + h/2)], tracejada=False)
    if rotulo:
        d.rotulo(tip_x + 8, tip_y - 6, rotulo, font_size=10, ancora="start")
    d.caixa(alvo_x, alvo_y, w, h, texto, cor=cor, max_chars=max_chars, font_size=11)


X_OUT = 720

y = spine(y, "Fase 1: porta 22 sem resposta,\nou sem chave e sem senha?", dh=54, max_chars=34)
ramo(y - 54, 54, X_OUT, y - 54 - 4, COR_ALERTA,
     "INACESSIVEL (v2.3.6, por motivo)\nrede: porta 22 sem resposta\nacesso: sem chave e sem senha",
     rotulo="Sim", h=62, max_chars=34)
y += GAP

y = spine(y, "Fase 2: porta fechou, nenhum\nperfil entrou ou sem sudo?", dh=54, max_chars=34)
ramo(y - 54, 54, X_OUT, y - 54 - 8, COR_ALERTA,
     "INACESSIVEL rede (porta fechou) ou\nacesso (login falhou em todos os perfis)\n"
     "/ SEM-SUDO (nenhum perfil com sudo)",
     rotulo="Sim", h=70, max_chars=40)
y += GAP

y = spine(y, "BEM_NUMERO ausente\nou invalido?", dh=54)
ramo(y - 54, 54, X_OUT, y - 54 + 7, COR_ALERTA,
     "PENDENTE (ausente)  /  INVALIDO\n(formato ou digito verificador)", rotulo="Sim", h=44, max_chars=36)
y += GAP

y = spine(y, "--write ativo E tag_antes\nja == tag esperada?", dh=58)
ramo(y - 58, 58, X_OUT, y - 58 + 7, COR_OK,
     "OK-ja-correto\nnenhum mecanismo executado",
     rotulo="Sim", h=44)
y += GAP

y = spine(y, "Modo e dry-run\n(sem --write)?", dh=52)
ramo(y - 52, 52, X_OUT, y - 52 + 4, "#e8e8e8",
     "DRY-RUN\napenas simulacao, nada gravado",
     rotulo="Sim", h=40)
y += GAP

d.caixa(CX - 220, y, 440, 40, "Cascata de escrita real: Mecanismo 1 -> 2 -> 3",
        cor=COR_ACAO, negrito=True, max_chars=44)
y += 40 + GAP
d.seta(CX, y - GAP, CX, y)

y_cascata_top = y

y1 = spine(y, "Mecanismo 1\n(amidelnx_64) sucesso?", dh=50, max_chars=22)
ramo(y1 - 50, 50, X_OUT, y1 - 50 + 5, COR_OK, "OK-amidelnx", rotulo="Sim", h=32)
y = y1 + GAP

y2 = spine(y, "Mecanismo 2\n(amibios_dmi) sucesso?", dh=50, max_chars=22)
ramo(y2 - 50, 50, X_OUT, y2 - 50 + 5, COR_OK, "OK-amibios", rotulo="Sim", h=32)
y = y2 + GAP

y3 = spine(y, "Ambos falharam com\nassinatura de firmware\nconhecida?", dh=64,
           max_chars=22)
ramo(y3 - 64, 64, X_OUT, y3 - 64 + 12, COR_ALERTA,
     "INCOMPATIVEL-HW\n(sem --allow-efi-fallback)", rotulo="Sim, sem EFI", h=40)
y = y3 + GAP

y4 = spine(y, "--allow-efi-fallback\native?", dh=50, max_chars=20)
ramo(y4 - 50, 50, X_OUT, y4 - 50 + 5, COR_ALERTA,
     "FALHOU-todos\n(falha generica, sem EFI)", rotulo="Nao", h=40)
y = y4 + GAP

d.rotulo(CX + 30, y - GAP + 15, "Sim: Mecanismo 3", font_size=10.5, ancora="start")
d.secao(CX - 260, y_cascata_top - 8, 700, (y - y_cascata_top) + 8, "")

d.caixa(CX - 220, y, 440, 34, "Mecanismo 3 (boot EFI, reboot fisico)",
        cor=COR_ACAO, font_size=11, max_chars=44)
y += 34 + GAP
d.seta(CX, y - GAP, CX, y)

y5 = spine(y, "Checagem de seguranca\nbloqueou?", dh=50, max_chars=22)
ramo(y5 - 50, 50, X_OUT, y5 - 50 + 5, COR_ALERTA,
     "BLOQUEADO-<motivo>\n(nada foi tocado no host)", rotulo="Sim", h=40)
y = y5 + GAP

y6 = spine(y, "Host respondeu via SSH\napos o reboot?", dh=50, max_chars=22)
ramo(y6 - 50, 50, X_OUT, y6 - 50 + 5, COR_ALERTA,
     "TRAVADO-POS-REBOOT\nrequer intervencao fisica", rotulo="Nao", h=40)
y = y6 + GAP

y7 = spine(y, "Tag apos reboot ==\nesperada?", dh=50, max_chars=20)
ramo(y7 - 50, 50, X_OUT, y7 - 50 + 5, COR_OK, "OK-efiboot", rotulo="Sim", h=32)
y = y7 + GAP

y8 = spine(y, "Assinatura de firmware\nconhecida no debug log?", dh=54,
           max_chars=22)
ramo(y8 - 54, 54, X_OUT, y8 - 54 + 8, COR_ALERTA,
     "INCOMPATIVEL-efiboot", rotulo="Sim", h=32)
d.rotulo(CX + 30, y8 + GAP + 4, "Nao", font_size=10.5, ancora="start")
y = y8 + GAP

d.caixa(CX - 220, y, 440, 40, "FALHOU-efiboot\n(host voltou, tag nao confere, "
        "causa nao mapeada)", cor=COR_ALERTA, negrito=True, max_chars=44,
        font_size=11)
y += 40

y += 30
d.rotulo(W/2, y, "LEGENDA", font_size=12, ancora="middle", negrito=True)
y += 16
legendas = [
    (COR_ALERTA, "Falha, bloqueio ou pendencia (exige acao do operador)"),
    (COR_OK, "Sucesso (tag gravada ou ja correta)"),
    ("#e8e8e8", "Simulacao (nenhuma gravacao real)"),
]
lx = (W - (300 * 3 + 40 * 2)) / 2
for cor, texto in legendas:
    d.caixa(lx, y, 300, 40, texto, cor=cor, font_size=10.5, max_chars=32)
    lx += 340
y += 40

ALTURA_FINAL = int(y + 30)
d.altura = ALTURA_FINAL
svg = d.render()
with open(os.path.join(SAIDA, "07_mapa_resultados_host.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("altura final:", ALTURA_FINAL)
