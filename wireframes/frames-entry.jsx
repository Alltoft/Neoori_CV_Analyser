// Entry flow wireframes: Landing, Form variations, Loading
// Each variant is an artboard inside one DCSection.

// ─── Landing ─────────────────────────────────────────────────────────────
const FrameLanding = () => (
  <SkChrome w={1100} h={760} label="app.neoori.fr">
    <div className="sk-paper sk-root" style={{ width:'100%', height:'100%', padding:'48px 64px', position:'relative' }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <NeooriMark size={20}/>
        <div style={{ display:'flex', gap:18, alignItems:'center' }}>
          <span className="sk-body" style={{ fontSize:13 }}>Le module</span>
          <span className="sk-body" style={{ fontSize:13 }}>Conseillers</span>
          <span className="sk-body" style={{ fontSize:13 }}>Tarifs</span>
          <span className="sk-btn">se connecter</span>
        </div>
      </div>

      <div style={{ marginTop:60, display:'grid', gridTemplateColumns:'1.1fr 0.9fr', gap:48 }}>
        <div>
          <span className="sk-tag" style={{ marginBottom:14, display:'inline-block' }}>BÊTA · ANALYSE CV</span>
          <div className="sk-h1" style={{ fontSize:54, lineHeight:1.02, marginTop:8 }}>
            Un CV lu autrement.<br/>
            <span style={{ color:'var(--sk-accent)'}}>Pour les parcours</span><br/>
            <span className="sk-strike">qu'on ne sait pas lire.</span>
          </div>
          <div className="sk-body" style={{ fontSize:16, marginTop:24, maxWidth:440, color:SK.ink2 }}>
            neoori produit une analyse stratégique de votre CV à destination
            de trois lecteurs simultanés : vous, votre conseiller, le RH.
          </div>
          <div style={{ display:'flex', gap:12, marginTop:32 }}>
            <span className="sk-btn sk-btn-cta sk-wob" style={{ padding:'12px 22px', fontSize:15 }}>analyser mon CV →</span>
            <span className="sk-btn sk-wob" style={{ padding:'12px 22px', fontSize:15 }}>voir un exemple</span>
          </div>
          <div style={{ display:'flex', gap:18, marginTop:24, alignItems:'center' }}>
            <span className="sk-small">prend ~2 min · sans compte pour la version d'essai</span>
          </div>
        </div>

        <div style={{ position:'relative' }}>
          {/* Mocked "report" stack */}
          <div className="sk-rect-2 sk-wob sk-shadow-soft" style={{ position:'absolute', right:30, top:30, width:300, height:380, background:SK.paper, padding:18, transform:'rotate(2deg)' }}>
            <span className="sk-stamp sk-stamp-accent">livrable candidat</span>
            <div className="sk-h2" style={{ marginTop:14, fontSize:22 }}>Analyse de CV</div>
            <div className="sk-small">Marion C. · Référente handicap</div>
            <div style={{ marginTop:14, display:'flex', flexDirection:'column', gap:12 }}>
              <SkLines rows={3} widths={['100%','86%','60%']}/>
              <div className="sk-line-soft"/>
              <SkLines rows={3} widths={['90%','100%','40%']}/>
              <div className="sk-line-soft"/>
              <SkLines rows={2} widths={['80%','55%']}/>
            </div>
          </div>
          <div className="sk-rect-2 sk-wob sk-shadow-soft" style={{ position:'absolute', right:0, top:0, width:300, height:380, background:SK.paper, padding:18, transform:'rotate(-3deg)' }}>
            <span className="sk-stamp">version conseiller</span>
            <div className="sk-h2" style={{ marginTop:14, fontSize:20 }}>Synthèse</div>
            <SkLines rows={5} widths={['100%','90%','70%','100%','50%']}/>
            <div style={{ marginTop:16 }} className="sk-num">§ 1 · 4 · 5</div>
          </div>
          <SkSticky rotate={4} style={{ position:'absolute', right:-20, bottom:30 }}>
            même analyse,<br/>deux exports →
          </SkSticky>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:24, marginTop:80 }}>
        {[
          ['01','Vous racontez votre cible', 'CV + offre/fiche métier + 6 champs de contexte'],
          ['02','neoori traduit', 'le langage de votre parcours vers celui du recruteur visé'],
          ['03','3 lectures, 1 document', 'pour vous · votre conseiller · un RH ou un jury'],
        ].map(([n,t,d])=>(
          <div key={n} style={{ display:'flex', flexDirection:'column', gap:6 }}>
            <span className="sk-hand" style={{ fontSize:28, color:'var(--sk-accent)' }}>{n}</span>
            <span className="sk-h3">{t}</span>
            <span className="sk-body" style={{ color:SK.ink2 }}>{d}</span>
          </div>
        ))}
      </div>

      {/* annotations */}
      <SkSticky rotate={-3} style={{ position:'absolute', left:24, bottom:24 }}>
        ton sobre &amp; pro,<br/>pas de boussoles
      </SkSticky>
    </div>
  </SkChrome>
);

