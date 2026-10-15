"""Gerador do diagrama 06_execucao_paralela_timeline do manual (SVG; PNG via gera_diagramas.py).

Recuperado em 15/10/2026 do historico da sessao de 17 a 20/07/2026.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.environ.get("DIAGRAMAS_SAIDA", ".")
from svg_helper import Diagrama, COR_INICIO_FIM, COR_ACAO, COR_OK, COR_ALERTA, COR_DECISAO

W = 1140
d = Diagrama(W, 100, "Execucao Paralela (--parallel N): fases e linha do tempo por host")
CX = W / 2

y0 = 55
_, _, _, h = d.caixa(60, y0, W - 120, 44,
                     "Inicio: le hosts.txt e as credenciais (perfis do --acesso ou senha unica)",
                     cor=COR_INICIO_FIM, negrito=True, max_chars=60)
y = y0 + h + 26
d.seta(CX, y - 26, CX, y)

d.secao(30, y - 10, W - 60, 90, "FASE 1: TRIAGEM (sequencial, todos os hosts)")
_, _, _, h = d.caixa(60, y + 18, W - 120, 44,
                     "testa_porta_ssh() + testa_conexao_ssh() de cada perfil (ate --ssh-timeout) "
                     "para cada host, um de cada vez", max_chars=80)
y = y + 18 + h + 26
d.seta(CX, y - 26, CX, y)

# ---- Fase 2: 3 colunas paralelas com alturas diferentes (tempo) ----
sec2_y0 = y - 10
LANE_W = 300
GAP_LANE = 40
total_lanes = LANE_W * 3 + GAP_LANE * 2
x0 = (W - total_lanes) / 2
xs = [x0, x0 + LANE_W + GAP_LANE, x0 + 2 * (LANE_W + GAP_LANE)]

d.rotulo(45, y + 30, "tempo", font_size=11, ancora="middle", negrito=True,
         cor="#555555")

y_submit = y + 16
for x in xs:
    d.caixa(x, y_submit, LANE_W, 34, "executor.submit(_worker)",
            cor=COR_ACAO, font_size=11, max_chars=30)

# Cada lane tem sua propria sequencia/altura, simulando duracoes diferentes
lanes = [
    {
        "ip": "192.168.56.11",
        "passos": [
            (30, "conecta, detecta sudo"),
            (30, "coleta ambiente"),
            (34, "Mecanismo 1: OK-amidelnx"),
        ],
        "resultado": "[2/3] .11 -> OK-amidelnx",
    },
    {
        "ip": "192.168.56.12",
        "passos": [
            (30, "conecta, detecta sudo"),
            (30, "coleta ambiente"),
            (30, "Mecanismo 1: falha"),
            (34, "Mecanismo 2: OK-amibios"),
        ],
        "resultado": "[1/3] .12 -> OK-amibios",
    },
    {
        "ip": "192.168.56.13",
        "passos": [
            (30, "conecta, detecta sudo"),
            (30, "coleta ambiente"),
            (26, "Mec 1 e 2: falha"),
            (30, "checagem de seguranca"),
            (44, "Mecanismo 3: reboot,\naguarda ate 900s"),
            (34, "OK-efiboot"),
        ],
        "resultado": "[3/3] .13 -> OK-efiboot",
    },
]

y_ends = []
for x, lane in zip(xs, lanes):
    yy = y_submit + 34 + 10
    d.rotulo(x + LANE_W / 2, yy - 2, "log: hosts/{}.log".format(lane["ip"]),
             font_size=9.5, ancora="middle", cor="#777777")
    yy += 12
    for h_box, texto in lane["passos"]:
        d.caixa(x, yy, LANE_W, h_box, texto, font_size=10.5, max_chars=34)
        yy += h_box + 8
    y_ends.append(yy)

y_max = max(y_ends)
for x, lane, y_end in zip(xs, lanes, y_ends):
    d.linha_simples(x + LANE_W / 2, y_end - 8, x + LANE_W / 2, y_max + 14,
                    tracejada=True, cor="#aaaaaa")
    d.rotulo(x + LANE_W / 2, y_max + 30, lane["resultado"], font_size=10,
             ancora="middle", negrito=True, cor="#155724")

y_conv = y_max + 55
for x in xs:
    d.seta(x + LANE_W / 2, y_conv - 14, CX, y_conv)

d.secao(30, sec2_y0, W - 60, (y_conv - sec2_y0) + 6,
        "FASE 2: PARALELA (ThreadPoolExecutor, ate N em voo; cada host "
        "isolado, sem lock, sem estado compartilhado)")

y = y_conv + 26
_, _, _, h = d.caixa(60, y, W - 120, 40,
                     "Todas as threads concluidas (with ThreadPoolExecutor "
                     "sai, aguarda todas terminarem)", cor=COR_OK, max_chars=68)
y = y + h + 26
d.seta(CX, y - 26, CX, y)

d.secao(30, y - 10, W - 60, 90, "FASE 3: MERGE (sequencial, apos a fase paralela)")
_, _, _, h = d.caixa(60, y + 18, W - 120, 50,
                     "Junta os logs por host no consolidado, na ORDEM do "
                     "hosts.txt (nao na ordem de conclusao)", max_chars=70)
y = y + 18 + h + 26
d.seta(CX, y - 26, CX, y)

_, _, _, h = d.caixa(60, y, W - 120, 40,
                     "Resumo agregado final (summary.py)",
                     cor=COR_INICIO_FIM, negrito=True, max_chars=60)
y = y + h + 26
d.seta(CX, y - 26, CX, y)
_, _, _, h = d.caixa(60, y, W - 120, 40,
                     "v2.3.6: <log>_inacessiveis_rede.txt e <log>_inacessiveis_acesso.txt "
                     "(triagem e Fase 2)", cor=COR_ACAO, max_chars=110)
y = y + h

ALTURA_FINAL = int(y + 30)
d.altura = ALTURA_FINAL
svg = d.render()
with open(os.path.join(SAIDA, "06_execucao_paralela_timeline.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("altura final:", ALTURA_FINAL)
