# Round-2 prototype (reference only)

Throwaway prototype from the visual exploration of 2026-10-10, kept beside
`../../2026-10-10-subdomain-landings-design.md` for reference. It is not
product code: the build re-implements it inside `frontend/`, and every value
it needs is in the spec's Appendix B.

- `src/kit/landing.css`, `landing.js`, `scenes.js`: styles, logo motion A and
  the ∞ wipe, the two three.js scenes.
- `make_pages.py`: writes the four hero pages (cv-1, cv-2, voyage-1, voyage-2)
  into `src/`. The chosen ones are cv-2 and voyage-2.
- `build.py`: builds `out/` with the logo data read from
  `frontend/public/brand/`. `out/` is not committed.

Preview: `python3 build.py && cd out && python3 -m http.server`, then open
`http://127.0.0.1:8000/index-preview.html`.
