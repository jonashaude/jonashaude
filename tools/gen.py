#!/usr/bin/env python3
"""Erzeugt die SVG-Karten des GitHub-Profils (hell + dunkel) im Stil von jonashaude.de.

Aufruf (aus dem Repo-Wurzelverzeichnis):
    python3 tools/gen.py [Zielordner] [--fonts Schriftordner]

Standard: Zielordner = assets/, Schriften = ~/ScalaX-DEV/jonashaude.de/fonts
(Hanken Grotesk und JetBrains Mono als variable woff2, Umgebungsvariable JH_FONTS geht auch).
Die Schriften werden pro Grafik auf die genutzten Zeichen reduziert und eingebettet.
Benötigt: pip install fonttools brotli
"""
import argparse, base64, io, os, html, re
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options
from fontTools.varLib.instancer import instantiateVariableFont

_ap = argparse.ArgumentParser()
_ap.add_argument("out", nargs="?", default=str(Path(__file__).resolve().parent.parent / "assets"))
_ap.add_argument("--fonts", default=os.environ.get("JH_FONTS", str(Path.home() / "ScalaX-DEV/jonashaude.de/fonts")))
_args = _ap.parse_args()
FONTS = Path(_args.fonts)
OUT = Path(_args.out)
OUT.mkdir(parents=True, exist_ok=True)

_cache = {}
def font_b64(name, chars):
    key = (name, chars)
    if key not in _cache:
        f = TTFont(FONTS / name, recalcTimestamp=False)
        o = Options(); o.flavor = "woff2"; o.layout_features = ["kern"]
        sub = Subsetter(o); sub.populate(unicodes=[ord(c) for c in chars] + [0x20]); sub.subset(f)
        b = io.BytesIO(); f.flavor = "woff2"; f.save(b)
        _cache[key] = base64.b64encode(b.getvalue()).decode()
    return _cache[key]

def chars_of(body):
    t = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return "".join(sorted(set(t)))

# --- Messen (für Zeilenumbruch) -------------------------------------------
_metrics = {}
def _font(kind, wght):
    key = (kind, wght)
    if key not in _metrics:
        f = TTFont(FONTS / ("hanken-grotesk-var.woff2" if kind == "sans" else "jetbrains-mono-var.woff2"))
        f = instantiateVariableFont(f, {"wght": wght})
        cmap = f.getBestCmap(); hmtx = f["hmtx"]
        _metrics[key] = (cmap, hmtx, f["head"].unitsPerEm)
    return _metrics[key]

def width(text, size, kind="sans", wght=400, ls=0.0):
    cmap, hmtx, upm = _font(kind, wght)
    w = 0
    for ch in text:
        g = cmap.get(ord(ch)) or cmap.get(0x20)
        w += hmtx[g][0]
    return w / upm * size + ls * size * len(text)

def wrap(text, maxw, size, kind="sans", wght=400, ls=0.0):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if width(t, size, kind, wght, ls) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

# --- Paletten -------------------------------------------------------------
LIGHT = dict(bg="#edece9", alt="#e2e0dc", surface="#fafaf8", line="#d2cfc9", ink="#1b1e20", text="#3e4245",
             muted="#5a5e62", acc="#c2185b", accs="#ad1552", code="#1b1e20", codeline="#33373a",
             codetext="#dadcd8", codemuted="#8a8f92", codeacc="#f07ba3", codestr="#c9cbc7", mark="#c2185b", onacc="#ffffff")
DARK = dict(bg="#16181a", alt="#1f2224", surface="#202326", line="#33373a", ink="#f2f1ee", text="#c3c6c3",
            muted="#8f9497", acc="#f07ba3", accs="#f07ba3", code="#0e0f10", codeline="#2b2e31",
            codetext="#dadcd8", codemuted="#8a8f92", codeacc="#f07ba3", codestr="#c9cbc7", mark="#f07ba3", onacc="#16181a")

W = 880
R = 28  # Eckenradius der Karten


def esc(s):
    return html.escape(s, quote=False)


