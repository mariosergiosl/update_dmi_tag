"""Gerador do diagrama 08_topologia_rede do manual (SVG; PNG via gera_diagramas.py).

Recuperado em 15/10/2026 do historico da sessao de 17 a 20/07/2026.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.environ.get("DIAGRAMAS_SAIDA", ".")
from svg_helper import Diagrama, COR_INICIO_FIM, COR_ACAO, COR_OK, COR_ALERTA, COR_DECISAO

W = 1080
H = 760
d = Diagrama(W, H, "Topologia de Rede: Modo Remoto (--hosts)")
CX = W / 2

y = 60
_, _, _, h_op = d.caixa(
    CX - 260, y, 520, 130,
    "Maquina do Operador\n"
    "update_dmi_tag.py (ou pacote instalado via RPM)\n"
    "amidelnx_64 (NDA)  |  AMIDEEFIx64.EFI + bootx64.efi (NDA/aberto)\n"
    "rpm/ (KMP amibios_dmi, aberto)  |  hosts.txt  |  .ssh_pass",
    cor=COR_INICIO_FIM, negrito=False, max_chars=58, font_size=12)
y_op_bottom = y + h_op

y_legenda = y_op_bottom + 18
d.rotulo(CX, y_legenda, "SSH (porta 22): bootstrap de chave, comandos "
         "remotos, checagens  |  SCP: copia de amidelnx_64, RPMs do KMP, "
         "binarios do Mecanismo 3", font_size=10.5, ancora="middle",
         cor="#555555")

y_seta_origem = y_legenda + 25
y_hosts = y_seta_origem + 90
n_hosts = 4
largura_host = 210
gap_host = 30
total = n_hosts * largura_host + (n_hosts - 1) * gap_host
x0 = (W - total) / 2

xs = [x0 + i * (largura_host + gap_host) for i in range(n_hosts)]
labels = ["Host A\nSLES 15", "Host B\nSLES 15", "Host C\nSLES 15", "Host N\nSLES 15"]

for x, label in zip(xs, labels):
    cx_host = x + largura_host / 2
    d.seta(CX, y_seta_origem, cx_host, y_hosts - 4)
    d.caixa(x, y_hosts, largura_host, 70,
            label + "\nusuario com sudo\n(root bloqueado em producao)",
            cor=COR_ACAO, max_chars=26, font_size=11)

y_nota = y_hosts + 70 + 40
d.secao(40, y_op_bottom + 30, W - 80, (y_nota - (y_op_bottom + 30)) + 10, "")
_, _, _, h_nota = d.caixa(
    CX - 400, y_nota, 800, 60,
    "Cada host e independente: NVRAM, ESP e BBconfig.conf proprios. "
    "Com --parallel N, ate N conexoes SSH simultaneas; sem --parallel "
    "(default), uma de cada vez.",
    cor="#f4f4f4", max_chars=90, font_size=11)

ALTURA_FINAL = int(y_nota + h_nota + 30)
d.altura = ALTURA_FINAL
svg = d.render()
with open(os.path.join(SAIDA, "08_topologia_rede.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("altura final:", ALTURA_FINAL)
