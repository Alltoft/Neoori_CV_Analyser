# Retour PM — 05/06/2026

## Corrigé

1. **Landing** — pitch 3 étapes → 4 étapes (parcours / projet / analyse ATS+humaine / CV optimisé).
2. **Prénom + Nom** — champ unique scindé, Nom auto-majuscule, transmis au prompt.
3. **Consentement** — « portrait de potentiel » → « cette analyse et vous faire des suggestions ».
4. **Mobilité** — sélection multiple (chips), jointure ` + ` côté prompt + livrable.
5. **Loader** — textes alignés sur la version PM (6 étapes nommées). Design inchangé.
6. **Impression / PDF** — A4 + marges, plus de saut de page par section, paywall lisible, bouton tableau de bord redirigé vers `/rapport?print=1`.

## Non corrigé en code

- **« Erreur inattendue »** — limite plan gratuit Render. Attendre et relancer. À régler par upgrade plan.
- **Analyse longue / redondante (§8)** — éditer le prompt depuis `/admin/prompts` (historique + rollback + A/B). Pas de modif code.
- **Pistes de reconversion manquantes (§9)** — même chose : ajuster le prompt via admin.

## À tester en live

- Soumettre une analyse complète (Chemin A) avec Prénom + Nom + plusieurs mobilités.
- Imprimer le rapport → vérifier A4 plein page, sections lisibles.
- Vérifier le loader (6 étapes, nouveau titre).
