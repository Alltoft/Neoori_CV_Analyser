// Deliverable wireframes: 3 layouts for candidate version, counselor variant, paywall

// Section data for the analysis (Sections 1–9)
const SECTIONS = [
  ['1','Lecture stratégique du parcours','le mouvement, la cohérence, ce que ça raconte'],
  ['2','Forces du profil pour la cible','5 forces, chacune avec sa condition d\'expression'],
  ['3','Compétences transférables','tags exploitables sur CV / LinkedIn'],
  ['4','Angles morts du CV actuel','ce qui passe à côté d\'un RH'],
  ['5','Préconisations terrain','réseau, formations, portfolio, CEP'],
  ['6','Exemple de réécriture','une expérience traduite vers le langage cible'],
  ['7','Synthèse','le mouvement à conduire'],
  ['8','Pistes d\'évolution','3 pistes au-delà de la cible initiale'],
  ['9','Proposition de CV retravaillé','le document, prêt à adapter'],
];

// ─── Deliverable A — long scroll, document-feel ──────────────────────────
const FrameDeliverableA = () => (
  <SkChrome w={900} h={1500} label="app.neoori.fr/analyse/marion-c">
    <SkAppBar active="Analyse CV"/>
    <div className="sk-plain sk-root" style={{ flex:1, overflow:'hidden', position:'relative' }}>
      {/* sticky header */}
      <div style={{ padding:'18px 44px', borderBottom:`1px solid ${SK.ink3}`, display:'flex', justifyContent:'space-between', alignItems:'center', background:SK.paper }}>
        <div>
          <span className="sk-tag">livrable candidat · v1.3</span>
          <div className="sk-h2" style={{ marginTop:4 }}>Marion C. → Référente handicap entreprise</div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <span className="sk-btn">↓ PDF</span>
          <span className="sk-btn">↗ partager</span>
          <span className="sk-btn sk-wob" style={{ background:SK.paper2 }}>version conseiller</span>
        </div>
      </div>

      <div style={{ padding:'32px 44px', position:'relative' }}>
        {/* avant-propos */}
        <div className="sk-rect sk-wob" style={{ padding:16, background:SK.paper2, marginBottom:24 }}>
          <span className="sk-h3">avant-propos</span>
          <div className="sk-body" style={{ marginTop:6, color:SK.ink2 }}>
            Cette analyse a été produite avec la version bêta de neoori, outil d'analyse de CV pensé pour les reconversions, les profils atypiques et les expériences que les autres outils ne savent pas lire.
          </div>
        </div>

        <SkSection n="1" title="Lecture stratégique du parcours"/>
        <div className="sk-body" style={{ marginTop:10, lineHeight:1.5 }}>
          Vous venez du conseil et de la communication, et vous avez basculé en septembre 2024 vers l'accompagnement handicap-emploi en intégrant Cap Emploi 75. Vous visez désormais un poste de référente handicap côté entreprise — un passage du côté prestataire au côté employeur.
        </div>
        <SkLines rows={3} widths={['100%','94%','60%']}/>

        <div style={{ marginTop:28 }}><SkSection n="2" title="Forces du profil pour la cible"/></div>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginTop:14 }}>
          {[
            ['Connaissance opérationnelle de l\'écosystème','RQTH · DOETH · Agefiph · FIPHFP — au-delà de la théorie'],
            ['Pédagogie interne','+20 actions de sensibilisation conçues et animées'],
            ['Communication appliquée au RH','agence 360° — savoir produire des supports professionnels'],
            ['Transformer un besoin en projet','pilotage de A à Z, cadre flou compris'],
          ].map(([t,sub])=>(
            <div key={t} className="sk-rect sk-wob" style={{ padding:12, background:SK.paper }}>
              <div className="sk-body" style={{ fontWeight:700 }}>{t}</div>
              <div className="sk-small" style={{ marginTop:4 }}>{sub}</div>
              <div className="sk-num" style={{ marginTop:8, color:'var(--sk-accent)' }}>→ pour la cible : …</div>
            </div>
          ))}
        </div>

        <div style={{ marginTop:28 }}><SkSection n="3" title="Compétences transférables"/></div>
        <div className="sk-small" style={{ marginTop:6 }}>tags directement exploitables sur CV ou profil LinkedIn</div>
        <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginTop:12 }}>
          {['politique handicap entreprise','RQTH','DOETH','Agefiph','FIPHFP','aménagement de poste','recrutement inclusif','sensibilisation managers','conduite de projet RH','relations partenaires emploi-formation','marque employeur inclusive','communication interne','accompagnement individuel','pilotage budgétaire','réseau partenarial'].map(t=>(
            <SkChip key={t}>{t}</SkChip>
          ))}
        </div>

        <div style={{ marginTop:28 }}><SkSection n="4" title="Angles morts du CV actuel"/></div>
        <div style={{ marginTop:12, display:'flex', flexDirection:'column', gap:10 }}>
          {[
            ['le titre reste dans le langage du prestataire','« Chargée de mission insertion handicap » → « Référente handicap & communication RH »'],
            ['l\'accroche peut être plus directionnelle','renforcer la dimension stratégique : structuration, pilotage, indicateurs, conformité'],
            ['l\'expérience comm 360° est sous-traduite','3 ans d\'agence à traduire en valeur RH transposable'],
            ['les preuves d\'impact sont dispersées','combien d\'aménagements négociés ? combien d\'embauches sécurisées ?'],
          ].map(([t,d],i)=>(
            <div key={i} style={{ display:'flex', gap:12, alignItems:'flex-start' }}>
              <span className="sk-hand" style={{ fontSize:24, color:'var(--sk-accent)', minWidth:30 }}>{i+1}.</span>
              <div>
                <div className="sk-body" style={{ fontWeight:700 }}>{t}</div>
                <div className="sk-small" style={{ marginTop:2 }}>{d}</div>
              </div>
            </div>
          ))}
        </div>

        {/* paywall fade — sections 5-9 locked in free */}
        <div className="sk-locked" style={{ marginTop:36, position:'relative' }}>
          <div className="sk-lock-badge sk-stamp sk-stamp-accent">plan payant</div>
          <SkSection n="5" title="Préconisations terrain" locked/>
          <div className="sk-body" style={{ marginTop:10 }}>Entretien réseau avec 2-3 référents handicap en poste. Formation courte sur la fonction…</div>
          <SkLines rows={2} widths={['90%','60%']}/>
          <div style={{ marginTop:24 }}><SkSection n="6" title="Exemple de réécriture" locked/></div>
          <SkLines rows={3} widths={['100%','86%','40%']}/>
          <div style={{ marginTop:24 }}><SkSection n="7" title="Synthèse" locked/></div>
          <SkLines rows={2} widths={['100%','64%']}/>
        </div>

        <div className="sk-rect-2 sk-wob" style={{ marginTop:24, padding:18, background:'var(--sk-accent)', color:SK.paper, display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div>
            <div className="sk-hand" style={{ fontSize:24 }}>débloquez les 5 sections restantes</div>
            <div className="sk-small" style={{ color:'rgba(255,255,255,.85)' }}>préconisations · réécriture · synthèse · pistes d'évolution · CV retravaillé</div>
          </div>
          <span className="sk-btn" style={{ background:SK.paper, color:SK.ink, borderColor:SK.paper }}>passer en payant — 9 € →</span>
        </div>

        <SkSticky rotate={-2} style={{ position:'absolute', right:-22, top:300 }}>
          variante A —<br/>document long,<br/>scroll continu.
        </SkSticky>
      </div>
    </div>
  </SkChrome>
);

// ─── Deliverable B — sidebar nav + content ───────────────────────────────
const FrameDeliverableB = () => (
  <SkChrome w={1100} h={780} label="app.neoori.fr/analyse/marion-c">
    <SkAppBar active="Analyse CV"/>
    <div className="sk-plain sk-root" style={{ flex:1, display:'grid', gridTemplateColumns:'260px 1fr', overflow:'hidden' }}>
      {/* sidebar */}
      <div style={{ padding:'22px 16px', borderRight:`1px solid ${SK.ink3}`, background:SK.paper2 }}>
        <div className="sk-h3">l'analyse</div>
        <div className="sk-small" style={{ marginTop:2 }}>Marion C. · 9 sections</div>
        <div style={{ marginTop:14, display:'flex', flexDirection:'column' }}>
          {SECTIONS.map(([n,t,_],i)=>{
            const locked = i>=4;
            const active = i===1;
            return (
              <div key={n} style={{
                display:'flex', alignItems:'baseline', gap:8, padding:'6px 6px',
                borderLeft: active?`3px solid var(--sk-accent)`:'3px solid transparent',
                background: active?SK.paper:'transparent',
                marginLeft:-6, paddingLeft:9,
              }}>
                <span className="sk-num" style={{ minWidth:14 }}>{n}</span>
                <span className="sk-body" style={{ fontSize:13, flex:1, color: locked?SK.ink3:active?SK.ink:SK.ink2, fontWeight: active?700:400 }}>{t}</span>
                {locked && <span style={{ fontSize:11, color:SK.ink3 }}>🔒</span>}
              </div>
            );
          })}
        </div>
        <div className="sk-line-soft" style={{ margin:'14px 0' }}/>
        <div className="sk-h3">actions</div>
        <div style={{ marginTop:8, display:'flex', flexDirection:'column', gap:6 }}>
          <span className="sk-btn sk-wob" style={{ justifyContent:'flex-start', fontSize:12 }}>↓ télécharger PDF</span>
          <span className="sk-btn sk-wob" style={{ justifyContent:'flex-start', fontSize:12 }}>↗ partager un lien</span>
          <span className="sk-btn sk-wob" style={{ justifyContent:'flex-start', fontSize:12 }}>👤 envoyer au conseiller</span>
          <span className="sk-btn sk-wob" style={{ justifyContent:'flex-start', fontSize:12 }}>↻ refaire l'analyse</span>
        </div>
      </div>

      {/* content */}
      <div style={{ padding:'24px 36px', overflow:'hidden', position:'relative' }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline' }}>
          <SkSection n="2" title="Forces du profil pour la cible"/>
          <div style={{ display:'flex', gap:8 }}>
            <span className="sk-tag">← § 1</span>
            <span className="sk-tag">§ 3 →</span>
          </div>
        </div>

        <div className="sk-body" style={{ marginTop:16, lineHeight:1.5 }}>
          Quatre forces ressortent du parcours, chacune nommée avec sa condition d'expression — c'est ce qui sépare une qualité affichée d'une compétence opérante.
        </div>

        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginTop:18 }}>
          {[
            ['Connaissance de l\'écosystème handicap-emploi','RQTH, DOETH, Agefiph, FIPHFP, aménagements','contextes où l\'entreprise dialogue avec des prestataires externes','structurer la relation entreprise / écosystème'],
            ['Pédagogie interne · conduite du changement','+20 actions de sensibilisation','environnements où il faut bouger les représentations sans braquer','former managers et équipes recrutement'],
            ['Communication appliquée à un sujet RH','agence 360° pendant 3 ans','rare chez les référents handicap','valoriser la politique handicap auprès des salariés et de la marque employeur'],
            ['Transformer un besoin en projet','pilotage de A à Z, du cadrage à l\'évaluation','quand il faut structurer une démarche en cadre flou','déployer une politique handicap — projet à construire, pas exécution'],
          ].map(([t,fact,cond,impact])=>(
            <div key={t} className="sk-rect sk-wob" style={{ padding:14, background:SK.paper }}>
              <div className="sk-body" style={{ fontWeight:700 }}>{t}</div>
              <div className="sk-num" style={{ marginTop:8 }}>FAIT</div>
              <div className="sk-small">{fact}</div>
              <div className="sk-num" style={{ marginTop:6 }}>CONDITION D'EXPRESSION</div>
              <div className="sk-small">{cond}</div>
              <div className="sk-num" style={{ marginTop:6, color:'var(--sk-accent)' }}>POUR LA CIBLE</div>
              <div className="sk-small" style={{ color:SK.ink }}>{impact}</div>
            </div>
          ))}
        </div>

        <SkSticky rotate={3} style={{ position:'absolute', right:18, bottom:18 }}>
          variante B —<br/>nav lat., contenu<br/>en focus.
        </SkSticky>
      </div>
    </div>
  </SkChrome>
);