def svg(name, h, body, title, p, extra_css=""):
    ch = chars_of(body)
    SANS_B64 = font_b64("hanken-grotesk-var.woff2", ch)
    MONO_B64 = font_b64("jetbrains-mono-var.woff2", ch)
    css = f"""
@font-face{{font-family:HG;src:url(data:font/woff2;base64,{SANS_B64}) format('woff2');font-weight:100 900}}
@font-face{{font-family:JM;src:url(data:font/woff2;base64,{MONO_B64}) format('woff2');font-weight:100 800}}
.s{{font-family:HG,'Hanken Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif}}
.m{{font-family:JM,'JetBrains Mono',ui-monospace,'SF Mono',Menlo,monospace}}
.fade{{opacity:0;animation:in .5s cubic-bezier(.2,.7,.1,1) forwards}}
@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.blink{{animation:bl 1.1s steps(1) infinite}}
@keyframes bl{{50%{{opacity:0}}}}
{extra_css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;opacity:1!important}}}}
"""
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" '
         f'aria-label="{html.escape(title)}"><title>{esc(title)}</title><style>{css}</style>'
         f'<rect width="{W}" height="{h}" rx="{R}" fill="{p["bg"]}"/>{body}</svg>')
    (OUT / name).write_text(s, encoding="utf-8")


def T(x, y, s, size, fill, cls="s", wght=400, ls=None, anchor=None, extra=""):
    a = f' text-anchor="{anchor}"' if anchor else ""
    l = f' letter-spacing="{ls}em"' if ls else ""
    return f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" font-weight="{wght}" fill="{fill}"{l}{a}{extra}>{s}</text>'


def para(x, y, text, maxw, size, fill, lh=1.5, wght=400, cls="s"):
    lines = wrap(text, maxw, size, "sans" if cls == "s" else "mono", wght)
    out = "".join(T(x, y + i * size * lh, esc(l), size, fill, cls, wght) for i, l in enumerate(lines))
    return out, y + (len(lines) - 1) * size * lh


def window_bar(x, y, w, label, p, right=None, dark=True):
    bar = p["codeline"] if dark else p["line"]
    out = f'<line x1="{x}" y1="{y+38}" x2="{x+w}" y2="{y+38}" stroke="{bar}"/>'
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        out += f'<circle cx="{x+22+i*18}" cy="{y+19}" r="5.5" fill="{c}" opacity=".9"/>'
    out += T(x + 84, y + 24, esc(label), 12.5, p["codemuted"] if dark else p["muted"], "m")
    if right:
        out += right
    return out


def section_head(y, cmd, title_parts, p, size=40):
    """cmd = mono-Prompt, title_parts = [(text, accent?)]"""
    out = T(48, y, f'<tspan fill="{p["accs"]}">$</tspan> {esc(cmd)}', 14, p["muted"], "m", 500)
    spans = "".join(f'<tspan fill="{p["acc"] if a else p["ink"]}">{esc(t)}</tspan>' for t, a in title_parts)
    out += T(46, y + size + 14, spans, size, p["ink"], "s", 800, ls=-0.035)
    return out


