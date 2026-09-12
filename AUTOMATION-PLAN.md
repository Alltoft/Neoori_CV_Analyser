# Automation plan — intake robot, toy shop, box discipline

**Status:** proposal, nothing built yet. Drafted 23/08/2026.
**Goal:** stop hand-relaying PM reports into code, without losing the safety that
the hand-relaying currently provides.

---

## Why

Today the loop is: PMs report something in WhatsApp → the developer translates it
into a technical task → Claude writes the change → `git push` → live in ~3 minutes.

The developer's own read of this is "all I do is redirect." That undersells it. The
relay step is doing four jobs at once:

1. turning a non-technical complaint into a spec ("the button is weird" → *which*
   button, what was expected, what happened)
2. filtering noise — most chat traffic is chat, not bug reports
3. deciding whether something is a bug, a question, or a settings change
4. being the person who answers for a bad deploy

The plan below automates **(2)** entirely, assists with **(1)** and **(3)**, and
deliberately leaves **(4)** with a human.

## What exists today (verified 23/08/2026)

| | |
|---|---|
| CI workflows | `deploy.yml` only |
| Tests / lint in CI | none |
| Branch protection | none (`initial` unprotected) |
| Triggers | push to `initial` or `main` → build → prod, ~3 min |
| Staging | none |
| Review gate | none |
| Prod data | 9 tables, 0 users, 0 analyses (pre-cutover) |
| Prod host | KVM2, 2 vCPU, 7.8 GB RAM, 96 GB disk — load 0.00, containers ~750 MB |

**The only gate between a WhatsApp message and production is the developer.**
That is the thing this plan must not remove before replacing it.

## Principles

These are the load-bearing decisions. Everything else is detail.

1. **The human stops being the typist, stays the approver.** No change reaches
   users without a person pressing a button.
2. **No agent gets Docker.** Docker socket access is root on the host — a process
   that can `docker compose up` staging can equally read `/srv/neoori/.env`, dump
   the production database, or stop prod. There is no partial version of this.
   Therefore agents never run Docker anywhere, and the "robot can touch staging but
   not prod" boundary is a wall, not a promise.
3. **GitHub is the box.** A proposed change is a branch/PR. Nothing is copied
   between machines by an agent; GitHub Actions builds and deploys, exactly as it
   already does for prod. This is what makes principle 2 affordable.
4. **The robot is shy, not eager.** Missing a real report for a few hours costs
   nothing — the PMs will repeat themselves. Three false alarms and the digest
   stops being read, and then the robot is worthless. When unsure: stay quiet.
5. **The toy shop never sees a real CV.** Fake seeded data only.
6. **Consent is a prerequisite, not a feature.** See below.

## Architecture

```
PMs chat in WhatsApp
        │
        ▼
   ROBOT  (home machine, always on)
   reads · ignores media/chatter · classifies
        │
        │  digest 2×/day → developer only
        ▼
   DEVELOPER  "yes, fix #2"
        │
        ▼
   CODER  (Claude Code, headless)
   pushes a branch  ──────────►  GITHUB  ← the box lives here
                                    │
                                    │ Actions builds + deploys
                                    ▼
                              TOY SHOP  (prod VPS, isolated, fake data)
                                    │
        ┌───────────────────────────┘
        ▼
   ROBOT → developer + PMs: "ready, link"
        │
        ▼
   PM tests the exact thing they reported → approves
        │
        ▼
   DEVELOPER clicks Merge
        │
        ▼
   GITHUB Actions ──► PROD (neoori.tech)
```

| Component | Lives on | May | May not |
|---|---|---|---|
| Robot | home machine | read WhatsApp, message the developer | touch code, Docker, prod |
| Coder | home machine | push side branches | merge, deploy, SSH prod |
| Toy shop | prod VPS, isolated stack | run a fake-data copy | see real CVs or live keys |
| Prod | prod VPS | serve users | — (unchanged by this plan) |

Only **two machines**. Because CI does all building, the coder needs no Docker, so
robot and coder can share the home machine without weakening the boundary.

## Components

### 1. Robot — triage

Runs on an otherwise-unused computer at home. Only makes **outbound** connections
(WhatsApp, GitHub, Anthropic), so no port forwarding, static IP, or inbound
firewall holes are needed.

Behaviour:

