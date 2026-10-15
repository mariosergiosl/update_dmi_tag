"""Gerador do diagrama 01_fluxo_macro_operacao do manual (SVG; PNG via gera_diagramas.py).

Recuperado em 15/10/2026 do historico da sessao de 17 a 20/07/2026.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.environ.get("DIAGRAMAS_SAIDA", ".")
from svg_helper import Diagrama, COR_INICIO_FIM, COR_ACAO, COR_DECISAO, COR_OK, COR_ALERTA

W = 980
d = Diagrama(W, 100, "Fluxo Macro de Operacao (update_dmi_tag.py)")
CX = W / 2
BW = 560


def decisao(d, y, texto, texto_lateral, texto_lateral_box, cor_lateral,
            max_chars=20, box_w=260, box_h=50, box_font=11, dh=70):
    """Desenha um losango centralizado em CX na altura y, com um ramo lateral
    (direita) rotulado e uma caixa de destino, e retorna o y de saida (continuacao
    para baixo, sem rotulo, pois so ha uma saida vertical por diagrama aqui)."""
    lw = 300 if max_chars > 20 else 260
    lx = CX - lw / 2
    d.losango(lx, y, lw, dh, texto, max_chars=max_chars)
    tip_x, tip_y = lx + lw, y + dh / 2
    box_x = tip_x + 55
    d.caixa(box_x, tip_y - box_h / 2, box_w, box_h, texto_lateral_box,
            cor=cor_lateral, max_chars=box_w // 9, font_size=box_font)
    d.linha_cotovelo([(tip_x, tip_y), (box_x, tip_y)])
    d.rotulo(tip_x + 10, tip_y - 8, texto_lateral, font_size=11, ancora="start")
    return y + dh


y = 55
d.caixa(CX - BW/2, y, BW, 46, "Inicio: update_dmi_tag.py --hosts hosts.txt [flags]",
        cor=COR_INICIO_FIM, negrito=True, max_chars=46)

y += 46 + 34
d.seta(CX, y-34, CX, y)
d.caixa(CX - BW/2, y, BW, 64, "Le hosts.txt (IP ou IP,BEM por linha) e as credenciais: "
        "perfis do --acesso (v2.3.0) ou senha unica (--ssh-pass > SSH_PASS > "
        "--ssh-pass-file)", max_chars=56)

y += 64 + 34
d.seta(CX, y-34, CX, y)
sec1_y = y - 8
d.caixa(CX - BW/2, y+22, BW, 64, "Para cada host: testa porta TCP 22 (2 s) e a chave "
        "SSH de cada perfil, sem senha (ate --ssh-timeout, padrao 30 s)", max_chars=62)
y = y + 22 + 64

y += 24
y2 = decisao(d, y, "Online e com\nacesso (chave OK ou\nsenha disponivel)?",
             "Nao", "INACESSIVEL: porta 22 sem resposta = rede; "
             "sem chave e sem senha = acesso (hosts_inacessiveis_*.txt)", COR_ALERTA,
             max_chars=20, box_h=78)
d.secao(CX - BW/2 - 15, sec1_y, BW + 30, (y2 - sec1_y) + 20, "FASE 1: TRIAGEM (todos os hosts)")
d.rotulo(CX + 22, y2 + 18, "Sim", font_size=11, ancora="start")
y = y2 + 30

d.seta(CX, y2, CX, y)
d.caixa(CX - BW/2, y, BW, 40, "Lista de hosts validos (online + chave ou senha)",
        cor=COR_OK, max_chars=52)
y += 40

y += 30
d.seta(CX, y-30, CX, y)
sec2_y = y - 8
d.rotulo(CX - BW/2 + 10, y+14, "FASE 2: PROCESSAMENTO POR HOST (processa_host_remoto) "
         "-- sequencial ou --parallel N", ancora="start", font_size=12, negrito=True,
         cor="#555555")
y += 22

etapas = [
    (78, "Bootstrap SSH perfil a perfil: chave pelo sshd do alvo (ed25519 a partir "
         "do OpenSSH 6.5, RSA antes) e ssh-copy-id com a senha; nenhum perfil entra: "
         "INACESSIVEL (acesso)"),
    (60, "Detecta sudo (sem senha, senha do usuario, senha do root); sem sudo, "
         "tenta o proximo perfil"),
    (60, "Coleta dados de ambiente: kernel, placa-mae, BIOS, SMBIOS, WSMT, "
         "UEFI, tag atual (dmidecode), MAC"),
    (46, "Audita RPMs relevantes (patrimonial, amibios-dmi, userspace)"),
    (50, "Resolve BEM_NUMERO: lista de hosts tem precedencia sobre "
         "BBconfig.conf remoto"),
    (50, "Valida formato e calcula DV (Modulo 11) -> tag esperada de 14 digitos"),
]
for h, texto in etapas:
    d.caixa(CX - BW/2, y, BW, h, texto, max_chars=48)
    y += h + 18
    d.seta(CX, y-18, CX, y)
y -= 18

y += 6
y2 = decisao(d, y, "BEM invalido\nou ausente?", "Sim",
             "Host marcado INVALIDO ou PENDENTE; processamento "
             "encerra aqui", COR_ALERTA, max_chars=16)
d.rotulo(CX + 22, y2 + 18, "Nao", font_size=11, ancora="start")
y = y2 + 30
d.seta(CX, y2, CX, y)

y2 = decisao(d, y, "sudo confirmado E\n(--write ou\n--test-write)?", "Nao",
             "Resultado SEM-SUDO; escrita nao tentada", COR_ALERTA, max_chars=18)
d.rotulo(CX + 22, y2 + 18, "Sim", font_size=11, ancora="start")
y = y2 + 30
d.seta(CX, y2, CX, y)

y2 = decisao(d, y, "tag_antes ja e igual\na tag_esperada,\ne e --write real?", "Sim",
             "Nenhum mecanismo executado. Resultado OK-ja-correto "
             "(sem escrita, sem reboot)", COR_OK, max_chars=20)
d.rotulo(CX + 22, y2 + 18, "Nao", font_size=11, ancora="start")
y = y2 + 30
d.secao(CX - BW/2 - 15, sec2_y, BW + 30, (y - sec2_y), "")
d.seta(CX, y2, CX, y)

d.caixa(CX - BW/2, y, BW, 56, "CASCATA DE ESCRITA: Mecanismo 1 -> Mecanismo 2 -> "
        "Mecanismo 3 (opcional). Ver diagrama dedicado.",
        cor=COR_ACAO, negrito=True, max_chars=44)
y += 56 + 18
d.seta(CX, y-18, CX, y)

d.caixa(CX - BW/2, y, BW, 50, "Se resultado comeca com OK: sincroniza BBconfig.conf "
        "(backup antes de editar)", max_chars=48)
y += 50 + 24
d.seta(CX, y-24, CX, y)

y2 = decisao(d, y, "--production ativo\nE resultado OK?", "Sim",
             "Executa reinstall-enable e reboot final do host", COR_ACAO,
             max_chars=18)
d.rotulo(CX + 22, y2 + 18, "Nao", font_size=11, ancora="start")
y = y2 + 30
d.seta(CX, y2, CX, y)

d.caixa(CX - BW/2, y, BW, 40, "Registro do host concluido (dict p/ tabela de resumo)",
        max_chars=52)
y += 40 + 24
d.seta(CX, y-24, CX, y)

d.caixa(CX - BW/2, y, BW, 50, "Apos todos os hosts: monta tabela detalhada + "
        "sumario agregado por resultado", max_chars=48)
y += 50 + 18
d.seta(CX, y-18, CX, y)

d.caixa(CX - BW/2, y, BW, 64, "v2.3.6: grava <log>_inacessiveis_rede.txt e "
        "<log>_inacessiveis_acesso.txt (triagem e Fase 2, formato do --hosts)",
        cor=COR_ACAO, max_chars=52)
y += 64 + 18
d.seta(CX, y-18, CX, y)

d.caixa(CX - BW/2, y, BW, 46, "Fim: grava logs (remoto/local/CSV/EFI) e "
        "retorna codigo de saida", cor=COR_INICIO_FIM, negrito=True, max_chars=46)
y += 46

ALTURA_FINAL = int(y + 30)
d.altura = ALTURA_FINAL
svg = d.render()
with open(os.path.join(SAIDA, "01_fluxo_macro_operacao.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("altura final:", ALTURA_FINAL)