// ─── Form variation A — single page ──────────────────────────────────────
const FrameFormA = () => (
  <SkChrome w={780} h={1180} label="app.neoori.fr/analyse/nouveau">
    <SkAppBar active="Analyse CV"/>
    <div className="sk-paper sk-root" style={{ padding:'28px 36px', flex:1, position:'relative' }}>
      <div style={{ display:'flex', alignItems:'baseline', justifyContent:'space-between' }}>
        <SkHeading size="h1">Nouvelle analyse</SkHeading>
        <span className="sk-tag">8 champs · ~2 min</span>
      </div>
      <div className="sk-body" style={{ color:SK.ink2, marginTop:18, maxWidth:520 }}>
        Tous les champs sont nécessaires pour déclencher l'analyse. Aucun n'est varié selon le plan choisi.
      </div>

      <div className="sk-rect-2 sk-wob" style={{ marginTop:24, padding:18, background:SK.paper }}>
        <div className="sk-h3">① votre CV</div>
        <div style={{ display:'grid', gridTemplateColumns:'1.2fr 1fr', gap:14, marginTop:12 }}>
          <SkDashed style={{ height:130, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:6, background:SK.paper2 }}>
            <span className="sk-hand" style={{ fontSize:22 }}>déposer un PDF</span>
            <span className="sk-small">glissez ici · ou cliquez</span>
            <span className="sk-tag">PDF · 10 Mo max</span>
          </SkDashed>
          <div className="sk-rect sk-wob" style={{ padding:10, minHeight:130, background:SK.paper, display:'flex', flexDirection:'column', gap:6 }}>
            <span className="sk-small">— ou copier-coller le texte —</span>
            <SkLines rows={5} widths={['100%','94%','100%','60%','30%']}/>
          </div>
        </div>
      </div>

      <div className="sk-rect-2 sk-wob" style={{ marginTop:14, padding:18, background:SK.paper }}>
        <div className="sk-h3">② cible visée</div>
        <div className="sk-small" style={{ marginTop:4 }}>offre d'emploi · fiche métier · programme de formation</div>
        <div className="sk-rect sk-wob" style={{ marginTop:10, minHeight:88, padding:10, background:SK.paper2 }}>
          <span className="sk-body" style={{ color:SK.ink3 }}>collez l'intitulé et la description du poste visé…</span>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginTop:14 }}>
        <div className="sk-rect-2 sk-wob" style={{ padding:16, background:SK.paper }}>
          <div className="sk-h3">③ qui êtes-vous</div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginTop:10 }}>
            <SkInput label="prénom" ph="Marion"/>
            <SkSelect label="tranche d'âge" ph="35 – 44"/>
            <SkInput label="localisation" ph="Paris"/>
            <SkSelect label="situation actuelle" ph="en poste"/>
          </div>
        </div>
        <div className="sk-rect-2 sk-wob" style={{ padding:16, background:SK.paper }}>
          <div className="sk-h3">④ type de mobilité</div>
          <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginTop:10 }}>
            <SkChip>évolution</SkChip>
            <SkChip on>reconversion proche</SkChip>
            <SkChip>reconversion forte</SkChip>
            <SkChip>première insertion</SkChip>
            <SkChip>retour à l'emploi</SkChip>
          </div>
          <div style={{ marginTop:14 }} className="sk-h3">⑤ notes</div>
          <div className="sk-rect sk-wob" style={{ marginTop:6, minHeight:54, padding:8, background:SK.paper2 }}>
            <span className="sk-body" style={{ color:SK.ink3 }}>RQTH, aidant, primo-arrivant, contraintes…</span>
          </div>
        </div>
      </div>

      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginTop:22 }}>
        <span className="sk-small">données stockées chiffrées · supprimables à tout moment</span>
        <div style={{ display:'flex', gap:10 }}>
          <span className="sk-btn">enregistrer brouillon</span>
          <span className="sk-btn sk-btn-cta sk-wob">lancer l'analyse →</span>
        </div>
      </div>

      <SkSticky rotate={-3} style={{ position:'absolute', right:-18, top:140 }}>
        variation A —<br/>tout sur une page.<br/><b>↑ scan rapide</b>
      </SkSticky>
    </div>
  </SkChrome>
);

