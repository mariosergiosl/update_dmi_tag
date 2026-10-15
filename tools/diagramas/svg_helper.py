"""Helper minimo para montar flowcharts em SVG (sem dependencias externas)."""

FONT = "Helvetica, Arial, sans-serif"

COR_BORDA      = "#2b2b2b"
COR_TEXTO      = "#1a1a1a"
COR_CAIXA      = "#ffffff"
COR_INICIO_FIM = "#30BA78"   # verde SUSE
COR_DECISAO    = "#FFF3CD"   # amarelo suave
COR_ACAO       = "#E8F4EF"   # verde bem claro
COR_ALERTA     = "#F8D7DA"   # vermelho suave (bloqueio/falha)
COR_OK         = "#D4EDDA"   # verde suave (sucesso)
COR_SETA       = "#2b2b2b"


def _esc(texto):
    """Escapa caracteres XML especiais. Texto sem isso quebra o parser SVG
    usado na conversao para PNG (svglib), que aborta silenciosamente o
    resto do documento ao encontrar '<'/'>'/'&' nao escapados dentro de
    conteudo de texto."""
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _wrap(texto, max_chars):
    """Quebra texto em linhas por max_chars, respeitando '\\n' explicito
    como quebra forcada (paragrafo), nao apenas glue de palavra. Bug real
    corrigido 2026-07-20: antes, o \\n literal era ignorado pelo split(' '),
    entao textos com \\n explicito coloncavam sem quebra visivel."""
    texto = _esc(texto)
    linhas = []
    for paragrafo in texto.split("\n"):
        palavras = paragrafo.split(" ")
        atual = ""
        for p in palavras:
            teste = (atual + " " + p).strip()
            if len(teste) > max_chars and atual:
                linhas.append(atual)
                atual = p
            else:
                atual = teste
        linhas.append(atual)
    return linhas


def _ponta(xa, ya, xb, yb, tam=9.0, meia=4.0):
    """Return a filled triangle polygon for an arrow tip at (xb, yb).

    The tip points from (xa, ya) to (xb, yb). Drawn as a polygon because
    svglib, used for the PNG conversion, ignores SVG markers.
    """
    import math
    dx, dy = xb - xa, yb - ya
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    bx, by = xb - ux * tam, yb - uy * tam
    pts = [(xb, yb), (bx - uy * meia, by + ux * meia), (bx + uy * meia, by - ux * meia)]
    return '<polygon points="{}" fill="{}" stroke="none"/>'.format(
        " ".join("{:.1f},{:.1f}".format(px, py) for px, py in pts), COR_SETA)