def build(p, suf):
    # ------------------------------------------------------------- HERO
    h = 470
    b = ""
    # Logo-Zeile
    b += T(48, 62, f'<tspan fill="{p["acc"]}">~</tspan>/jonas-haude', 15, p["ink"], "m", 700)
    b += T(W - 48, 62, "jonashaude.de", 13, p["muted"], "m", 500, anchor="end")
    # Headline
    b += T(46, 150, "Hi, ich bin", 30, p["text"], "s", 500, ls=-0.02)
    b += T(44, 222, f'Jonas Haude<tspan fill="{p["acc"]}">.</tspan>', 66, p["ink"], "s", 800, ls=-0.045)
    intro = ("Bei Scala X machen wir Gebäude digital, vom 3D-Laserscan bis zum BIM-Modell. "
             "Dazu baue ich Software, die Planen, Bauen und Betreiben schneller und genauer macht.")
    pt, yl = para(48, 268, intro, 400, 16.5, p["text"], 1.55)
    b += pt
    b += T(48, yl + 16.5 * 1.55, "Heute, nicht irgendwann.", 16.5, p["ink"], "s", 700)
    # Pills
    px, py = 48, 396
    for label, accent in [("Co-Founder · Scala X", True), ("Head of IT · thinkBIC", False)]:
        wv = width(label, 13, "mono", 600) + 30
        if accent:
            b += f'<rect x="{px}" y="{py}" width="{wv}" height="32" rx="16" fill="{p["acc"]}"/>'
            b += T(px + 15, py + 21, esc(label), 13, p["onacc"], "m", 600)
        else:
            b += f'<rect x="{px+.5}" y="{py+.5}" width="{wv-1}" height="31" rx="15.5" fill="none" stroke="{p["line"]}"/>'
            b += T(px + 15, py + 21, esc(label), 13, p["ink"], "m", 600)
        px += wv + 10
    # Terminal rechts
    tx, ty, tw, th = 500, 100, 332, 330
    b += f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="18" fill="{p["code"]}"/>'
    b += window_bar(tx, ty, tw, "jonas@bau: ~", p)
    lines = [
        (f'<tspan fill="{p["codeacc"]}">$</tspan> whoami', "codetext", 500),
        ("IT'ler auf'm Bau", "codetext", 800),
        ("", None, 0),
        (f'<tspan fill="{p["codeacc"]}">→</tspan> co-founder @ Scala X', "codetext", 500),
        ("  · gebäude digital erfassen", "codemuted", 400),
        (f'<tspan fill="{p["codeacc"]}">→</tspan> head of it @ thinkBIC', "codetext", 500),
        ("  · ki für die planprüfung", "codemuted", 400),
        (f'<tspan fill="{p["codeacc"]}">→</tspan> python seit 2012', "codetext", 500),
        ("  · ai-first seit dem ersten copilot", "codemuted", 400),
        ("", None, 0),
        (f'status: <tspan fill="{p["codeacc"]}">verändert die branche</tspan>', "codetext", 500),
    ]
    yy = ty + 72
    k = 0
    for txt, col, wg in lines:
        if col:
            size = 17 if wg == 800 else 13
            b += f'<g class="fade" style="animation-delay:{0.25 + k*0.18:.2f}s">' + \
                 T(tx + 22, yy, txt if "<tspan" in txt else esc(txt), size, p[col], "m", wg, extra=' xml:space="preserve"') + "</g>"
            k += 1
        yy += 22 if col else 10
    b += f'<g class="fade" style="animation-delay:{0.25 + k*0.18:.2f}s">' + \
         T(tx + 22, yy + 6, f'<tspan fill="{p["codeacc"]}">$</tspan>', 13, p["codetext"], "m", 500) + \
         f'<rect class="blink" x="{tx+38}" y="{yy-5}" width="8" height="15" fill="{p["codeacc"]}"/></g>'
    svg(f"hero-{suf}.svg", h, b, "Jonas Haude – IT'ler auf'm Bau. Co-Founder von Scala X, Head of IT bei thinkBIC.", p)

    # ------------------------------------------------------------- FIXES
    b = section_head(64, "git log --oneline fixes", [("Drei Baustellen. ", False), ("Jeden Tag.", True)], p, 34)
    fixes = [
        ("7be90d4", "Scala X", "Bestand wird Modell",
         "Aus 3D-Laserscans werden BIM-Modelle. Mit Scan4X entsteht das Modell direkt in der Punktwolke, nachvollziehbar und prüfbar.",
         "scan4x.py", "Zollstock und Skizze", ["modell = scan4x.modelliere(", "    punktwolke,", '    ziel=<S>"IFC"</S>,', ")"], "gebaeude.ifc"),
        ("e52a9f0", "Scala X", "Punktwolke wird Gebäudedaten",
         "Mit Scan4POI werden Zähler, technische Anlagen und Sicherheitseinrichtungen in Scans und 360°-Aufnahmen KI-gestützt erkannt und verortet.",
         "scan4poi.py", "Begehung mit Klemmbrett", ["pois = scan4poi.erkenne(", "    scan,", '    klassen=[<S>"Zähler"</S>,', '             <S>"Melder"</S>],', ")"], "pois.json fürs CAFM"),
        ("a1f3c2e", "thinkBIC", "KI prüft mit",
         "Bei thinkBIC verantworte ich die Technik hinter SaaS und KI, die Bauunterlagen, Pläne und BIM-Modelle automatisch auf Vollständigkeit, Qualität und Normen prüft.",
         "pruefung.py", "Textmarker", ["bericht = pruefe(", "    unterlagen,", '    regeln=[<S>"HOAI"</S>,', '            <S>"DIN"</S>, <S>"MBO"</S>],', ")"], "aufgaben ans planungsteam"),
    ]
    cy0 = 148
    cardw, kw = W - 96, 372
    nmax = max(len(f[6]) for f in fixes)
    kh = 84 + (nmax - 1) * 18 + 30 + 22
    ch = kh + 32
    for i, (hsh, co, title, desc, fn, vorher, code, result) in enumerate(fixes):
        cy = cy0 + i * (ch + 16)
        cx = 48
        kx, ky = cx + cardw - 16 - kw, cy + 16
        tw = kx - (cx + 28) - 32
        b += f'<rect x="{cx}" y="{cy}" width="{cardw}" height="{ch}" rx="18" fill="{p["surface"]}" stroke="{p["line"]}"/>'
        hash_pos = len(b)
        b += T(cx + 28, cy + 46, f'<tspan fill="{p["accs"]}">{hsh}</tspan> · {esc(co)}', 13, p["muted"], "m", 600)
        tl = wrap(title, tw, 26, "sans", 800, -0.025)
        dl_ = wrap(desc, tw, 15)
        # Inhalt (Kappe Hash-Zeile bis Unterlänge letzte Zeile) senkrecht mittig
        top_ink = 46 - 10
        bot_ink = 122 + (len(tl) - 1) * 30 + (len(dl_) - 1) * 23 + 4
        off = cy + (ch - (bot_ink - top_ink)) / 2 - top_ink - cy
        b = b[:hash_pos] + b[hash_pos:].replace(f'y="{cy + 46}"', f'y="{cy + 46 + off:.1f}"', 1)
        for j, l in enumerate(tl):
            b += T(cx + 27, f"{cy + 86 + off + j * 30:.1f}", esc(l), 26, p["ink"], "s", 800, ls=-0.025)
        dy = cy + 122 + off + (len(tl) - 1) * 30
        for j, l in enumerate(dl_):
            b += T(cx + 28, f"{dy + j * 23:.1f}", esc(l), 15, p["text"], "s")
        # Code-Fenster
        b += f'<rect x="{kx}" y="{ky}" width="{kw}" height="{kh}" rx="12" fill="{p["code"]}"/>'
        b += T(kx + 18, ky + 24, esc(fn), 12, p["codemuted"], "m", 500)
        b += f'<line x1="{kx}" y1="{ky+36}" x2="{kx+kw}" y2="{ky+36}" stroke="{p["codeline"]}"/>'
        b += T(kx + 18, ky + 62, esc("# vorher: " + vorher), 12, p["codemuted"], "m", 400)
        for j, l in enumerate(code):
            l = esc(l).replace("&lt;S&gt;", f'<tspan fill="{p["codeacc"]}">').replace("&lt;/S&gt;", "</tspan>")
            b += T(kx + 18, ky + 84 + j * 18, l, 12, p["codetext"], "m", 400, extra=' xml:space="preserve"')
        b += T(kx + 18, ky + kh - 20, f'<tspan fill="{p["codeacc"]}">→</tspan> {esc(result)}', 12, p["codestr"], "m", 600)
    cy = cy0 + 2 * (ch + 16)
    svg(f"fixes-{suf}.svg", cy + ch + 40, b, "Drei Baustellen. Jeden Tag. Scala X: Bestand wird Modell (Scan4X). Scala X: Punktwolke wird Gebäudedaten (Scan4POI). thinkBIC: KI prüft mit.", p)

    # ------------------------------------------------------------- SCALA X
    b = section_head(64, "ls ~/scala-x", [("Was ich bei ", False), ("Scala X", True), (" baue.", False)], p, 34)
    pt, yl = para(48, 148, "Scala X habe ich 2024 mitgegründet. Wir digitalisieren Bestandsgebäude mit 3D-Laserscanning "
                  "und machen aus den Daten etwas, mit dem man arbeiten kann.", 640, 16, p["text"], 1.55)
    b += pt
    b += T(48, yl + 34, "Digitize. Analyze. Optimize.", 14, p["accs"], "m", 700)
    # Featured Scan4X
    fy = yl + 62
    b += f'<rect x="48" y="{fy}" width="{W-96}" height="118" rx="18" fill="{p["code"]}"/>'
    b += T(72, fy + 34, "plattform", 12.5, p["codeacc"], "m", 600)
    b += T(72, fy + 74, "Scan4X", 34, "#f2f1ee", "s", 800, ls=-0.035)
    pt, _ = para(300, fy + 54, "Vom Laserscan zum BIM-Modell, direkt in der Punktwolke modelliert und gegen den Scan geprüft.",
                 480, 16, p["codetext"], 1.5)
    b += pt
    tiles = [
        ("customize", "Scan4POI", "Points of Interest aus Punktwolken und 360°-Aufnahmen, KI-gestützt erkannt und direkt nutzbar."),
        ("digitize", "Scan4Documentation", "Bestandsdigitalisierung: aktuell, schnell und präzise, als Grundlage für Umbau und Betrieb."),
        ("analyze", "Scan4Valuation", "Automatisierte Datenanalytik für belastbare Bewertungen und Gutachten."),
        ("optimize", "Scan4ESG", "Nachhaltigkeitskennzahlen für Gebäude und Portfolios, auf Basis echter Scandaten."),
    ]
    tw4, g4 = (W - 96 - 3 * 14) / 4, 14
    ty4 = fy + 118 + 14
    descs = [wrap(t[2], tw4 - 36, 13) for t in tiles]
    th4 = 100 + max(len(d) for d in descs) * 20
    for i, (tag, name, d) in enumerate(tiles):
        x = 48 + i * (tw4 + g4)
        b += f'<rect x="{x:.1f}" y="{ty4}" width="{tw4:.1f}" height="{th4}" rx="18" fill="{p["surface"]}" stroke="{p["line"]}"/>'
        b += T(f"{x+18:.1f}", ty4 + 32, esc(tag), 12, p["accs"], "m", 600)
        nsize = min(19, *[int(10 * 19 * (tw4 - 40) / width(t[1], 19, "sans", 800, -0.02)) / 10 for t in tiles])
        b += T(f"{x+18:.1f}", ty4 + 66, esc(name), nsize, p["ink"], "s", 800, ls=-0.02)
        for j, l in enumerate(descs[i]):
            b += T(f"{x+18:.1f}", ty4 + 96 + j * 20, esc(l), 13, p["text"], "s")
    svg(f"scalax-{suf}.svg", ty4 + th4 + 40, b, "Was ich bei Scala X baue: Scan4X, Scan4POI, Scan4Documentation, Scan4Valuation, Scan4ESG. Digitize. Analyze. Optimize.", p)

    # ------------------------------------------------------------- KONTAKT
    h = 344
    b = f'<rect width="{W}" height="{h}" rx="{R}" fill="{p["code"]}"/>'
    b += T(48, 64, f'<tspan fill="{p["codeacc"]}">$</tspan> ./kontakt.sh', 14, p["codemuted"], "m", 500)
    b += T(46, 124, "Lass uns die Branche", 44, "#f2f1ee", "s", 800, ls=-0.04)
    b += T(46, 174, f'<tspan fill="{p["codeacc"]}">umbauen.</tspan>', 44, "#f2f1ee", "s", 800, ls=-0.04)
    b += T(W - 48, 140, "schreib mir", 13, p["codemuted"], "m", 500, anchor="end")
    b += T(W - 48, 174, "hallo@jonashaude.de", 18, "#f2f1ee", "m", 700, anchor="end")
    b += f'<line x1="48" y1="212" x2="{W-48}" y2="212" stroke="{p["codeline"]}"/>'
    s1 = "python · java · spring boot · angular · azure · aws · gcp · docker"
    s2 = "llms · rag · agents · github copilot · claude code"
    b += T(48, 246, f'<tspan fill="{p["codeacc"]}">stack</tspan> = {esc(s1)}', 13.5, p["codetext"], "m", 500)
    b += T(48, 272, f'<tspan fill="{p["codeacc"]}">ai</tspan>    = {esc(s2)}', 13.5, p["codetext"], "m", 500, extra=' xml:space="preserve"')
    b += T(48, 306, "© 2026 Jonas Haude · Lünen, NRW · exit 0", 12, p["codemuted"], "m", 500)
    svg(f"kontakt-{suf}.svg", h, b, "Lass uns die Branche umbauen. hallo@jonashaude.de", p)

    # ------------------------------------------------------------- Buttons
    for key, label in [("web", "jonashaude.de"), ("linkedin", "linkedin"), ("instagram", "instagram"), ("mail", "hallo@jonashaude.de"), ("scalax", "scala-x.de")]:
        bw = int(width(label, 13, "mono", 700) + 52)
        MONO_B64 = font_b64("jetbrains-mono-var.woff2", "".join(sorted(set(label + "→"))))
        primary = key == "mail"
        fill = p["acc"] if primary else p["surface"]
        col = p["onacc"] if primary else p["ink"]
        stroke = "none" if primary else p["line"]
        s = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw}" height="40" viewBox="0 0 {bw} 40" role="img" aria-label="{label}">'
             f'<style>@font-face{{font-family:JM;src:url(data:font/woff2;base64,{MONO_B64}) format("woff2");font-weight:100 800}}'
             f'.m{{font-family:JM,ui-monospace,Menlo,monospace}}</style>'
             f'<rect x=".5" y=".5" width="{bw-1}" height="39" rx="19.5" fill="{fill}" stroke="{stroke}"/>'
             f'<text x="22" y="25" class="m" font-size="13" font-weight="700" fill="{p["acc"] if not primary else p["onacc"]}">→</text>'
             f'<text x="40" y="25" class="m" font-size="13" font-weight="700" fill="{col}">{label}</text></svg>')
        (OUT / f"btn-{key}-{suf}.svg").write_text(s, encoding="utf-8")


build(LIGHT, "light")
build(DARK, "dark")
print("ok", sorted(x.name for x in OUT.iterdir()))
