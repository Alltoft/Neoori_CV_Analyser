"""Writes the four round-2 hero mockups into src/ from shared pieces."""
import pathlib

SRC = pathlib.Path(__file__).parent / "src"

ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
OUT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8"/></svg>'
MENU = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'
CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>'

IMPORTMAP = ('<script type="importmap">{ "imports": {'
             ' "three": "https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.module.js",'
             ' "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/" } }</script>')


def head(title, theme):
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="theme-color" content="{theme}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=JetBrains+Mono:wght@500;600;700&amp;family=Plus+Jakarta+Sans:wght@700;800&amp;display=swap">
<link rel="stylesheet" href="kit/landing.css">
{IMPORTMAP}
</head>"""


def nav(app):
    if app == "cv":
        logo, links, cross = "navy", [("#comment", "Comment ça marche"), ("#conseillers", "Pour les conseillers"), ("#", "Tarifs"), ("#", "Questions")], "Le voyage"
    else:
        logo, links, cross = "light", [("#etapes", "Les six étapes"), ("#conseillers", "Pour les conseillers"), ("#", "Questions")], "J’ai une cible"
    items = "".join(f'<a href="{h}"{" data-inert" if h == "#" else ""}>{t}</a>' for h, t in links)
    return f"""<header class="nav">
  <div class="container nav-in">
    <a class="logo-link" href="#" data-inert aria-label="neoori, accueil"><span data-logo="{logo}" data-play="once"></span></a>
    <nav class="nav-links" aria-label="Sections">{items}</nav>
    <div class="nav-actions">
      <a class="nav-signin" href="#" data-inert>Se connecter</a>
      <a class="nav-cross" href="#" data-inert>{cross} {OUT}</a>
      <button class="nav-menu" type="button" aria-label="Menu">{MENU}</button>
    </div>
  </div>
</header>"""


def doors(app):
    if app == "cv":
        a = ("Analyser mon CV", "Gratuit pour commencer, avec ou sans compte.")
        b = "Vos codes, et les rapports qui vous reviennent."
    else:
        a = ("Commencer le voyage", "Session 0&#160;: cinq minutes, en autonomie.")
        b = "Vos codes, les séances, le portrait à valider."
    return f"""<div class="doors" style="--i:3">
        <div class="door"><a class="btn btn-primary" href="#" data-wipe-open>{a[0]} {ARROW}</a><p class="door-note">{a[1]}</p></div>
        <div class="door"><a class="btn btn-secondary" href="#conseillers">Je suis conseiller</a><p class="door-note">{b}</p></div>
      </div>"""


CV_COPY = """<span class="label" style="--i:0">J’ai une cible</span>
      <h1 id="h" style="--i:1">Lire un parcours face à sa cible.</h1>
      <p class="sub" style="--i:2">Un métier, une formation, un poste, un projet&#160;: neoori lit le CV face à ce qui est visé, et montre les forces, ce qui reste à renforcer et par où avancer.</p>"""

VOY_COPY = """<span class="label" style="--i:0">Le voyage</span>
      <h1 id="h" style="--i:1">Du brouillard à la clarté, une étape après l’autre.</h1>
      <p class="sub" style="--i:2">Six étapes pour poser ce que vous savez déjà de vous. La première se fait en cinq minutes, en autonomie&#8239;; les cinq suivantes, avec un conseiller.</p>"""


def advisors(app):
    if app == "cv":
        h = "Proposez l’analyse aux personnes que vous accompagnez."
        pts = ["Des codes à remettre, pour une analyse ou pour un voyage.",
               "Avec votre code, le rapport complet vous revient, à vous seul.",
               "Une note privée sur chaque analyse, que vous seul lisez.",
               "Pour toute cible&#160;: un métier, une formation, un poste, un projet."]
    else:
        h = "Accompagnez chaque voyage, séance après séance."
        pts = ["Votre code ouvre les sessions 1 à 5.",
               "Une fiche de suivi par voyage, rien que pour vous.",
               "Le portrait se relit ensemble et n’est remis qu’après votre validation.",
               "Le voyage peut ensuite nourrir les analyses de CV."]
    lis = "".join(f"<li>{CHECK}<span>{p}</span></li>" for p in pts)
    return f"""<section class="advisors" id="conseillers" aria-labelledby="adv-h">
  <div class="container">
    <div>
      <span class="label">Pour les conseillers</span>
      <h2 id="adv-h">{h}</h2>
      <div class="links"><a class="btn btn-dark" href="#" data-inert>Créer un compte conseiller</a><a class="btn btn-line" href="#" data-inert>Se connecter</a></div>
    </div>
    <ul>{lis}</ul>
  </div>
</section>"""


