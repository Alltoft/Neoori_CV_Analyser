/* Round 2 — shared behaviour for the four hero mockups:
   the logo (motion A, picked in round 1), the ∞ wipe on the main button,
   and the hand-off of the oo mark's path to the 3D module. */
(() => {
  const L = /*LOGO_DATA*/;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const C = 2 * Math.PI * 47.24; // circumference of the oo's mid-circle

  function bezier(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const sx = (t) => ((ax * t + bx) * t + cx) * t;
    const sy = (t) => ((ay * t + by) * t + cy) * t;
    const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
    return (x) => {
      if (x <= 0) return 0; if (x >= 1) return 1;
      let t = x;
      for (let i = 0; i < 8; i++) { const e = sx(t) - x, d = dx(t); if (Math.abs(e) < 1e-6 || Math.abs(d) < 1e-6) break; t -= e / d; }
      return sy(Math.min(1, Math.max(0, t)));
    };
  }
  const camera = bezier(0.76, 0, 0.24, 1); // the ad's wipe curve
  const clamp01 = (v) => Math.min(1, Math.max(0, v));
  const smooth = (a, b, v) => { const t = clamp01((v - a) / (b - a)); return t * t * (3 - 2 * t); };

  let uid = 0;
  function logoSVG(onDark) {
    const id = `lg${uid++}`;
    const stops = L.g.stops.map(([o, c]) => `<stop offset="${o}" stop-color="${c}"/>`).join("");
    return `<svg class="logo" viewBox="0 0 627 175" role="img" aria-label="neoori">
      <defs>
        <linearGradient id="${id}-g" x1="${L.g.x1}" y1="0" x2="${L.g.x2}" y2="0" gradientUnits="userSpaceOnUse">${stops}</linearGradient>
        <mask id="${id}-m" maskUnits="userSpaceOnUse" x="0" y="-40" width="627" height="260">
          <circle class="ring" cx="323.97" cy="108.21" r="47.24" fill="none" stroke="#fff" stroke-width="44" stroke-dasharray="${C} ${C}" stroke-dashoffset="0" transform="rotate(-90 323.97 108.21)"/>
          <circle class="ring" cx="418.45" cy="108.21" r="47.24" fill="none" stroke="#fff" stroke-width="44" stroke-dasharray="${C} ${C}" stroke-dashoffset="0" transform="rotate(90 418.45 108.21)"/>
        </mask>
      </defs>
      <g fill="${onDark ? "#ffffff" : L.navy}">${["n", "e", "r", "i"].map((k) => `<path class="l" d="${L.letters[k]}"/>`).join("")}</g>
      <path d="${L.oo}" fill="url(#${id}-g)" mask="url(#${id}-m)"/>
    </svg>`;
  }

  // Motion A · Tracé: the rings draw, then the letters rise. Once per page load.
  function playLogo(svg) {
    const [rl, rr] = svg.querySelectorAll(".ring");
    const draw = [{ strokeDashoffset: C }, { strokeDashoffset: 0 }];
    rl.animate(draw, { duration: 900, easing: "cubic-bezier(.65,0,.35,1)", fill: "both" });
    rr.animate(draw, { duration: 900, delay: 160, easing: "cubic-bezier(.65,0,.35,1)", fill: "both" });
    svg.querySelectorAll(".l").forEach((p, i) =>
      p.animate([{ transform: "translateY(28px)", opacity: 0 }, { transform: "none", opacity: 1 }],
        { duration: 620, delay: 560 + i * 70, easing: "cubic-bezier(.16,1,.3,1)", fill: "both" }));
  }

  document.querySelectorAll("[data-logo]").forEach((el) => {
    el.innerHTML = logoSVG(el.dataset.logo === "light");
    const svg = el.querySelector("svg");
    svg.querySelectorAll(".l").forEach((p) => { p.style.transformBox = "view-box"; });
    if (!reduce && el.dataset.play === "once") playLogo(svg);
  });

  // The ∞ wipe: a circle grows from the main button, led by a thin ring,
  // and opens the product (here a preview card; on the site, the real page).
  const wipe = document.getElementById("wipe");
  const ring = document.querySelector("#wipeRing circle");
  if (wipe && ring) {
    let origin = null, busy = false, opener = null;
    const ringColor = getComputedStyle(document.body).getPropertyValue("--ring").trim() || "#ea5624";
    ring.setAttribute("stroke", ringColor);
    const run = (open, x, y) => {
      if (busy) return; busy = true;
      const maxR = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)) + 12;
      ring.setAttribute("cx", x); ring.setAttribute("cy", y);
      wipe.hidden = false;
      const dur = reduce ? 1 : 900, t0 = performance.now();
      const step = (now) => {
        const p = camera(clamp01((now - t0) / dur));
        const r = open ? p * maxR : (1 - p) * maxR;
        wipe.style.clipPath = `circle(${r.toFixed(1)}px at ${x}px ${y}px)`;
        ring.setAttribute("r", r.toFixed(1));
        ring.setAttribute("opacity", String(open ? 1 - smooth(0.55, 1, p) : smooth(0, 0.25, p) * (1 - smooth(0.75, 1, p))));
        if (p < 1) { requestAnimationFrame(step); return; }
        ring.setAttribute("r", "0"); busy = false;
        if (open) { wipe.style.clipPath = ""; wipe.querySelector("[data-wipe-back]").focus({ preventScroll: true }); }
        else { wipe.hidden = true; wipe.style.clipPath = ""; opener && opener.focus({ preventScroll: true }); }
      };
      requestAnimationFrame(step);
    };
    document.querySelectorAll("[data-wipe-open]").forEach((btn) => btn.addEventListener("click", (e) => {
      e.preventDefault();
      const b = btn.getBoundingClientRect();
      origin = { x: b.left + b.width / 2, y: b.top + b.height / 2 }; opener = btn;
      run(true, origin.x, origin.y);
    }));
    const close = () => origin && run(false, origin.x, origin.y);
    wipe.querySelector("[data-wipe-back]").addEventListener("click", close);
    wipe.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  }

  // Inert links in the mockup (sign-in, menu, cross-app) do nothing on click.
  document.querySelectorAll("a[data-inert]").forEach((a) => a.addEventListener("click", (e) => e.preventDefault()));

  window.NEOORI = { mark: L.mark };
})();
