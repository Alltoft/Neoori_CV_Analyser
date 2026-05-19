// Admin dashboard + user history wireframes

// ─── Admin: overview + prompt editor + logs ──────────────────────────────
const FrameAdmin = () => (
  <SkChrome w={1280} h={820} label="admin.neoori.fr/dashboard" >
    <div style={{ display:'flex', alignItems:'center', gap:14, padding:'10px 18px', borderBottom:`1px solid ${SK.ink3}`, background:SK.paper2 }}>
      <NeooriMark size={14}/>
      <span className="sk-stamp">admin</span>
      <div style={{ display:'flex', gap:14, marginLeft:18 }}>
        {['vue d\'ensemble','prompts','analyses','utilisateurs','conseillers','coûts API'].map((t,i)=>(
          <span key={t} className="sk-body" style={{ fontSize:13, color: i===0?SK.ink:SK.ink2, borderBottom: i===0?`1.5px solid var(--sk-accent)`:'none', paddingBottom:2 }}>{t}</span>
        ))}
      </div>
      <span style={{ marginLeft:'auto' }} className="sk-small">déconnexion</span>
    </div>

    <div className="sk-plain sk-root" style={{ flex:1, padding:'22px 28px', overflow:'hidden', position:'relative' }}>
      {/* KPI strip */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:14 }}>
        {[
          ['analyses générées','142','+18 cette semaine'],
          ['taux de succès','94 %','8 erreurs · 1 timeout'],
          ['tokens consommés','1.8 M','≈ 64 € · mai'],
          ['conversion → payant','27 %','38 / 142'],
          ['prompt actif','v1.3','depuis 4 j'],
        ].map(([k,v,d],i)=>(
          <div key={k} className="sk-rect sk-wob" style={{ padding:12, background:SK.paper }}>
            <span className="sk-num">{k}</span>
            <div className="sk-h1" style={{ fontSize:28, marginTop:4, color: i===4?'var(--sk-accent)':SK.ink }}>{v}</div>
            <span className="sk-small">{d}</span>
          </div>
        ))}
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1.4fr 1fr', gap:18, marginTop:18 }}>
        {/* prompt editor */}
        <div className="sk-rect-2 sk-wob" style={{ padding:16, background:SK.paper }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline' }}>
            <div>
              <SkHeading size="h2">prompt système</SkHeading>
              <span className="sk-small">éditable sans redéploiement · versionné · rollback possible</span>
            </div>
            <div style={{ display:'flex', gap:8 }}>
              <span className="sk-tag">v1.3 · ACTIVE</span>
              <span className="sk-btn">historique</span>
              <span className="sk-btn sk-btn-cta">publier nouvelle version</span>
            </div>
          </div>

          <div style={{ display:'flex', gap:6, marginTop:14 }}>
            {['v1.0','v1.1','v1.2','v1.3'].map((v,i)=>(
              <span key={v} className="sk-pill sk-wob" style={{ fontSize:12, padding:'2px 10px', background:i===3?'var(--sk-accent)':SK.paper, color:i===3?SK.paper:SK.ink, borderColor:i===3?'var(--sk-accent)':SK.ink }}>{v}</span>
            ))}
            <span className="sk-small" style={{ marginLeft:'auto' }}>auteur · M. Cadot · 7 mai 2026</span>
          </div>

          <div className="sk-rect sk-wob" style={{ marginTop:12, padding:14, background:SK.paper2, fontFamily:'JetBrains Mono, monospace', fontSize:11, lineHeight:1.5, color:SK.ink, height:260, overflow:'hidden', position:'relative' }}>
            <div style={{ color:SK.ink2 }}>{'# system prompt · v1.3'}</div>
            <div style={{ color:SK.ink2 }}>{'# Règles de ton — non négociables'}</div>
            <div>1. Vouvoiement strict — « vous » ou prénom à la 3e personne</div>
            <div>2. Phrases courtes — &lt; 25 mots</div>
            <div>3. Zéro jargon psychologique : pas de « introverti, anxieux,</div>
            <div>   dispersé, hyperactif »</div>
            <div>4. Zéro terme pathologisant — aucun diagnostic</div>
            <div>5. Pas de « parce que » — causalité implicite</div>
            <div>6. Pas de clichés orientation : pas de boussole, copilote, miroir…</div>
            <div>7. Pas de termes wellness : pas d'épanouissement, alignement…</div>
            <div>8. Pas de marketing — pas de « excellence, talent unique »</div>
            <div style={{ color:'var(--sk-accent)' }}>9. Pas de comparaison compétitive — pas de « vous vous démarquez »</div>
            <div>10. Forces · format trait + condition d'expression</div>
            <div style={{ color:SK.ink3 }}>...</div>
            <div style={{ position:'absolute', right:10, bottom:8 }}><span className="sk-tag">2 184 / 8 000 tokens</span></div>
            <div style={{ position:'absolute', left:0, right:0, bottom:0, height:60, background:`linear-gradient(transparent, ${SK.paper2})` }}/>
          </div>
          <div style={{ display:'flex', gap:8, marginTop:10 }}>
            <span className="sk-btn sk-wob">éditer</span>
            <span className="sk-btn sk-wob">comparer à v1.2</span>
            <span className="sk-btn sk-wob">rollback v1.2</span>
            <span className="sk-small" style={{ marginLeft:'auto' }}>traçabilité B2G : chaque analyse stocke la version utilisée</span>
          </div>
        </div>

        {/* recent logs */}
        <div className="sk-rect-2 sk-wob" style={{ padding:16, background:SK.paper, overflow:'hidden' }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline' }}>
            <SkHeading size="h2">analyses récentes</SkHeading>
            <span className="sk-small">consultation · lecture seule</span>
          </div>
          <div style={{ marginTop:14, display:'flex', flexDirection:'column' }}>
            {[
              ['12:42','Marion C.','référente handicap','succès','v1.3','candidat'],
              ['12:28','Karim B.','dev fullstack','succès','v1.3','candidat'],
              ['11:55','Aïcha N.','reconversion santé','timeout','v1.3','—'],
              ['11:33','Élise R.','chargée DEI','succès','v1.3','conseiller'],
              ['11:02','Pierre L.','contrôleur de gestion','erreur','v1.3','—'],
              ['10:48','Camille D.','ergothérapeute','succès','v1.2','candidat'],
              ['10:21','Yann T.','technicien BTP','succès','v1.2','conseiller'],
            ].map(([h,n,c,st,v,a],i)=>(
              <div key={i} style={{ display:'grid', gridTemplateColumns:'40px 1fr 80px 60px 60px', gap:8, padding:'7px 0', borderBottom:`1px dashed ${SK.ink3}`, alignItems:'center' }}>
                <span className="sk-mono" style={{ fontSize:10, color:SK.ink2 }}>{h}</span>
                <div>
                  <span className="sk-body" style={{ fontSize:12 }}>{n}</span>
                  <div className="sk-small" style={{ fontSize:11 }}>{c}</div>
                </div>
                <span className="sk-tag" style={{ fontSize:9, background: st==='succès'?'#e8f1e3':st==='timeout'?'#fdf3d0':'#fae3df', borderColor:'transparent' }}>{st}</span>
                <span className="sk-mono" style={{ fontSize:10, color:SK.ink2 }}>{v}</span>
                <span className="sk-small" style={{ fontSize:11 }}>{a}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* sparkline strip */}
      <div className="sk-rect sk-wob" style={{ marginTop:14, padding:14, background:SK.paper, display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:18 }}>
        {[
          ['analyses · 30j', 'M T W T F S D · …'],
          ['tokens · 30j', '↑ 14% vs avril'],
          ['plans · candidat vs conseiller', '78 · 64'],
        ].map(([t,sub],i)=>(
          <div key={i}>
            <span className="sk-num">{t}</span>
            <svg width="100%" height="40" viewBox="0 0 240 40" style={{ marginTop:4 }}>
              <polyline points={i===0?'0,30 20,28 40,22 60,26 80,20 100,18 120,14 140,18 160,12 180,16 200,9 220,12 240,6':i===1?'0,34 20,30 40,30 60,24 80,28 100,22 120,18 140,20 160,16 180,12 200,14 220,8 240,10':'0,22 20,20 40,18 60,22 80,16 100,18 120,14 140,16 160,12 180,14 200,10 220,12 240,8'}
                stroke={i===2?'var(--sk-accent)':SK.ink} strokeWidth="1.6" fill="none" strokeLinecap="round"/>
            </svg>
            <span className="sk-small">{sub}</span>
          </div>
        ))}
      </div>

      <SkSticky rotate={2} style={{ position:'absolute', right:14, bottom:14 }}>
        anticiper l'archi :<br/>
        — dashboard conseiller<br/>
        — historique utilisateur<br/>
        — double export par analyse
      </SkSticky>
    </div>
  </SkChrome>
);

// ─── User space / history ────────────────────────────────────────────────
const FrameUserSpace = () => (
  <SkChrome w={1100} h={780} label="app.neoori.fr/espace">
    <SkAppBar active="Historique"/>
    <div className="sk-paper sk-root" style={{ flex:1, padding:'28px 44px', overflow:'hidden', position:'relative' }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-end' }}>
        <div>
          <SkHeading size="h1">Mon espace</SkHeading>
          <div className="sk-body" style={{ color:SK.ink2, marginTop:6 }}>Vos analyses, vos brouillons, votre code conseiller le cas échéant.</div>
        </div>
        <span className="sk-btn sk-btn-cta sk-wob">+ nouvelle analyse</span>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:14, marginTop:24 }}>
        {[
          {date:'7 mai 2026', title:'Référente handicap entreprise', state:'complète', plan:'payant', sec:9},
          {date:'2 mai 2026', title:'Chargée mission DEI · piste 2', state:'complète', plan:'payant', sec:9},
          {date:'28 avr.', title:'Référente neurodiversité', state:'gratuite', plan:'gratuit', sec:4},
          {date:'15 avr.', title:'Consultante portage', state:'brouillon', plan:'—', sec:0},
        ].map((a,i)=>(
          <div key={i} className="sk-rect-2 sk-wob" style={{ padding:16, background:SK.paper, position:'relative' }}>
            <span className="sk-tag">{a.date}</span>
            <div className="sk-h2" style={{ fontSize:18, marginTop:8 }}>{a.title}</div>
            <div style={{ display:'flex', gap:6, marginTop:8, flexWrap:'wrap' }}>
              <SkChip>{a.state}</SkChip>
              <SkChip dim>{a.plan}</SkChip>
              {a.sec>0 && <SkChip dim>{a.sec} sections</SkChip>}
            </div>
            <div style={{ height:60, marginTop:12, background:SK.paper2, borderRadius:4, padding:8 }}>
              <SkLines rows={3} widths={['100%','82%','55%']}/>
            </div>
            <div style={{ display:'flex', gap:8, marginTop:12 }}>
              <span className="sk-btn" style={{ padding:'4px 10px', fontSize:11 }}>ouvrir</span>
              <span className="sk-btn" style={{ padding:'4px 10px', fontSize:11 }}>↓</span>
              <span className="sk-btn" style={{ padding:'4px 10px', fontSize:11 }}>↗</span>
              <span style={{ marginLeft:'auto' }} className="sk-small">⋯</span>
            </div>
          </div>
        ))}

        <div className="sk-rect-d sk-wob" style={{ padding:16, background:SK.paper2, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', minHeight:220 }}>
          <span className="sk-hand" style={{ fontSize:32, color:SK.ink2 }}>+</span>
          <span className="sk-body" style={{ marginTop:8 }}>nouvelle analyse</span>
          <span className="sk-small">~2 min</span>
        </div>
      </div>

      {/* side panel : conseiller link + crédits */}
      <div style={{ display:'grid', gridTemplateColumns:'2fr 1fr', gap:14, marginTop:22 }}>
        <div className="sk-rect sk-wob" style={{ padding:14, background:SK.paper, display:'flex', alignItems:'center', gap:14 }}>
          <span className="sk-hand" style={{ fontSize:24 }}>partagez avec votre conseiller</span>
          <div className="sk-rect-thin sk-wob" style={{ padding:'6px 10px', background:SK.paper2, flex:1 }}>
            <span className="sk-mono" style={{ fontSize:11, color:SK.ink2 }}>neoori.fr/c/marion-c-mai26</span>
          </div>
          <span className="sk-btn">copier</span>
        </div>
        <div className="sk-rect sk-wob" style={{ padding:14, background:SK.paper, display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div>
            <span className="sk-num">crédits restants</span>
            <div className="sk-h2" style={{ fontSize:22, marginTop:2 }}>2 analyses</div>
          </div>
          <span className="sk-btn sk-btn-cta">recharger</span>
        </div>
      </div>

      <SkSticky rotate={-3} style={{ position:'absolute', right:24, bottom:24 }}>
        version bêta —<br/>retours bienvenus<br/>↑ bouton flottant ?
      </SkSticky>
    </div>
  </SkChrome>
);

Object.assign(window, { FrameAdmin, FrameUserSpace });
