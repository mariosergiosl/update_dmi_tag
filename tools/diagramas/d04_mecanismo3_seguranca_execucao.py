"""Gerador do diagrama 04_mecanismo3_seguranca_execucao do manual (SVG; PNG via gera_diagramas.py).

Recuperado em 15/10/2026 do historico da sessao de 17 a 20/07/2026.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.environ.get("DIAGRAMAS_SAIDA", ".")
from svg_helper import Diagrama, COR_INICIO_FIM, COR_ACAO, COR_OK, COR_ALERTA

W = 1080
d = Diagrama(W, 100, "Mecanismo 3: Checagem de Seguranca e Execucao do Boot EFI (boot_efi.py)")
CX = W / 2
BW = 620
GAP = 22


def fn_box(y, funcao, modulo, desc, cor="#ffffff", max_chars=58):
    _, _, _, h = d.caixa_fn(CX - BW/2, y, BW, funcao, modulo, desc,
                             cor=cor, max_chars=max_chars)
    return y + h + GAP


def box(y, texto, h=38, cor="#ffffff", max_chars=60, negrito=False):
    _, _, _, h_real = d.caixa(CX - BW/2, y, BW, h, texto, cor=cor,
                               max_chars=max_chars, negrito=negrito)
    return y + h_real + GAP


def seta_ate(y_novo):
    d.seta(CX, y_novo - GAP, CX, y_novo)


def gate(y, texto, motivo_bloqueio, max_chars=30, dh=54, lw=420, box_w=250,
         rotulo_ok="OK", seta_entrada=True):
    if seta_entrada:
        d.seta(CX, y - 6, CX, y)
    lx = CX - lw / 2
    d.losango(lx, y, lw, dh, texto, max_chars=max_chars, font_size=11.5)
    tip_x, tip_y = lx + lw, y + dh / 2
    box_x = tip_x + 40
    d.caixa(box_x, tip_y - 24, box_w, 48, motivo_bloqueio, cor=COR_ALERTA,
            max_chars=box_w // 8, font_size=10)
    d.linha_cotovelo([(tip_x, tip_y), (box_x, tip_y)])
    d.rotulo(tip_x + 8, tip_y - 6, "Falhou", font_size=10.5, ancora="start")
    y_out = y + dh
    d.rotulo(CX + 16, y_out + 13, rotulo_ok, font_size=10.5, ancora="start")
    return y_out


y = 55
y = fn_box(y, "executa_boot_efi_remoto(ip, tag, args, ...)", "boot_efi.py",
           "Chamado por write_cascade.py quando Mec. 1 e 2 falharam E "
           "--allow-efi-fallback esta ativo.", cor=COR_INICIO_FIM)
seta_ate(y)

y = box(y, "_limpa_sobra_anterior(): remove label/diretorio de uma execucao "
        "anterior que nao limpou (idempotencia)", h=44)
seta_ate(y)

d.secao(CX - BW/2 - 130, y - 10, BW + 260, 620,
        "verifica_seguranca_efi_remoto()  -- bateria READ-ONLY, nada e "
        "escrito no host antes de tudo aprovar")
y += 16

y = gate(y, "1. UEFI confirmado?\n(/sys/firmware/efi/efivars)",
         "BLOQUEADO: host em Legacy\nBIOS, Mecanismo 3 nao se aplica",
         max_chars=26, dh=50, seta_entrada=False)
y += 6
y = gate(y, "2. efibootmgr disponivel?\n(instala via zypper se ausente)",
         "BLOQUEADO: binario ausente\nmesmo apos tentativa de instalar",
         max_chars=26, dh=50)
y += 6
y = gate(y, "3. Secure Boot desabilitado?\n(mokutil --sb-state, via sudo)",
         "Se habilitado: BLOQUEADO, exceto\ncom --force-efi-secureboot (perigoso,\n"
         "so teste supervisionado)", max_chars=28, dh=58)
y += 6
y = gate(y, "4. TPM presente com LUKS selado\nnele (crypttab/clevis tpm2)?",
         "BLOQUEADO: alterar o boot pode\nimpedir o desbloqueio do disco",
         max_chars=30, dh=54)
y += 6
y = gate(y, "5. ESP montada e gravavel?\n(mountpoint + sudo test -w)",
         "BLOQUEADO: particao EFI nao\nmontada ou nao gravavel",
         max_chars=26, dh=50)
y += 6
y = gate(y, "6. Espaco livre na ESP >= minimo\nexigido? (default 10240 KB)",
         "BLOQUEADO: espaco insuficiente\nna particao EFI",
         max_chars=28, dh=54)
y += 6
y = gate(y, "7. Sem entrada de boot com o\nmesmo label ja na NVRAM?",
         "BLOQUEADO: possivel sobra de\nexecucao anterior, checar manual",
         max_chars=28, dh=54)
y += 10

y = box(y, "APROVADA: host elegivel para o Mecanismo 3", h=36, cor=COR_OK,
        negrito=True)
seta_ate(y)

d.secao(CX - BW/2 - 15, y - 10, BW + 30, 560, "EXECUCAO (so apos aprovacao)")
y += 16

y = box(y, "Copia AMIDEEFIx64.EFI + bootx64.efi + startup.nsh gerado "
        "(com checkpoints MEC3-DEBUG) para a ESP", h=48)
seta_ate(y)

y = box(y, "Descobre disco/particao da ESP; captura a BootOrder original "
        "ANTES de criar a entrada temporaria", h=48)
seta_ate(y)

y = box(y, "Cria entrada de boot temporaria (efibootmgr --create)", h=36)
seta_ate(y)

y = box(y, "CORRECAO CRITICA (pos-incidente): restaura a BootOrder original "
        "imediatamente. So o BootNext (uso unico) aponta para a entrada "
        "temporaria; qualquer reboot seguinte cai direto no SO, mesmo se a "
        "limpeza nunca rodar. Elimina o risco de loop de reboot infinito.",
        h=70, cor=COR_ALERTA)
seta_ate(y)

y = box(y, "Define BootNext e reinicia o host (reboot)", h=36, cor=COR_ACAO)
seta_ate(y)

y = box(y, "Aguarda o host voltar via SSH (timeout configuravel via "
        "--efi-timeout, default 300s no codigo; heartbeat a cada 30s)",
        h=48)
seta_ate(y)

y2 = gate(y, "Host respondeu via SSH\ndentro do timeout?",
          "return 'TRAVADO-POS-REBOOT'\n(requer intervencao fisica)",
          max_chars=26, dh=56, lw=420, box_w=260, rotulo_ok="Sim",
          seta_entrada=False)
y = y2 + 10

y = box(y, "Le amide_debug.log (saida do AMIDEEFIx64.EFI); confirma "
        "chassis-asset-tag via dmidecode; limpa entrada de boot e "
        "arquivos da ESP", h=54)
seta_ate(y)

y2 = gate(y, "Tag lida == tag esperada?",
          "Verifica assinatura de incompat.\nde firmware no debug log",
          max_chars=22, dh=50, box_w=270, rotulo_ok="Sim: return 'OK-efiboot'",
          seta_entrada=False)
y = y2 + 30

lw = 380
lx = CX - lw/2
d.losango(lx, y, lw, 66, "Assinatura de incompatibilidade\nde firmware detectada no log?",
          max_chars=30, font_size=11.5)
tip_x, tip_y = lx + lw, y + 33
box_x = tip_x + 40
d.caixa(box_x, tip_y - 24, 260, 48, "return 'INCOMPATIVEL-efiboot'",
        cor=COR_ALERTA, max_chars=30, font_size=11)
d.linha_cotovelo([(tip_x, tip_y), (box_x, tip_y)])
d.rotulo(tip_x + 8, tip_y - 6, "Sim", font_size=10.5, ancora="start")
y = y + 66 + GAP
d.seta(CX, y - GAP, CX, y)
d.rotulo(CX + 16, y - GAP + 15, "Nao", font_size=10.5, ancora="start")

y = box(y, "return 'FALHOU-efiboot' (host voltou, mas a tag nao confere; "
        "causa nao identificada como incompatibilidade conhecida)",
        h=48, cor=COR_ALERTA, negrito=True)

ALTURA_FINAL = int(y - GAP + 30)
d.altura = ALTURA_FINAL
svg = d.render()
with open(os.path.join(SAIDA, "04_mecanismo3_seguranca_execucao.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("altura final:", ALTURA_FINAL)