// ─── Form variation B — multi-step ───────────────────────────────────────
const FrameFormB = () => {
  const steps = ['CV','cible','vous','contexte','récap'];
  return (
    <SkChrome w={780} h={760} label="app.neoori.fr/analyse/nouveau · 3/5">
      <SkAppBar active="Analyse CV"/>
      <div className="sk-paper sk-root" style={{ padding:'28px 36px', flex:1, position:'relative' }}>
        {/* stepper */}
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          {steps.map((s,i)=>(
            <React.Fragment key={s}>
              <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                <span className="sk-radio" style={{ ...(i<=2?{background:'var(--sk-accent)',borderColor:'var(--sk-accent)'}:{})}}/>
                <span className="sk-body" style={{ fontSize:12, color: i===2?SK.ink:SK.ink2, fontWeight: i===2?700:400 }}>{s}</span>
              </div>
              {i<steps.length-1 && <span className="sk-line" style={{ flex:1, height:1, opacity: i<2?1:0.3 }}/>}
            </React.Fragment>
          ))}
        </div>

        <div style={{ marginTop:24 }}>
          <SkHeading size="h1">Qui êtes-vous ?</SkHeading>
          <div className="sk-body" style={{ color:SK.ink2, marginTop:10, maxWidth:480 }}>
            Cinq éléments rapides — votre prénom, votre âge, votre localisation,
            votre situation actuelle, et le type de mobilité que vous cherchez.
          </div>
        </div>

        <div style={{ marginTop:24, display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
          <SkInput label="prénom" value="Marion"/>
          <SkSelect label="tranche d'âge" value="35 – 44 ans"/>
          <SkInput label="ville / région" value="Paris"/>
          <SkSelect label="situation actuelle" value="en poste · CDD"/>
        </div>

        <div style={{ marginTop:18 }}>
          <span className="sk-num">TYPE DE MOBILITÉ</span>
          <div style={{ display:'flex', flexWrap:'wrap', gap:8, marginTop:8 }}>
            {['évolution','reconversion proche','reconversion forte','première insertion','retour à l\'emploi'].map((t,i)=>(
              <span key={t} className="sk-pill sk-wob" style={{ background: i===1?'var(--sk-accent)':SK.paper, color:i===1?SK.paper:SK.ink, borderColor:i===1?'var(--sk-accent)':SK.ink, fontSize:13 }}>{t}</span>
            ))}
          </div>
        </div>

        <div style={{ position:'absolute', left:36, right:36, bottom:28, display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <span className="sk-btn">← retour</span>
          <span className="sk-small">étape 3 sur 5 · ↵ pour valider</span>
          <span className="sk-btn sk-btn-cta sk-wob">continuer →</span>
        </div>

        <SkSticky rotate={3} style={{ position:'absolute', right:-22, top:120 }}>
          variation B —<br/>5 étapes guidées.<br/>moins de friction
        </SkSticky>
      </div>
    </SkChrome>
  );
};

// ─── Form variation C — conversational ───────────────────────────────────
const FrameFormC = () => (
  <SkChrome w={780} h={920} label="app.neoori.fr/analyse/conversation">
    <SkAppBar active="Analyse CV"/>
    <div className="sk-paper sk-root" style={{ padding:'24px 36px', flex:1, overflow:'hidden', position:'relative' }}>
      <div style={{ display:'flex', alignItems:'baseline', gap:10 }}>
        <SkHeading size="h2">on commence ?</SkHeading>
        <span className="sk-small">— 8 questions, dans l'ordre, à votre rythme</span>
      </div>

      <div style={{ marginTop:20, display:'flex', flexDirection:'column', gap:16 }}>
        {/* bot turn */}
        <div style={{ display:'flex', gap:10, alignItems:'flex-start' }}>
          <span style={{ width:28, height:28, borderRadius:'50%', border:`1.5px solid ${SK.ink}`, display:'inline-flex', alignItems:'center', justifyContent:'center' }} className="sk-hand">n</span>
          <div className="sk-rect sk-wob" style={{ padding:'10px 14px', background:SK.paper, maxWidth:480 }}>
            <span className="sk-body">Bonjour — pour commencer, déposez votre CV ou collez-le ici. PDF accepté.</span>
          </div>
        </div>

        {/* user turn */}
        <div style={{ display:'flex', justifyContent:'flex-end' }}>
          <div className="sk-rect sk-wob" style={{ padding:'8px 12px', background:'var(--sk-accent)', color:SK.paper, maxWidth:300 }}>
            <span className="sk-body" style={{ fontFamily:'JetBrains Mono, monospace', fontSize:12 }}>📎 CV_Marion_C.pdf · 142 ko</span>
          </div>
        </div>

        {/* bot turn 2 */}
        <div style={{ display:'flex', gap:10, alignItems:'flex-start' }}>
          <span style={{ width:28, height:28, borderRadius:'50%', border:`1.5px solid ${SK.ink}` }} className="sk-hand"/>
          <div className="sk-rect sk-wob" style={{ padding:'10px 14px', background:SK.paper, maxWidth:480 }}>
            <span className="sk-body">Bien reçu. Quelle est la cible visée — une offre, une fiche métier, ou une formation ?</span>
          </div>
        </div>

        <div style={{ display:'flex', justifyContent:'flex-end' }}>
          <div className="sk-rect sk-wob" style={{ padding:'8px 12px', background:'var(--sk-accent)', color:SK.paper, maxWidth:380 }}>
            <span className="sk-body">Référente handicap en entreprise — ETI ou groupe, région parisienne</span>
          </div>
        </div>

        <div style={{ display:'flex', gap:10, alignItems:'flex-start' }}>
          <span style={{ width:28, height:28, borderRadius:'50%', border:`1.5px solid ${SK.ink}` }} className="sk-hand"/>
          <div className="sk-rect sk-wob" style={{ padding:'10px 14px', background:SK.paper, maxWidth:480 }}>
            <span className="sk-body">Compris. Votre prénom ?</span>
          </div>
        </div>
      </div>

      <div style={{ position:'absolute', left:36, right:36, bottom:24 }}>
        <div className="sk-rect sk-wob" style={{ padding:'10px 14px', background:SK.paper, display:'flex', alignItems:'center', gap:10 }}>
          <span className="sk-body" style={{ color:SK.ink3, flex:1 }}>tapez votre prénom…</span>
          <span className="sk-btn sk-btn-cta" style={{ padding:'4px 12px', fontSize:12 }}>envoyer ↵</span>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginTop:8 }}>
          <span className="sk-num">3 / 8</span>
          <div style={{ flex:1, height:3, background:SK.ink3, borderRadius:2, overflow:'hidden' }}>
            <div style={{ width:'37%', height:'100%', background:'var(--sk-accent)' }}/>
          </div>
          <span className="sk-small">passer →</span>
        </div>
      </div>

      <SkSticky rotate={-2} style={{ position:'absolute', right:-18, top:80 }}>
        variation C —<br/>conversationnel.<br/><b>+ chaleureux</b>
      </SkSticky>
    </div>
  </SkChrome>
);

// ─── Form variation D — split (sidebar context + canvas) ─────────────────
const FrameFormD = () => (
  <SkChrome w={1100} h={760} label="app.neoori.fr/analyse/atelier">
    <SkAppBar active="Analyse CV"/>
    <div className="sk-paper sk-root" style={{ flex:1, display:'grid', gridTemplateColumns:'260px 1fr', overflow:'hidden' }}>
      <div style={{ padding:'22px 18px', borderRight:`1px solid ${SK.ink3}`, background:SK.paper2 }}>
        <div className="sk-h3">vos infos</div>
        <div style={{ marginTop:14, display:'flex', flexDirection:'column', gap:10 }}>
          {[
            ['prénom','Marion','on'],
            ['âge','35 – 44 ans','on'],
            ['ville','Paris','on'],
            ['situation','en poste · CDD','on'],
            ['mobilité','reconversion proche','on'],
            ['notes','RQTH éligible','half'],
          ].map(([k,v,st])=>(
            <div key={k} style={{ display:'flex', alignItems:'center', gap:8 }}>
              <span className={`sk-check ${st==='on'?'on':''}`}/>
              <span className="sk-small" style={{ width:60 }}>{k}</span>
              <span className="sk-body" style={{ fontSize:13, color: st==='on'?SK.ink:SK.ink2 }}>{v}</span>
            </div>
          ))}
        </div>
        <div className="sk-line-soft" style={{ margin:'18px 0' }}/>
        <div className="sk-h3">documents</div>
        <div style={{ marginTop:10, display:'flex', flexDirection:'column', gap:8 }}>
          <div className="sk-rect-thin sk-wob" style={{ padding:8 }}>
            <span className="sk-mono" style={{ fontSize:11 }}>📄 CV_Marion.pdf</span>
          </div>
          <div className="sk-rect-thin sk-wob" style={{ padding:8 }}>
            <span className="sk-mono" style={{ fontSize:11 }}>📄 fiche_poste.txt</span>
          </div>
        </div>
        <div style={{ marginTop:'auto', paddingTop:18 }}>
          <span className="sk-btn sk-btn-cta sk-wob" style={{ width:'100%', justifyContent:'center', display:'flex' }}>tout est prêt — lancer →</span>
        </div>
      </div>

      <div style={{ padding:'24px 36px', overflow:'hidden', position:'relative' }}>
        <SkHeading size="h2">Cible visée</SkHeading>
        <span className="sk-small">collez l'offre, la fiche métier, ou décrivez le poste</span>
        <div className="sk-rect-2 sk-wob" style={{ marginTop:14, padding:16, background:SK.paper, height:300 }}>
          <div className="sk-body" style={{ lineHeight:1.5 }}>
            <b>Référent·e handicap</b> — Groupe industriel, 4 200 salariés. Structurer la politique handicap, piloter l'OETH, animer le réseau des référents internes…
          </div>
          <div style={{ marginTop:10 }}>
            <SkLines rows={5} widths={['100%','96%','100%','88%','60%']}/>
          </div>
        </div>

        <div style={{ marginTop:16, display:'flex', gap:14 }}>
          <div className="sk-rect-2 sk-wob" style={{ flex:1, padding:14, background:SK.paper }}>
            <div className="sk-h3">cadrage sectoriel auto-détecté</div>
            <div style={{ marginTop:8, display:'flex', flexWrap:'wrap', gap:6 }}>
              <SkChip on>industrie / BTP</SkChip>
              <SkChip dim>ESS / social</SkChip>
              <SkChip dim>secteur public</SkChip>
            </div>
            <span className="sk-small" style={{ marginTop:8, display:'block' }}>le lexique du livrable s'adapte automatiquement</span>
          </div>
          <div className="sk-rect-2 sk-wob" style={{ flex:1, padding:14, background:SK.paper }}>
            <div className="sk-h3">notes spécifiques</div>
            <div className="sk-body" style={{ marginTop:6, fontSize:13 }}>
              RQTH éligible · mémoire M2 sur la neurodiversité · 12 mois de mentorat bénévole
            </div>
          </div>
        </div>

        <SkSticky rotate={-2} style={{ position:'absolute', right:18, bottom:18 }}>
          variation D —<br/>atelier · contexte<br/>toujours visible
        </SkSticky>
      </div>
    </div>
  </SkChrome>
);

// ─── Loading / generation state ──────────────────────────────────────────
const FrameLoading = () => (
  <SkChrome w={780} h={720} label="app.neoori.fr/analyse/en-cours">
    <SkAppBar active="Analyse CV"/>
    <div className="sk-paper sk-root" style={{ padding:'40px 48px', flex:1, position:'relative' }}>
      <div style={{ textAlign:'center' }}>
        <span className="sk-tag">EN COURS · ~40 SEC</span>
        <div className="sk-h1" style={{ marginTop:14, fontSize:38 }}>neoori vous lit.</div>
        <span className="sk-small">prompt système v1.3 · claude-sonnet-4 · max 4 000 tokens</span>
      </div>

      <div style={{ marginTop:36, maxWidth:520, margin:'36px auto 0' }}>
        {[
          ['lecture du CV','done'],
          ['cadrage sectoriel · cible identifiée','done'],
          ['lecture stratégique du parcours','active'],
          ['forces · compétences transférables','wait'],
          ['angles morts · préconisations','wait'],
          ['proposition de CV retravaillé','wait-locked'],
        ].map(([t,st])=>(
          <div key={t} style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 0', borderBottom:`1px dashed ${SK.ink3}` }}>
            <span style={{
              width:18, height:18, borderRadius:'50%',
              border:`1.5px solid ${st==='wait-locked'?SK.ink3:SK.ink}`,
              background: st==='done'?'var(--sk-accent)': st==='active'?SK.paper:SK.paper,
              display:'inline-flex', alignItems:'center', justifyContent:'center', fontSize:11,
              color: st==='done'?SK.paper:SK.ink,
            }}>{st==='done'?'✓': st==='active'?'•':''}</span>
            <span className="sk-body" style={{ flex:1, color: st==='wait-locked'?SK.ink3:SK.ink, fontStyle: st==='active'?'italic':'normal' }}>{t}</span>
            {st==='active' && <span className="sk-mono" style={{ fontSize:10, color:SK.ink2 }}>1.8 s</span>}
            {st==='wait-locked' && <span className="sk-tag">payant</span>}
          </div>
        ))}
      </div>

      <div style={{ marginTop:30, maxWidth:520, margin:'30px auto 0' }}>
        <div style={{ display:'flex', justifyContent:'space-between' }}>
          <span className="sk-num">PROGRESSION</span>
          <span className="sk-num">42%</span>
        </div>
        <div style={{ height:8, background:SK.paper2, border:`1.5px solid ${SK.ink}`, borderRadius:2, marginTop:6, overflow:'hidden' }}>
          <div style={{ width:'42%', height:'100%', background:'var(--sk-accent)' }}/>
        </div>
        <div className="sk-small" style={{ marginTop:10, textAlign:'center' }}>vous pouvez fermer cet onglet — on vous prévient par e-mail</div>
      </div>

      <SkSticky rotate={3} style={{ position:'absolute', right:24, top:120 }}>
        montrer ce qui se<br/>passe — pas un<br/>spinner anonyme.
      </SkSticky>
    </div>
  </SkChrome>
);

Object.assign(window, { FrameLanding, FrameFormA, FrameFormB, FrameFormC, FrameFormD, FrameLoading });