class Diagrama:
    def __init__(self, largura, altura, titulo=None):
        self.largura = largura
        self.altura = altura
        self.titulo = titulo
        self.partes = []
        if titulo:
            self.partes.append(
                '<text x="{}" y="34" font-family="{}" font-size="20" '
                'font-weight="bold" fill="{}" text-anchor="middle">{}</text>'.format(
                    largura / 2, FONT, COR_TEXTO, titulo))

    def caixa(self, x, y, w, h, texto, cor=COR_CAIXA, rx=8, max_chars=28,
              font_size=13, negrito=False, borda=COR_BORDA, borda_largura=1.6):
        linhas = _wrap(texto, max_chars)
        n = len(linhas)
        h_necessaria = n * (font_size + 3) + 22
        h = max(h, h_necessaria)
        self.partes.append(
            '<rect x="{}" y="{}" width="{}" height="{}" rx="{}" fill="{}" '
            'stroke="{}" stroke-width="{}"/>'.format(
                x, y, w, h, rx, cor, borda, borda_largura))
        peso = ' font-weight="bold"' if negrito else ""
        cy = y + h / 2 - (n - 1) * (font_size + 3) / 2 + font_size / 3
        for i, linha in enumerate(linhas):
            self.partes.append(
                '<text x="{}" y="{}" font-family="{}" font-size="{}"{} '
                'fill="{}" text-anchor="middle">{}</text>'.format(
                    x + w / 2, cy + i * (font_size + 3), FONT, font_size,
                    peso, COR_TEXTO, linha))
        return (x, y, w, h)

    def caixa_fn(self, x, y, w, funcao, modulo, desc, cor=COR_CAIXA, rx=8,
                 max_chars=46, font_size=12, borda=COR_BORDA):
        """Caixa de duas camadas: cabecalho com nome da funcao + modulo (uma
        unica linha, sem tspan, o parser SVG usado na conversao para PNG nao
        lida bem com conteudo misto texto+elemento) e descricao abaixo.
        Altura calculada automaticamente a partir do texto (evita overflow).
        """
        desc_linhas = _wrap(desc, max_chars)
        n = len(desc_linhas)
        h = 34 + n * (font_size + 4) + 8
        self.partes.append(
            '<rect x="{}" y="{}" width="{}" height="{}" rx="{}" fill="{}" '
            'stroke="{}" stroke-width="1.6"/>'.format(x, y, w, h, rx, cor, borda))
        cabec_y = y + 20
        cabecalho = _esc("{}  ({})".format(funcao, modulo) if modulo else funcao)
        self.partes.append(
            '<text x="{}" y="{}" font-family="Consolas, Courier, monospace" '
            'font-size="12.5" font-weight="bold" fill="#154c79" '
            'text-anchor="middle">{}</text>'.format(x + w/2, cabec_y, cabecalho))
        self.partes.append(
            '<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#dddddd" '
            'stroke-width="1"/>'.format(x + 14, y + 28, x + w - 14, y + 28))
        area_y0 = y + 28
        area_h = h - 28
        cy = area_y0 + area_h / 2 - (n - 1) * (font_size + 4) / 2 + font_size / 3
        for i, linha in enumerate(desc_linhas):
            self.partes.append(
                '<text x="{}" y="{}" font-family="{}" font-size="{}" '
                'fill="{}" text-anchor="middle">{}</text>'.format(
                    x + w / 2, cy + i * (font_size + 4), FONT, font_size,
                    COR_TEXTO, linha))
        return (x, y, w, h)

    def losango(self, x, y, w, h, texto, cor=COR_DECISAO, max_chars=20,
                font_size=12):
        cx, cy = x + w / 2, y + h / 2
        pontos = "{},{} {},{} {},{} {},{}".format(
            cx, y, x + w, cy, cx, y + h, x, cy)
        self.partes.append(
            '<polygon points="{}" fill="{}" stroke="{}" stroke-width="1.6"/>'.format(
                pontos, cor, COR_BORDA))
        linhas = _wrap(texto, max_chars)
        n = len(linhas)
        ty = cy - (n - 1) * (font_size + 2) / 2 + font_size / 3
        for i, linha in enumerate(linhas):
            self.partes.append(
                '<text x="{}" y="{}" font-family="{}" font-size="{}" '
                'fill="{}" text-anchor="middle">{}</text>'.format(
                    cx, ty + i * (font_size + 2), FONT, font_size, COR_TEXTO, linha))
        return (x, y, w, h)

    def circulo(self, cx, cy, r, texto, cor=COR_CAIXA, font_size=11,
                max_chars=12, borda=COR_BORDA):
        self.partes.append(
            '<circle cx="{}" cy="{}" r="{}" fill="{}" stroke="{}" '
            'stroke-width="1.6"/>'.format(cx, cy, r, cor, borda))
        linhas = _wrap(texto, max_chars)
        n = len(linhas)
        ty = cy - (n - 1) * (font_size + 2) / 2 + font_size / 3
        for i, linha in enumerate(linhas):
            self.partes.append(
                '<text x="{}" y="{}" font-family="{}" font-size="{}" '
                'fill="{}" text-anchor="middle">{}</text>'.format(
                    cx, ty + i * (font_size + 2), FONT, font_size, COR_TEXTO, linha))

    def seta(self, x1, y1, x2, y2, curva=False, tracejada=False):
        estilo = ' stroke-dasharray="4,3"' if tracejada else ""
        if curva:
            mx = (x1 + x2) / 2
            self.partes.append(
                '<path d="M {} {} Q {} {}, {} {}" fill="none" stroke="{}" '
                'stroke-width="1.6"{}/>'.format(
                    x1, y1, mx, y1, x2, y2, COR_SETA, estilo))
            self.partes.append(_ponta(mx, y1, x2, y2))
        else:
            self.partes.append(
                '<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="{}" '
                'stroke-width="1.6"{}/>'.format(
                    x1, y1, x2, y2, COR_SETA, estilo))
            self.partes.append(_ponta(x1, y1, x2, y2))

    def linha_cotovelo(self, pontos, tracejada=False):
        estilo = ' stroke-dasharray="4,3"' if tracejada else ""
        d = "M " + " L ".join("{} {}".format(px, py) for px, py in pontos)
        self.partes.append(
            '<path d="{}" fill="none" stroke="{}" stroke-width="1.6"{}/>'.format(
                d, COR_SETA, estilo))
        (xa, ya), (xb, yb) = pontos[-2], pontos[-1]
        self.partes.append(_ponta(xa, ya, xb, yb))

    def linha_simples(self, x1, y1, x2, y2, cor=None, largura=1.3,
                       tracejada=False):
        estilo = ' stroke-dasharray="4,3"' if tracejada else ""
        self.partes.append(
            '<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="{}" '
            'stroke-width="{}"{}/>'.format(
                x1, y1, x2, y2, cor or COR_SETA, largura, estilo))

    def rotulo(self, x, y, texto, font_size=11, ancora="middle", cor=None,
               negrito=False):
        texto = _esc(texto)
        peso = ' font-weight="bold"' if negrito else ""
        self.partes.append(
            '<text x="{}" y="{}" font-family="{}" font-size="{}"{} '
            'fill="{}" text-anchor="{}">{}</text>'.format(
                x, y, FONT, font_size, peso, cor or COR_TEXTO, ancora, texto))

    def secao(self, x, y, w, h, texto, cor="none"):
        # fill="none": esta caixa e desenhada por ultimo (para ficar por cima
        # das setas sem cobrir o conteudo), entao nunca pode ter preenchimento
        # opaco, ou esconderia tudo que ja foi desenhado dentro dela.
        self.partes.append(
            '<rect x="{}" y="{}" width="{}" height="{}" rx="10" fill="{}" '
            'stroke="#bbbbbb" stroke-width="1.4" stroke-dasharray="5,4"/>'.format(
                x, y, w, h, cor))
        if texto:
            self.partes.append(
                '<rect x="{}" y="{}" width="{}" height="20" fill="#ffffff"/>'.format(
                    x + 8, y - 10, 8 + len(texto) * 6.6))
            self.rotulo(x + 12, y + 4, texto, font_size=12, ancora="start",
                        negrito=True, cor="#555555")

    def render(self):
        defs = (
            '<defs><marker id="seta" markerWidth="10" markerHeight="10" '
            'refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L0,6 L9,3 z" fill="{}"/></marker></defs>'
        ).format(COR_SETA)
        corpo = "\n".join(self.partes)
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" '
            'viewBox="0 0 {} {}">'
            '<rect x="0" y="0" width="{}" height="{}" fill="#ffffff"/>'
            "{}{}</svg>"
        ).format(self.largura, self.altura, self.largura, self.altura,
                  self.largura, self.altura, defs, corpo)

    def salvar(self, caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(self.render())