// ─── Deliverable C — document/rapport (A4-feel, page numbers) ────────────
const FrameDeliverableC = () => (
  <SkChrome w={780} h={1100} label="app.neoori.fr/analyse/marion-c/rapport">
    <SkAppBar active="Analyse CV"/>
    <div style={{ background:SK.paper2, padding:'24px 0', flex:1, overflow:'hidden', position:'relative' }}>
      <div style={{ display:'flex', justifyContent:'center', gap:8, marginBottom:18 }}>
        <span className="sk-btn">vue rapport</span>
        <span className="sk-btn sk-wob" style={{ background:SK.paper2 }}>vue navigable</span>
        <span className="sk-btn sk-wob" style={{ background:SK.paper2 }}>vue conseiller</span>
      </div>

      <div className="sk-plain sk-root sk-shadow-soft" style={{ width:560, margin:'0 auto', padding:'46px 54px', position:'relative', minHeight:900, background:SK.paper }}>
        <div className="sk-corner-fold"/>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-end', borderBottom:`1.5px solid ${SK.ink}`, paddingBottom:8 }}>
          <div>
            <div className="sk-mono" style={{ fontSize:10, letterSpacing:'.06em' }}>NEOORI · ANALYSE DE CV</div>
            <div className="sk-h2" style={{ marginTop:4, fontSize:22 }}>Marion C.</div>
            <div className="sk-small">Cible : Référente handicap entreprise · Mai 2026</div>
          </div>
          <NeooriMark size={14}/>
        </div>

        <div style={{ marginTop:20 }}>
          <span className="sk-stamp sk-stamp-accent">§ 1</span>
          <span className="sk-h2" style={{ fontSize:18, marginLeft:10 }}>Lecture stratégique</span>
        </div>
        <div className="sk-body" style={{ marginTop:10, fontSize:13, lineHeight:1.6 }}>
          Vous venez du conseil et de la communication, et vous avez basculé en septembre 2024 vers l'accompagnement handicap-emploi en intégrant Cap Emploi 75. C'est le mouvement classique d'une professionnelle qui veut passer de l'accompagnement individuel à l'impact systémique sur les pratiques de recrutement.
        </div>
        <SkLines rows={3} widths={['100%','94%','70%']}/>

        <div style={{ marginTop:18 }}>
          <span className="sk-stamp sk-stamp-accent">§ 2</span>
          <span className="sk-h2" style={{ fontSize:18, marginLeft:10 }}>Forces du profil</span>
        </div>
        <div style={{ marginTop:10, display:'flex', flexDirection:'column', gap:10 }}>
          {[
            ['Connaissance opérationnelle de l\'écosystème handicap-emploi'],
            ['Pédagogie interne · conduite du changement'],
            ['Communication appliquée à un sujet RH'],
            ['Capacité à transformer un besoin en projet'],
          ].map(([t],i)=>(
            <div key={i} style={{ display:'flex', gap:10 }}>
              <span className="sk-hand" style={{ fontSize:18, minWidth:18 }}>—</span>
              <div className="sk-body" style={{ fontSize:13 }}>{t}</div>
            </div>
          ))}
        </div>

        <div style={{ marginTop:18 }}>
          <span className="sk-stamp">§ 3</span>
          <span className="sk-h2" style={{ fontSize:18, marginLeft:10 }}>Compétences transférables</span>
        </div>
        <div className="sk-body" style={{ marginTop:8, fontSize:12, lineHeight:1.6, color:SK.ink2 }}>
          politique handicap entreprise · RQTH · DOETH · Agefiph · FIPHFP · aménagement de poste · recrutement inclusif · sensibilisation managers · conduite de projet RH · relations partenaires emploi-formation · marque employeur inclusive…
        </div>

        <div style={{ marginTop:18 }}>
          <span className="sk-stamp">§ 4</span>
          <span className="sk-h2" style={{ fontSize:18, marginLeft:10 }}>Angles morts</span>
        </div>
        <SkLines rows={4} widths={['100%','92%','100%','58%']}/>

        <div style={{ position:'absolute', left:54, right:54, bottom:18, display:'flex', justifyContent:'space-between' }}>
          <span className="sk-mono" style={{ fontSize:10, color:SK.ink2 }}>neoori · v1.3 · confidentiel</span>
          <span className="sk-mono" style={{ fontSize:10, color:SK.ink2 }}>1 / 6</span>
        </div>
      </div>

      <SkSticky rotate={4} style={{ position:'absolute', right:24, top:120 }}>
        variante C —<br/>vue « rapport »<br/>imprimable A4
      </SkSticky>
    </div>
  </SkChrome>
);