def wipe(app):
    if app == "cv":
        inner = """<span class="label">Nouvelle analyse</span>
    <h2 id="wipe-h">Votre CV et votre cible</h2>
    <div class="fld"><span>Votre CV</span><div>Déposez un PDF ou collez le texte</div></div>
    <div class="fld"><span>Votre cible</span><div>Un métier, une formation, un poste, un projet…</div></div>"""
    else:
        inner = """<span class="label" style="color:#b4532a">Session 0 · cinq minutes</span>
    <h2 id="wipe-h">Dans 10 ans</h2>
    <p style="color:#56637b">20 affirmations. Pour chacune&#8239;: oui, non ou «&#8239;–&#8239;».</p>
    <div class="bar" aria-hidden="true"><i></i></div>"""
    return f"""<div class="wipe" id="wipe" hidden role="dialog" aria-modal="true" aria-labelledby="wipe-h">
  <div class="wipe-card">
    {inner}
    <p class="wipe-note">Maquette&#160;: sur le site, c’est la vraie page qui s’ouvre ici.</p>
    <div><button type="button" class="btn btn-line" data-wipe-back>Retour</button></div>
  </div>
</div>
<svg class="wipe-ring" id="wipeRing" aria-hidden="true"><circle r="0" fill="none" stroke-width="5"/></svg>"""


def page(name, title, app, hero, module):
    theme = "#ffffff" if app == "cv" else "#1c3561"
    body_class = "cv" if app == "cv" else "voy"
    html = f"""{head(title, theme)}
<body class="{body_class}">
{nav(app)}
<main>
{hero}
{advisors(app)}
</main>
{wipe(app)}
<script src="kit/landing.js"></script>
<script type="module">
{module}
</script>
</body>
</html>
"""
    (SRC / name).write_text(html)


CV1 = f"""<section class="hero-split" aria-labelledby="h">
  <div class="container">
    <div class="hero-copy rise">
      {CV_COPY}
      {doors("cv")}
    </div>
    <div class="panel" id="sheet3d" aria-hidden="true">
      <span class="chip c2"><b>§3</b>Compétences transférables</span>
      <span class="chip c1"><b>§2</b>Forces du profil pour la cible</span>
    </div>
  </div>
</section>"""

TIERS = """<div class="index-band" id="comment">
    <div class="container">
      <div class="index-head"><h2>Ce que contient le rapport</h2><p>Commencez gratuitement&#160;: §1 à §3 et un verdict. Le reste s’ajoute quand vous le souhaitez.</p></div>
      <div class="tiers">
        <section class="tier" aria-label="Gratuit"><div class="tier-name"><span class="label">Pour commencer</span><span class="tag free">Gratuit</span></div>
          <ol><li><b>§1</b>Lecture stratégique du parcours</li><li><b>§2</b>Forces du profil pour la cible</li><li><b>§3</b>Compétences transférables</li><li><b>✓</b>Verdict</li></ol></section>
        <section class="tier" aria-label="Rapport complet"><div class="tier-name"><span class="label">Rapport complet</span><span class="tag full">Complet</span></div>
          <ol><li><b>§4</b>Ce qui reste à renforcer</li><li><b>§5</b>Préconisations terrain</li><li><b>§6</b>Exemple de réécriture</li><li><b>§7</b>Synthèse pour le candidat</li><li><b>§8</b>Pistes d’évolution</li><li><b>§9</b>Proposition de CV retravaillé</li></ol></section>
        <section class="tier" aria-label="Premium"><div class="tier-name"><span class="label">En plus</span><span class="tag prem">Premium</span></div>
          <ol><li><b>§10</b>Préparation à l’entretien</li><li><b>§11</b>Questions difficiles</li></ol></section>
      </div>
    </div>
  </div>"""