- **Text only, at first.** Ignores TikTok links, memes, images, voice notes. This
  also sidesteps the weakest capability — Darija voice-note transcription. French
  text is handled well; Darija in Latin script (3/7/9 substitutions) is workable
  but should be flagged low-confidence rather than acted on.
- **Classifies each thread** into: chatter · question (needs an answer, not a
  change) · real defect · **prompt tuning** · feature request · unclear.
- **`prompt tuning` is a first-class category on purpose.** Length, tone and
  redundancy complaints belong in `/admin/prompts`, not in code. This is the single
  most likely thing for a naive robot to "fix" wrongly, so it gets named explicitly
  and routes to the PM, never to a branch.
- **Never posts in the group.** It messages the developer only. Digest 2×/day plus
  an urgent ping if something reads as site-down.
- **Drafts, does not send.** For questions it drafts a reply the developer can
  copy; it does not answer on anyone's behalf.
- **Daily heartbeat**, so a power cut or dead internet is visible rather than
  silent.
- **Kill switch:** one command stops it. Documented next to the runbook.
- **Audit log:** every message it classified, every digest, every decision taken —
  so "who approved this" always has an answer.

Auth: `claude setup-token` (subscription, no `ANTHROPIC_API_KEY`) then headless
`claude -p` with `--allowedTools` restricted. Caveat: the robot draws from the same
subscription quota as the developer's interactive work — batching to 2×/day keeps
this small; a busy period may justify a separate subscription or the API for the
triage step, which costs fractions of a cent per day at this volume.

### 2. Coder

Same machine. Claude Code headless, invoked after the developer approves an item.
Writes the change on a branch, pushes, opens a PR. Holds a GitHub token scoped to
push — **not** merge. No VPS credentials of any kind.

### 3. Toy shop — staging

Runs **on the existing prod VPS**, as a separate isolated stack. The host is idle
(load 0.00, 750 MB of 7.8 GB used, 91 GB free) and images are built in CI, not on
the box, so this costs almost nothing and needs no second server.

- Separate compose **project name** (`neoori-staging`) → own network, own container
  names, no collisions
- **Own MySQL container and volume.** A prod dump is never restored into it
- **Seeded fake data** — invented candidates, invented CVs. Needs a seed script
  alongside the existing `seed_prompt_v17.py`
- `staging.neoori.tech`, added to the existing certificate, own nginx server block
- **Basic auth + `noindex`** so it stays out of Google and away from strangers,
  with a shared password the PMs get
- **Its own secrets, and this matters:** `STRIPE_SECRET_KEY` must be a `sk_test_`
  key, and outbound email must be disabled or redirected to a catch-all. A staging
  environment that can charge a card or email a real beneficiary is not a staging
  environment
- Deployed by GitHub Actions, like prod. No agent touches it directly

### 4. Prod

Unchanged. Existing rollback stays the safety net if something bad slips through:
`IMAGE_TAG=<sha> docker compose -f docker-compose.prod.yml up -d`.

## The loop, and where humans touch it

| # | Step | Who | Automatic? |
|---|---|---|---|
| 1 | PMs report in WhatsApp | PMs | — |
| 2 | Triage + digest | robot | ✅ |
| 3 | **Approve an item** | developer | ❌ human |
| 4 | Write change, push branch | coder | ✅ |
| 5 | Build + deploy to toy shop | GitHub Actions | ✅ |
| 6 | "Ready, here's the link" | robot | ✅ |
| 7 | **Test the reported thing** | PM | ❌ human |
| 8 | **Merge** | developer | ❌ human |
| 9 | Build + deploy to prod | GitHub Actions | ✅ |

Three human touches. Everything between them is automatic.

Open question for step 4→5: whether the developer reads the diff before it reaches
the toy shop. Recommended **yes** at first — a glance at the PR — relaxing to
straight-to-toy-shop for small fixes once the pattern is trusted.

## Risks, and what blunts them