// ─── Counselor view (sections 1, 4, 5 only) ──────────────────────────────
const FrameCounselor = () => (
  <SkChrome w={900} h={1100} label="app.neoori.fr/analyse/marion-c?audience=conseiller">
    <SkAppBar active="Analyse CV"/>
    <div className="sk-plain sk-root" style={{ flex:1, overflow:'hidden', position:'relative' }}>
      <div style={{ padding:'18px 44px', borderBottom:`1px solid ${SK.ink3}`, display:'flex', justifyContent:'space-between', alignItems:'center', background:SK.paper }}>
        <div>
          <span className="sk-tag" style={{ background:'var(--sk-accent)', color:SK.paper, borderColor:'var(--sk-accent)' }}>VERSION CONSEILLER</span>
          <div className="sk-h2" style={{ marginTop:4 }}>Préparer un entretien · Marion C.</div>
          <span className="sk-small">3 sections — 5 min de lecture · à destination Cap Emploi, Mission Locale, France Travail, CEP</span>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <span className="sk-btn">↓ PDF synthèse</span>
          <span className="sk-btn sk-wob" style={{ background:SK.paper2 }}>vue candidat</span>
        </div>
      </div>

      <div style={{ padding:'28px 44px', position:'relative' }}>
        {/* top key fact box */}
        <div className="sk-rect-2 sk-wob" style={{ padding:16, background:SK.paper2, display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:14 }}>
          {[
            ['Cible visée','Référente handicap entreprise'],
            ['Mobilité','reconversion proche'],
            ['Posture actuelle','Cap Emploi 75 · CDD'],
            ['Points sensibles','RQTH éligible'],
          ].map(([k,v])=>(
            <div key={k}>
              <div className="sk-num">{k}</div>
              <div className="sk-body" style={{ marginTop:2, fontSize:13 }}>{v}</div>
            </div>
          ))}
        </div>

        <div style={{ marginTop:24 }}><SkSection n="1" title="Lecture stratégique" sub="le mouvement à conduire"/></div>
        <div className="sk-body" style={{ marginTop:10 }}>
          Passage du côté prestataire au côté employeur. Écart sectoriel faible — elle reste dans l'écosystème handicap-emploi mais change de positionnement. Mouvement classique d'une professionnelle qui veut passer de l'accompagnement individuel à l'impact systémique.
        </div>

        <div style={{ marginTop:24 }}><SkSection n="4" title="Angles morts du CV actuel"/></div>
        <div className="sk-body" style={{ marginTop:6, color:SK.ink2, fontSize:13 }}>à pointer en entretien — l'écart de langage entre prestataire et entreprise</div>
        <div style={{ marginTop:12, display:'flex', flexDirection:'column', gap:8 }}>
          {[
            ['titre CV','reste dans le vocabulaire Cap Emploi'],
            ['accroche','militante plutôt que stratégique'],
            ['expérience agence','sous-traduite vers RH'],
            ['preuves d\'impact','dispersées · pas chiffrées'],
          ].map(([k,v])=>(
            <div key={k} style={{ display:'grid', gridTemplateColumns:'140px 1fr', gap:14, padding:'6px 0', borderBottom:`1px dashed ${SK.ink3}` }}>
              <span className="sk-h3">{k}</span>
              <span className="sk-body" style={{ fontSize:13 }}>{v}</span>
            </div>
          ))}
        </div>

        <div style={{ marginTop:24 }}><SkSection n="5" title="Préconisations terrain" sub="à proposer dans le plan d'action"/></div>
        <div style={{ marginTop:12, display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
          {[
            ['entretiens réseau','2-3 référents handicap en poste · LinkedIn, club Être'],
            ['formation Agefiph','Référent handicap entreprise · quelques jours'],
            ['portfolio ciblé','2-3 réalisations relues sous angle ROI employeur'],
            ['CEP externe','prise de recul, plan d\'action 3-6 mois'],
          ].map(([k,v])=>(
            <div key={k} className="sk-rect sk-wob" style={{ padding:12, background:SK.paper }}>
              <div className="sk-h3">{k}</div>
              <div className="sk-small" style={{ marginTop:4 }}>{v}</div>
              <div style={{ marginTop:8, display:'flex', gap:6 }}>
                <span className="sk-check"/>
                <span className="sk-body" style={{ fontSize:12, color:SK.ink2 }}>à valider avec Marion</span>
              </div>
            </div>
          ))}
        </div>

        <div className="sk-rect-d sk-wob" style={{ marginTop:24, padding:14, background:SK.paper2 }}>
          <div className="sk-h3">notes pour l'entretien</div>
          <div className="sk-small" style={{ marginTop:4, fontStyle:'italic' }}>champ libre · sauvegardé sur votre espace conseiller — non partagé avec le candidat</div>
          <div style={{ height:80, marginTop:8, background:`repeating-linear-gradient(transparent 0 19px, ${SK.ink3} 19px 20px)` }}/>
        </div>

        <SkSticky rotate={-3} style={{ position:'absolute', right:-18, top:160 }}>
          même objet d'analyse —<br/>export différent.<br/>pas de re-génération.
        </SkSticky>
      </div>
    </div>
  </SkChrome>
);

// ─── Paywall — comparing two treatments side by side ─────────────────────
const FramePaywall = () => (
  <SkChrome w={1100} h={760} label="app.neoori.fr/analyse/marion-c/débloquer">
    <SkAppBar active="Analyse CV"/>
    <div className="sk-paper sk-root" style={{ padding:'32px 44px', flex:1, position:'relative' }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline' }}>
        <div>
          <SkHeading size="h1">Débloquer le livrable complet</SkHeading>
          <div className="sk-body" style={{ color:SK.ink2, marginTop:6 }}>Vous avez vu les 4 premières sections. Les 5 suivantes sont la partie actionnable.</div>
        </div>
        <span className="sk-stamp">v1.3 · bêta</span>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginTop:28 }}>
        <div className="sk-rect-2 sk-wob" style={{ padding:24, background:SK.paper }}>
          <div className="sk-h3">gratuit</div>
          <div className="sk-h1" style={{ fontSize:42, marginTop:8 }}>0 €</div>
          <div className="sk-small">version d'essai · 1 analyse</div>
          <div className="sk-line-soft" style={{ margin:'14px 0' }}/>
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {SECTIONS.slice(0,4).map(([n,t])=>(
              <div key={n} style={{ display:'flex', gap:8 }}><span className="sk-check on"/><span className="sk-body" style={{ fontSize:13 }}>§ {n} · {t}</span></div>
            ))}
            {SECTIONS.slice(4).map(([n,t])=>(
              <div key={n} style={{ display:'flex', gap:8 }}><span className="sk-check"/><span className="sk-body sk-strike" style={{ fontSize:13, color:SK.ink3 }}>§ {n} · {t}</span></div>
            ))}
          </div>
        </div>

        <div className="sk-rect-2 sk-wob" style={{ padding:24, background:'var(--sk-accent)', color:SK.paper, position:'relative' }}>
          <div className="sk-stamp" style={{ background:SK.paper, color:SK.ink, borderColor:SK.paper, position:'absolute', top:-12, right:24 }}>recommandé</div>
          <div className="sk-h3" style={{ color:SK.paper }}>complet</div>
          <div style={{ display:'flex', alignItems:'baseline', gap:8 }}>
            <div className="sk-h1" style={{ fontSize:42, marginTop:8, color:SK.paper }}>9 €</div>
            <span className="sk-small" style={{ color:'rgba(255,255,255,.85)' }}>une fois · sans abonnement</span>
          </div>
          <div className="sk-small" style={{ color:'rgba(255,255,255,.85)' }}>livrable 9 sections + CV retravaillé + export conseiller</div>
          <div style={{ height:1, background:'rgba(255,255,255,.4)', margin:'14px 0' }}/>
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {SECTIONS.map(([n,t])=>(
              <div key={n} style={{ display:'flex', gap:8 }}>
                <span className="sk-check on" style={{ borderColor:SK.paper, background:'transparent' }}/>
                <span className="sk-body" style={{ fontSize:13 }}>§ {n} · {t}</span>
              </div>
            ))}
          </div>
          <div className="sk-btn" style={{ width:'100%', justifyContent:'center', marginTop:18, background:SK.paper, color:'var(--sk-accent)', borderColor:SK.paper, fontWeight:700 }}>débloquer pour 9 € →</div>
          <div className="sk-small" style={{ color:'rgba(255,255,255,.85)', marginTop:8, textAlign:'center' }}>code conseiller — gratuit pour les bénéficiaires Cap Emploi / France Travail</div>
        </div>
      </div>

      <div className="sk-rect sk-wob" style={{ marginTop:22, padding:14, background:SK.paper2, display:'flex', alignItems:'center', gap:14 }}>
        <span className="sk-hand" style={{ fontSize:22 }}>déjà un code conseiller ?</span>
        <div className="sk-rect" style={{ padding:'6px 12px', background:SK.paper, flex:1 }}>
          <span className="sk-mono" style={{ fontSize:13, color:SK.ink3 }}>CAP-2026-XXXX-XXXX</span>
        </div>
        <span className="sk-btn">activer</span>
      </div>

      <SkSticky rotate={-3} style={{ position:'absolute', right:24, bottom:24 }}>
        ne PAS flouter agressivement —<br/>les 4 sections gratuites sont déjà<br/>très utiles. payer = aller plus loin.
      </SkSticky>
    </div>
  </SkChrome>
);

Object.assign(window, { FrameDeliverableA, FrameDeliverableB, FrameDeliverableC, FrameCounselor, FramePaywall, SECTIONS });