CV2 = f"""<section class="hero-index" aria-labelledby="h">
  <div class="container">
    <div class="rise" style="display:grid;gap:24px;justify-items:start;position:relative;z-index:4">
      {CV_COPY}
      {doors("cv")}
    </div>
    <div class="object" id="sheet3d" aria-hidden="true"></div>
  </div>
  {TIERS}
</section>"""

V1 = f"""<section class="hero-mist" id="hero" aria-labelledby="h">
  <div class="stage" id="mark3d" aria-hidden="true"></div>
  <div class="mist" aria-hidden="true"></div><div class="mist m2" aria-hidden="true"></div><div class="dawn" aria-hidden="true"></div>
  <div class="container">
    <div class="copy rise">
      {VOY_COPY}
      {doors("voy")}
    </div>
  </div>
</section>"""

STEPS = "".join(
    f'<li class="step{" lit" if i == 0 else ""}"><i></i><b>Session {i}</b>{f"<span>{cap}</span>" if cap else ""}</li>'
    for i, cap in enumerate(["Dans 10 ans · cinq minutes, en autonomie", "avec votre conseiller", "", "", "", "puis le portrait, relu ensemble"]))

V2 = f"""<section class="hero-path" id="hero" aria-labelledby="h">
  <div class="stage" id="mark3d" aria-hidden="true"></div>
  <div class="mist-left" aria-hidden="true"></div><div class="mist" aria-hidden="true"></div>
  <div class="container">
    <div class="copy rise">
      {VOY_COPY}
      {doors("voy")}
    </div>
    <div class="path" id="etapes"><ol aria-label="Les six étapes du voyage">{STEPS}</ol></div>
  </div>
</section>"""

M_CV1 = """import { mountSheet } from "./kit/scenes.js";
mountSheet(document.getElementById("sheet3d"), { layout: (a, v) => ({ x: 0.08, y: -0.06, s: Math.min(1.05, v.w / 2.95) }) });"""
M_CV2 = """import { mountSheet } from "./kit/scenes.js";
mountSheet(document.getElementById("sheet3d"), {
  pointerArea: document.body,
  layout: (a, v) => window.innerWidth > 900
    ? { x: 0.05, y: 0, s: Math.min(1.12, v.w / 2.8) }
    : { x: 0.05, y: -0.12, s: Math.min(1.18, v.h / 3.9) },
});"""
M_V1 = """import { mountMark } from "./kit/scenes.js";
mountMark(document.getElementById("mark3d"), {
  markPath: window.NEOORI.mark, pointerArea: document.getElementById("hero"),
  layout: (a, v) => window.innerWidth > 900
    ? { x: v.w * 0.25, y: 0.1, s: Math.min(1, (v.w * 0.4) / 3.94) }
    : { x: 0, y: 0, s: Math.min(0.85, (v.w * 0.78) / 3.94) },
});"""
M_V2 = """import { mountMark } from "./kit/scenes.js";
mountMark(document.getElementById("mark3d"), {
  markPath: window.NEOORI.mark, pointerArea: document.getElementById("hero"),
  layout: (a, v) => window.innerWidth > 900
    ? { x: v.w * 0.31, y: v.h * 0.06, s: Math.min(0.72, (v.w * 0.3) / 3.94) }
    : { x: 0, y: 0, s: Math.min(0.7, (v.w * 0.62) / 3.94) },
});"""

page("cv-1.html", "cv. · 1 · Côte à côte (maquette)", "cv", CV1, M_CV1)
page("cv-2.html", "cv. · 2 · Le rapport en index (maquette)", "cv", CV2, M_CV2)
page("voyage-1.html", "voyage. · 1 · Brouillard (maquette)", "voy", V1, M_V1)
page("voyage-2.html", "voyage. · 2 · Six étapes (maquette)", "voy", V2, M_V2)
print("wrote", sorted(p.name for p in SRC.glob("*.html")))
