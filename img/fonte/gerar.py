# -*- coding: utf-8 -*-
u"""Gera as imagens do README do perfil a partir dos HTML desta pasta.

    python gerar.py              gera as três
    python gerar.py banner       gera só uma (banner, ecossistema, valores)

Cada imagem é um HTML com CSS (`<nome>.html` + `nocturne.css`), aberto no
Chromium do Playwright e fotografado no tamanho exato, com fator de escala 1.
O PNG vai para a pasta de cima (`img/<nome>.png`), que é onde o README o
procura.

É o mesmo gerador da Local Suite (docs/img/fonte/gerar.py), com duas
diferenças: acha o Chromium também fora do Windows, e confere se um texto
invade o bloco vizinho DENTRO da mesma coluna — o nome do projeto que desce
por cima da fronteira da camada é exatamente o defeito que a checagem de
blocos inteiros não vê.

═══ POR QUE HTML, E NÃO UM SCRIPT DE DESENHO ═══

O texto quebra linha sozinho e a medida é a do navegador. Um diagrama em que
um título invade a coluna vizinha não é defeito de estética — é um passo
ilegível (lição do fluxo do PhotoID RT, onde «Simulation data» escrevia por
cima de «Sheet»).

═══ O QUE ELE RECUSA, EM VEZ DE FOTOGRAFAR ═══

  * FONTE QUE NÃO CARREGOU. Sem a Outfit, o Chromium desenha com a fonte do
    sistema e a peça sai «quase certa» — que é a forma que engana. As três
    faces precisam estar `loaded`.
  * TEXTO QUE SAI DO LUGAR: bloco fora da peça, bloco que se sobrepõe a outro
    bloco (`data-bloco`), texto mais largo ou mais alto que a própria coluna
    (`.col`), e dois textos da mesma coluna que se sobrepõem.

Recusar aqui custa uma linha no terminal; fotografar assim mesmo custa uma
imagem publicada com o texto cortado.

SEM CAMINHO ABSOLUTO: tudo se resolve pela pasta deste arquivo. O Chromium é o
que o Playwright instalado já sabe abrir; se o build que ele pede não estiver
baixado, serve o Chromium que já estiver na pasta de navegadores do Playwright
(`PLAYWRIGHT_BROWSERS_PATH`, ou `%LOCALAPPDATA%\\ms-playwright` no Windows).

    pip install playwright        (uma vez, e `python -m playwright install
                                   chromium` se não houver Chromium nenhum)
    python img/fonte/gerar.py
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import struct

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.dirname(AQUI)                       # img/

# (nome, largura, altura). A largura é sempre 1280, que é o que o GitHub usa
# no social preview e o que cabe na coluna do README sem reamostrar demais.
PECAS = (
    ("banner", 1280, 640),
    ("ecossistema", 1280, 640),
    ("valores", 1280, 440),
)

# As três faces que toda peça usa. O nome é o `font-family` do nocturne.css.
FACES = (("Outfit", "400"), ("Outfit", "700"), ("JetBrains Mono", "400"))


def _chromiums():
    u"""Os executáveis de Chromium já baixados pelo Playwright nesta máquina,
    do build mais novo para o mais velho."""
    bases = []
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        bases.append(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    if os.environ.get("LOCALAPPDATA"):
        bases.append(os.path.join(os.environ["LOCALAPPDATA"], "ms-playwright"))
    bases.append(os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright"))
    bases.append(os.path.join(os.path.expanduser("~"), "Library", "Caches",
                              "ms-playwright"))
    achados = []
    for base in bases:
        if not os.path.isdir(base):
            continue
        for nome in sorted(os.listdir(base), reverse=True):
            if not nome.startswith("chromium-"):
                continue
            for rel in (("chrome-win64", "chrome.exe"), ("chrome-win", "chrome.exe"),
                        ("chrome-linux", "chrome"),
                        ("chrome-mac", "Chromium.app", "Contents", "MacOS",
                         "Chromium")):
                exe = os.path.join(base, nome, *rel)
                if os.path.isfile(exe):
                    achados.append(exe)
    return achados


def _abrir(p):
    u"""O navegador: primeiro o que o Playwright pede, depois qualquer
    Chromium dele que já esteja no disco."""
    try:
        return p.chromium.launch()
    except Exception as erro:                       # build pedido não baixado
        primeiro = erro
    for exe in _chromiums():
        try:
            return p.chromium.launch(executable_path=exe)
        except Exception:
            continue
    raise primeiro


# Carrega as três faces e diz o estado de cada uma. `document.fonts.ready` só
# espera as faces que a página já pediu; `load()` pede todas, e o estado que
# volta é o que vale.
_JS_FONTES = u"""
async () => {
  const faces = [...document.fonts];
  await Promise.all(faces.map(f => f.load().catch(() => null)));
  await document.fonts.ready;
  return faces.map(f => [f.family.replace(/["']/g, ''), String(f.weight), f.status]);
}
"""

# O que sai do lugar. Devolve uma lista de frases; vazia é «cabe».
_JS_LUGAR = u"""
() => {
  const W = window.innerWidth, H = window.innerHeight, prob = [];
  const nome = el => (el.dataset.bloco || el.className || el.tagName) +
                     ' «' + (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 40) + '»';
  const cruza = (a, b) => a.left < b.right && b.left < a.right &&
                          a.top < b.bottom && b.top < a.bottom;
  const blocos = [...document.querySelectorAll('[data-bloco]')];
  for (const el of blocos) {
    const r = el.getBoundingClientRect();
    if (r.left < -0.5 || r.top < -0.5 || r.right > W + 0.5 || r.bottom > H + 0.5)
      prob.push('fora da peça: ' + nome(el) + ' ' +
                [r.left, r.top, r.right, r.bottom].map(Math.round).join(','));
  }
  for (let i = 0; i < blocos.length; i++)
    for (let j = i + 1; j < blocos.length; j++)
      if (cruza(blocos[i].getBoundingClientRect(), blocos[j].getBoundingClientRect()))
        prob.push('sobreposição: ' + nome(blocos[i]) + ' × ' + nome(blocos[j]));
  for (const el of document.querySelectorAll('.col, .col *')) {
    if (getComputedStyle(el).display === 'inline') continue;
    if (el.scrollWidth > el.clientWidth + 1)
      prob.push('mais largo que a coluna: ' + nome(el) +
                ' (' + el.scrollWidth + ' > ' + el.clientWidth + ')');
  }
  for (const col of document.querySelectorAll('.col')) {
    if (col.scrollHeight > col.clientHeight + 1)
      prob.push('mais alto que a coluna: ' + nome(col) +
                ' (' + col.scrollHeight + ' > ' + col.clientHeight + ')');
    const filhos = [...col.children].filter(f => !f.classList.contains('traco'));
    for (let i = 0; i < filhos.length; i++)
      for (let j = i + 1; j < filhos.length; j++)
        if (cruza(filhos[i].getBoundingClientRect(), filhos[j].getBoundingClientRect()))
          prob.push('dentro da coluna ' + (col.dataset.bloco || '?') + ': ' +
                    nome(filhos[i]) + ' × ' + nome(filhos[j]));
  }
  return prob;
}
"""


def _tamanho_png(caminho):
    u"""(largura, altura) lidas do cabeçalho IHDR do PNG, sem Pillow."""
    with open(caminho, "rb") as f:
        cab = f.read(24)
    if cab[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(u"não é PNG: %s" % caminho)
    return struct.unpack(">II", cab[16:24])


def _url_de_arquivo(caminho):
    caminho = os.path.abspath(caminho).replace("\\", "/")
    return "file://" + ("" if caminho.startswith("/") else "/") + caminho


def gerar(nomes=None):
    u"""Gera as peças pedidas (todas, sem nome). Devolve o código de saída."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(u"FALHOU: este Python não tem o Playwright.")
        print(u"  Instale com:  python -m pip install playwright")
        return 2

    pedidas = [p for p in PECAS if not nomes or p[0] in nomes]
    desconhecidas = sorted(set(nomes or ()) - set(p[0] for p in PECAS))
    if desconhecidas:
        print(u"FALHOU: peça desconhecida: %s (há: %s)"
              % (", ".join(desconhecidas), ", ".join(p[0] for p in PECAS)))
        return 2

    falhas = 0
    with sync_playwright() as p:
        try:
            nav = _abrir(p)
        except Exception as erro:
            print(u"FALHOU: não consegui abrir um Chromium do Playwright.")
            print(u"  %s" % str(erro).splitlines()[0])
            print(u"  Instale com:  python -m playwright install chromium")
            return 2
        try:
            for nome, w, h in pedidas:
                html = os.path.join(AQUI, nome + ".html")
                png = os.path.join(SAIDA, nome + ".png")
                ctx = nav.new_context(viewport={"width": w, "height": h},
                                      device_scale_factor=1)
                pg = ctx.new_page()
                pg.goto(_url_de_arquivo(html))
                faces = pg.evaluate(_JS_FONTES)
                carregadas = set((f, wt) for f, wt, st in faces
                                 if st == "loaded")
                faltam = [u"%s %s" % fw for fw in FACES
                          if fw not in carregadas]
                problemas = pg.evaluate(_JS_LUGAR)
                if faltam or problemas:
                    falhas += 1
                    print(u"FALHOU: %s" % nome)
                    for f in faltam:
                        print(u"  fonte não carregou: %s" % f)
                    for pr in problemas:
                        print(u"  %s" % pr)
                    ctx.close()
                    continue
                pg.screenshot(path=png, full_page=False)
                ctx.close()
                lw, lh = _tamanho_png(png)
                if (lw, lh) != (w, h):
                    falhas += 1
                    print(u"FALHOU: %s saiu %d × %d, e não %d × %d"
                          % (nome, lw, lh, w, h))
                    continue
                print(u"ok  %-12s %d × %d  %6.1f KB  %s"
                      % (nome, lw, lh, os.path.getsize(png) / 1024.0,
                         os.path.relpath(png, os.path.dirname(SAIDA))))
        finally:
            nav.close()
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(gerar(sys.argv[1:]))