| Risk | Why it bites | Mitigation |
|---|---|---|
| **Consent** — two other people are in that chat | They are data subjects; they will discuss beneficiaries and named candidates. Piping their messages to an AI silently is not a technical choice | **Hard prerequisite: the PMs are told and agree.** Cleanest form is a separate number in the group that is visibly a bot |
| **WhatsApp has no legitimate API for this** | Business Cloud API covers business↔customer, not a group you're in. `whatsapp-web.js` / Baileys are reverse-engineered, breach ToS, risk a number ban, and break on client updates | Accept knowingly with a burner number, **or** move defect reporting to a form / GitHub Issues and leave WhatsApp to humans. See "escape hatch" below |
| **Robot "fixes" a non-problem** | PM complaints are often questions or prompt tuning. An agreeable agent edits code instead | Triage never writes code. Explicit `prompt tuning` class. Human approval at step 3 |
| **Missing context, not mistranslation** | Chat shorthand points at calls, screenshots and decisions the robot never saw. Humans resolve ambiguity later, in person; an agent resolves it by guessing | Low-confidence items go to a "maybe?" pile, never to a branch. A structured intake form removes most of this at the source |
| **Prompt injection with credentials attached** | Anyone typing in the group is an instruction source. A forwarded message, text inside a screenshot, a joke | Robot has no write access to anything. Worst case is a wasted branch |
| **Linked-device impersonation** | If the robot links the developer's own number, WhatsApp sees it *as* the developer and it could in principle send messages | Read-only by construction; prefer a separate number |
| **Accountability** | "Prod broke — who decided?" must have an answer | Merge is a named human action; robot keeps an audit log |
| **Quota exhaustion** | Robot burns the shared subscription window mid-workday | Batched digests; separate subscription or API for triage if needed |
| **Home machine offline** | Robot goes deaf silently | Digest model tolerates gaps; daily heartbeat makes outages visible; systemd auto-start survives power cuts; sleep disabled |
| **Staging fills the disk** | Prod MySQL loses the ability to write | Log rotation already capped (10 MB × 3); periodic `docker image prune`; disk alert |

## Rejected options, and why

- **Robot on the prod VPS.** Would need Docker to drive staging; Docker socket =
  root = prod. The boundary becomes a promise instead of a wall. Rejected on
  principle 2. Also puts a reverse-engineered WhatsApp library on the machine
  holding job-seekers' CVs.
- **A second server for staging.** Considered, then dropped — the prod box is idle
  and builds happen in CI. €5/month for no benefit.
- **Robot merges to prod.** The entire value of the design is the human at step 8.
- **Skipping the toy shop, testing in prod.** That is today's setup, and it is the
  thing being fixed.

## Build order

Phases 0–2 are worth doing on their own merits, robot or no robot. **If the
WhatsApp piece turns out too fragile or the PMs decline, phases 0–2 still deliver
most of the value** — that is the escape hatch.

- **Phase 0 — floor.** Tests and lint in CI; branch protection on `initial`;
  `main` deleted or protected. Removes "one push = prod, unreviewed."
- **Phase 1 — toy shop.** Isolated staging stack on the VPS, fake seed data,
  `staging.neoori.tech`, basic auth, test-mode Stripe, email off. PMs get the link.
- **Phase 2 — box discipline.** Branch → PR → auto-deploy to toy shop → merge to
  ship. The loop works with a human doing the triage, exactly as today.
- **Phase 3 — robot, read-only.** Home machine, digests to the developer only.
  Measure how often the triage was right before trusting it.
- **Phase 4 — revisit.** Only with weeks of evidence. Candidate first step: let the
  robot open the branch itself for the narrow class of changes it has been reliably
  right about.

## Open decisions

1. **Tell the PMs** — required before any WhatsApp reading. Also decides bot number
   vs. linked device.
2. **WhatsApp ingestion vs. structured intake.** A form kills consent, ToS,
   injection and ambiguity problems in one move; WhatsApp preserves the PMs'
   existing habits. Possible middle ground: keep chat, add a form for defects only.
3. **Home machine** — which computer, which OS. Linux is the least friction.
4. **Diff review before toy shop** — yes at first, per above.
5. **Second subscription for the robot**, or API for triage.
6. **Fake data seed** — invented profiles, or lightly scrambled real ones. Invented
   is safer and only slightly more work.

## Cost

| Item | Cost |
|---|---|
| Home machine | €0 + electricity |
| Toy shop on existing VPS | €0 |
| Robot on Claude subscription | €0 marginal (shares quota) |
| Triage via API instead | cents/month at this volume |
| Second server (rejected) | ~€5/month avoided |
