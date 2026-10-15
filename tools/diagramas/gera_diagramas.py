"""Gera os PNGs dos diagramas do manual a partir dos geradores dNN_*.py.

USAGE: python tools/diagramas/gera_diagramas.py [-o PASTA] [-f] NN [NN ...]
       ex.: python tools/diagramas/gera_diagramas.py -o assets/diagramas -f 01 07

Cada gerador grava um SVG (svg_helper.py); o SVG vira PDF pelo svglib e
reportlab, e o PDF vira PNG pelo PyMuPDF. So os diagramas pedidos sao
gerados. Sem -f, PNG existente no destino nao e sobrescrito. Sem -o, a
saida vai para uma pasta temporaria, para conferencia.

Dependencias: svglib, reportlab e pymupdf (pip).
"""
import argparse
import glob
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
DPI = 160


def gera(numero, destino, forca):
    """Run one generator and convert its SVG to PNG.

    PARAMETER 1: diagram number as text, e.g. "01"
    PARAMETER 2: output folder for the PNG
    PARAMETER 3: overwrite an existing PNG when True
    RETURNS: path of the PNG written
    """
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF
    import fitz

    scripts = glob.glob(os.path.join(AQUI, "d%s_*.py" % numero))
    if len(scripts) != 1:
        raise SystemExit("gerador d%s_*.py nao encontrado (ou ambiguo)" % numero)
    nome = os.path.basename(scripts[0])[1:-3]
    png = os.path.join(destino, nome + ".png")
    if os.path.exists(png) and not forca:
        raise SystemExit("ja existe (use -f): %s" % png)
    tmp = tempfile.mkdtemp(prefix="diagramas_")
    env = dict(os.environ, DIAGRAMAS_SAIDA=tmp)
    subprocess.run([sys.executable, scripts[0]], env=env, check=True)
    svg = os.path.join(tmp, nome + ".svg")
    pdf = os.path.join(tmp, nome + ".pdf")
    renderPDF.drawToFile(svg2rlg(svg), pdf)
    doc = fitz.open(pdf)
    doc[0].get_pixmap(dpi=DPI).save(png)
    doc.close()
    return png


def main(argv=None):
    """Command line entry point.

    PARAMETER 1: argument list (default sys.argv[1:])
    RETURNS: exit code
    """
    p = argparse.ArgumentParser(description="Gera os PNGs dos diagramas do manual.")
    p.add_argument("numeros", nargs="+", help="numeros dos diagramas, ex.: 01 07")
    p.add_argument("-o", "--saida", default=None, help="pasta dos PNGs (padrao: temporaria)")
    p.add_argument("-f", "--forca", action="store_true", help="sobrescreve PNG existente")
    a = p.parse_args(argv)
    destino = a.saida or tempfile.mkdtemp(prefix="diagramas_png_")
    os.makedirs(destino, exist_ok=True)
    for n in a.numeros:
        print("gravado:", gera(n, destino, a.forca))
    return 0


if __name__ == "__main__":
    sys.exit(main())
