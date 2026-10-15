"""Gerador do diagrama 05_arquitetura_mapa_modulos do manual (SVG; PNG via gera_diagramas.py).

Recuperado em 15/10/2026 do historico da sessao de 17 a 20/07/2026.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.environ.get("DIAGRAMAS_SAIDA", ".")
from svg_helper import Diagrama, COR_INICIO_FIM, COR_ACAO, COR_OK, COR_ALERTA, COR_DECISAO, _ponta

W = 1220
H = 940
d = Diagrama(W, H, "Arquitetura: Mapa de Modulos do Pacote update_dmi_tag")

CINZA = "#eef0f2"


def mod(x, y, w, nome, papel, cor="#ffffff", font_size=11.5, max_chars=30):
    return d.caixa_fn(x, y, w, nome, "", papel, cor=cor, font_size=font_size,
                       max_chars=max_chars)


def liga(a, b, tracejado=False, dupla_seta=False):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    # decide se conecta vertical (topo/base) ou horizontal (lados),
    # com base na posicao relativa dos centros
    acx, acy = ax + aw/2, ay + ah/2
    bcx, bcy = bx + bw/2, by + bh/2
    if abs(acx - bcx) < 6:
        # mesma coluna: vertical
        p1 = (acx, ay + ah) if ay < by else (acx, ay)
        p2 = (bcx, by) if ay < by else (bcx, by + bh)
    elif abs(acy - bcy) < 6:
        # mesma linha: horizontal
        p1 = (ax + aw, acy) if ax < bx else (ax, acy)
        p2 = (bx, bcy) if ax < bx else (bx + bw, bcy)
    else:
        # diagonal: sai pela base/topo mais proxima, entra pelo lado mais proximo
        if ay < by:
            p1 = (acx, ay + ah)
        else:
            p1 = (acx, ay)
        if bcx > acx:
            p2 = (bx, bcy)
        else:
            p2 = (bx + bw, bcy)
    if tracejado:
        d.partes.append(
            '<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#999999" '
            'stroke-width="1.3" stroke-dasharray="4,3"/>'.format(
                p1[0], p1[1], p2[0], p2[1]))
        d.partes.append(_ponta(p1[0], p1[1], p2[0], p2[1]))
    else:
        d.seta(p1[0], p1[1], p2[0], p2[1])


# --- Linha 1: entrada ---
b_shim = mod(40, 55, 260, "update_dmi_tag.py", "Shim executavel: chama "
             "update_dmi_tag/__main__.py", cor=COR_INICIO_FIM, max_chars=28)
b_main = mod(340, 55, 300, "__main__.py", "CLI: parse_args, orquestra o "
             "fluxo completo, codigo de saida", cor=COR_INICIO_FIM, max_chars=30)
b_tool = mod(860, 55, 320, "tools/efi_write.py", "Ferramenta STANDALONE: "
             "testa so o Mecanismo 3, fora do fluxo principal",
             cor=COR_DECISAO, max_chars=34)

# --- Linha 2: orquestracao por host ---
b_hp = mod(120, 175, 420, "host_processor.py", "Orquestra triagem e "
           "processamento de cada host, perfil a perfil", cor=COR_ACAO, max_chars=40)
b_hosts = mod(900, 175, 280, "hosts.py", "Le hosts.txt; grava as listas de "
              "inacessiveis por motivo (v2.3.6)", max_chars=30)
b_acesso = mod(580, 175, 280, "acesso.py", "Perfis do --acesso: usuario, senha "
               "e senhas de sudo, em ordem (v2.3.0)", max_chars=30)

# --- Linha 3: infra SSH e ambiente ---
b_sshboot = mod(40, 295, 260, "ssh_bootstrap.py", "Chave pelo sshd do alvo "
                "(ed25519 ou RSA) via ssh-copy-id; senha efetiva", max_chars=28)
b_sshutil = mod(320, 295, 260, "ssh_utils.py", "ssh_run, porta/conexao "
                "(--ssh-timeout), sudo, compatibilidade ssh-rsa", max_chars=28)
b_env = mod(600, 295, 260, "environment.py", "Coleta hardware, kernel, BIOS, "
            "SMBIOS, WSMT, tag atual", max_chars=28)
b_bbconf = mod(880, 295, 300, "bbconfig.py", "Le e sincroniza BEM_NUMERO em "
               "/etc/BBconfig.conf remoto", max_chars=32)

# --- Linha 4: validacao e cascata ---
b_pat = mod(40, 425, 300, "patrimonio.py", "Valida formato e calcula o DV "
            "(Modulo 11) da tag patrimonial", cor=COR_OK, max_chars=32)
b_cascade = mod(400, 425, 420, "write_cascade.py", "Cascata: tenta "
                "Mecanismo 1, depois 2, depois 3 (opcional)", cor=COR_ACAO,
                max_chars=42)
b_summary = mod(880, 425, 300, "summary.py", "Monta a tabela detalhada e o "
                "sumario agregado final", cor=COR_INICIO_FIM, max_chars=32)

# --- Linha 5: os 3 mecanismos ---
b_m1 = mod(80, 570, 300, "bios_amidelnx.py", "Mecanismo 1: binario "
           "amidelnx_64 (proprietario AMI, NDA)", cor=COR_DECISAO, max_chars=32)
b_m2 = mod(430, 570, 300, "bios_sysfs.py", "Mecanismo 2: modulo de kernel "
           "amibios_dmi via sysfs", cor=COR_DECISAO, max_chars=32)
b_m3 = mod(780, 570, 320, "boot_efi.py", "Mecanismo 3: boot EFI temporario "
           "com AMIDEEFIx64.EFI (experimental)", cor=COR_ALERTA, max_chars=34)

# --- Linha 6: utilitarios transversais ---
d.secao(20, 720, W - 40, 130, "UTILITARIOS TRANSVERSAIS "
        "(usados por praticamente todos os modulos acima)")
b_const = mod(60, 760, 500, "constants.py", "SCRIPT_VERSION, excecoes "
              "(MecanismoIndisponivelError, etc.), deteccao de "
              "incompatibilidade de firmware", max_chars=54)
b_log = mod(640, 760, 500, "logging_utils.py", "Formatacao e escrita "
            "centralizada de logs (remoto, local, CSV, EFI)", max_chars=54)

y_legenda = 890
d.rotulo(60, y_legenda, "-> seta solida: chamada/importacao direta   "
         "- - -> tracejada: uso pontual (ferramenta standalone ou "
         "utilitario transversal)", font_size=11.5, ancora="start", cor="#555555")

# ================= LIGACOES =================
liga(b_shim, b_main)
liga(b_main, b_hp)
liga(b_main, b_hosts, tracejado=True)
liga(b_main, b_summary, tracejado=True)
liga(b_main, b_acesso)
# seta horizontal direta: as caixas tem alturas diferentes e o liga()
# trataria como diagonal, cruzando a propria caixa de origem
_ym = b_hp[1] + min(b_hp[3], b_acesso[3]) / 2
d.seta(b_hp[0] + b_hp[2], _ym, b_acesso[0], _ym)

liga(b_hp, b_sshboot)
liga(b_hp, b_sshutil)
liga(b_hp, b_env)
liga(b_hp, b_bbconf)
liga(b_hp, b_pat)
liga(b_hp, b_cascade)

liga(b_cascade, b_m1)
liga(b_cascade, b_m2)
liga(b_cascade, b_m3, tracejado=True)

liga(b_tool, b_m3, tracejado=True)
liga(b_tool, b_pat, tracejado=True)
liga(b_tool, b_hosts, tracejado=True)

d.altura = H
svg = d.render()
with open(os.path.join(SAIDA, "05_arquitetura_mapa_modulos.svg"), "w", encoding="utf-8") as f:
    f.write(svg)
print("ok")
