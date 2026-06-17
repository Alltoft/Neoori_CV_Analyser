# neoori — Image shot-list (handoff)

You generate these (nanobanana or any model). Save each to the **exact path** below, inside
`frontend/public/`. The code already references them — once the file exists at the path, it appears.

> Until a file exists, the page shows a warm brand-colored placeholder (no broken layout, no build error).

## Art direction (apply to ALL photos — keep them a consistent set)

- **Style:** editorial *documentary* photography. Authentic, candid, optimistic — **not** stocky, posed, or cheesy.
- **People:** diverse French working-age adults (mix of ages 20s–55+, origins, one wheelchair user welcome — this serves Cap Emploi). Real expressions, no fake laughing-with-salad.
- **Light:** soft, warm natural daylight. Bright, airy.
- **Palette in-scene:** lean into **deep navy `#0f1e34`** and **warm orange `#ff7a39`** accents (clothing, objects, walls), warm neutral/cream backgrounds. No competing bright colors (no teal/green/purple).
- **Setting:** modern but human French workplaces / public-employment offices / bright meeting rooms. Avoid generic Silicon-Valley startup clichés.
- **Composition:** generous negative space on one side for text overlay. Shallow depth of field.
- **Format:** JPG, sRGB, quality ~80, no text baked in, no watermark.

---

## 1 — Hero (landing) · `frontend/public/img/hero-counselor.jpg`
**Size:** 1600 × 1200 (4:3). Right/left third should be calmer for overlay.
**Prompt:**
> Documentary photo of a warm French career counselor (40s, approachable) sitting beside a job-seeker (30s) at a light wooden table in a bright modern public-employment office, both looking at a tablet together, the counselor gesturing encouragingly. Soft natural window light, warm cream walls, a hint of deep-navy and warm-orange in their clothing. Candid, optimistic, hopeful mood. Shallow depth of field, 35mm, editorial. Generous empty space on the right side. No text.

## 2 — Persona: Candidat · `frontend/public/img/persona-candidat.jpg`
**Size:** 1000 × 1250 (4:5).
**Prompt:**
> Documentary portrait of a confident French job-seeker in their early 30s, diverse, holding a printed CV, calm hopeful half-smile, looking slightly off-camera. Bright warm cream background, soft daylight, subtle navy/orange tones in clothing. Authentic, not posed. Shallow depth of field. No text.

## 3 — Persona: Conseiller · `frontend/public/img/persona-conseiller.jpg`
**Size:** 1000 × 1250 (4:5).
**Prompt:**
> Documentary photo of a French employment counselor at a tidy desk in a Cap Emploi / France Travail style office, mid-conversation, warm and attentive, a laptop and notepad on the desk. Soft daylight, warm neutral tones with navy/orange accents. Authentic, professional, reassuring. Shallow depth of field. No text.

## 4 — Persona: Organisation · `frontend/public/img/persona-organisation.jpg`
**Size:** 1000 × 1250 (4:5).
**Prompt:**
> Documentary photo of a small diverse French team (3 people, one a wheelchair user) in a bright modern meeting room reviewing something together on a screen, collaborative and engaged. Warm daylight, cream walls, navy/orange accents. Public-sector / training-organisation feel, optimistic. Shallow depth of field. No text.

## 5 — Auth side panel · `frontend/public/img/auth-side.jpg`
**Size:** 1200 × 1500 (4:5 portrait) — fills a tall split-screen panel.
**Prompt:**
> Soft, slightly out-of-focus documentary photo of a French professional writing/reviewing a CV at a sunlit desk, warm cream and deep-navy tones with a warm-orange glow from window light. Calm, motivational, premium. Lots of soft bokeh. No faces required (over-the-shoulder or hands-on-paper is ideal). No text.

## 6 — Social / OG cover · `frontend/public/img/og-cover.png`
**Size:** 1200 × 630 (PNG). This is the link-preview card (LinkedIn/Slack/email).
**Prompt:**
> Clean branded cover on a deep-navy `#0f1e34` background with a soft warm-orange glow lower-left. Centered composition leaving room for the neoori logo (added separately). A subtle pair of overlapping thin rings (one orange `#ff7a39`, one mid-blue `#15386d`) echoing an infinity mark, lower-right, low opacity. Premium, minimal, institutional. No text needed (logo/title overlaid in code is fine, but bake nothing).

## 7 — Square mark (optional) · `frontend/public/img/neoori-mark.png`
**Size:** 512 × 512 (PNG, transparent). Just the **figure/flame glyph** from the left of your logo (no wordmark), centered, on transparent. Used for the favicon, loading screen, and small avatars.
**Prompt:**
> The neoori figure glyph only — the leaping figure made of an orange-gradient blade with a round orange head and a deep-navy base — centered on a transparent square canvas, generous padding, crisp edges. Exactly matches the mark in the existing logo. No wordmark, no text, no background.

---

### Notes
- Paths are referenced in code as `/img/<name>` (Next serves `frontend/public/` at `/`).
- The full logo lockup is already in place at `frontend/public/neoori-logo.png` — **do not change it.**
- If you'd rather skip an image, tell me and I'll swap that slot for the ring-motif/illustration treatment.
