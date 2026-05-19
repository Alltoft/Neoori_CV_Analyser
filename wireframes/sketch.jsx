// Sketch primitives for neoori CV-Analyzer wireframes
// Hand-drawn aesthetic — wobbly rects, hatched fills, Caveat annotations.
// All sizes are explicit px (artboards don't scroll).

const SK = {
  ink: '#1d1a17',
  ink2: 'rgba(29,26,23,0.55)',
  ink3: 'rgba(29,26,23,0.32)',
  paper: '#faf7f0',
  paper2: '#f3eee2',
  yellow: '#f7e07a',
  accents: {
    terracotta: '#c96442',
    forest: '#3f6b4b',
    indigo: '#4a4f8c',
    plum: '#7a3d5e',
    none: '#1d1a17',
  },
};

// One-shot CSS for sketch primitives — wobbly rect filter, fonts, hatch.
if (typeof document !== 'undefined' && !document.getElementById('sk-styles')) {
  const s = document.createElement('style');
  s.id = 'sk-styles';
  s.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;600;700&family=Architects+Daughter&family=Kalam:wght@300;400;700&family=Patrick+Hand&family=JetBrains+Mono:wght@400;600&display=swap');
    .sk-root{ font-family:'Patrick Hand', 'Kalam', system-ui, sans-serif; color:${SK.ink}; }
    .sk-hand{ font-family:'Caveat', cursive; }
    .sk-print{ font-family:'Architects Daughter', cursive; }
    .sk-mono{ font-family:'JetBrains Mono', monospace; }
    .sk-paper{ background:${SK.paper};
      background-image:
        radial-gradient(rgba(0,0,0,0.04) 1px, transparent 1.2px);
      background-size: 22px 22px;
    }
    .sk-plain{ background:${SK.paper}; }
    .sk-frame{ position:relative; }
    .sk-rect{ border:1.5px solid ${SK.ink}; border-radius:6px; }
    .sk-rect-2{ border:2px solid ${SK.ink}; border-radius:8px; }
    .sk-rect-d{ border:1.5px dashed ${SK.ink}; border-radius:6px; }
    .sk-rect-thin{ border:1px solid ${SK.ink2}; border-radius:5px; }
    .sk-wob{ filter:url(#sk-wobble); }
    .sk-hatch{
      background-image: repeating-linear-gradient(45deg,
        rgba(29,26,23,0.18) 0 1px, transparent 1px 7px);
    }
    .sk-hatch-soft{
      background-image: repeating-linear-gradient(45deg,
        rgba(29,26,23,0.08) 0 1px, transparent 1px 8px);
    }
    .sk-hatch-accent{
      background-image: repeating-linear-gradient(45deg,
        var(--sk-accent, ${SK.accents.terracotta}) 0 1.5px, transparent 1.5px 8px);
      opacity: .35;
    }
    .sk-stamp{ display:inline-block; border:1.5px solid ${SK.ink}; padding:1px 6px; border-radius:3px; transform:rotate(-1.5deg); font-family:'Architects Daughter',cursive; font-size:10px; letter-spacing:.04em; }
    .sk-stamp-accent{ background:var(--sk-accent, ${SK.accents.terracotta}); color:${SK.paper}; border-color:var(--sk-accent, ${SK.accents.terracotta}); }
    .sk-pill{ display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border:1.5px solid ${SK.ink}; border-radius:999px; background:${SK.paper}; }
    .sk-btn{ display:inline-flex; align-items:center; gap:6px; padding:7px 14px; border:1.5px solid ${SK.ink}; border-radius:8px; background:${SK.paper}; font:inherit; cursor:default; }
    .sk-btn-cta{ background:var(--sk-accent, ${SK.accents.terracotta}); color:${SK.paper}; border-color:var(--sk-accent, ${SK.accents.terracotta}); }
    .sk-arrow{ stroke:${SK.ink}; stroke-width:1.4; fill:none; stroke-linecap:round; }
    .sk-anno{ font-family:'Caveat', cursive; color:${SK.ink2}; font-size:15px; line-height:1.05; }
    .sk-anno-acc{ font-family:'Caveat', cursive; color:var(--sk-accent, ${SK.accents.terracotta}); font-weight:600; }
    .sk-line{ height:1.5px; background:${SK.ink}; border-radius:1px; }
    .sk-line-soft{ height:1px; background:${SK.ink3}; }
    .sk-strike{ position:relative; }
    .sk-strike::after{ content:""; position:absolute; left:-2px; right:-2px; top:55%; height:1.5px; background:${SK.ink}; transform:rotate(-2deg); }
    .sk-check{ width:14px; height:14px; border:1.5px solid ${SK.ink}; border-radius:3px; display:inline-block; vertical-align:-3px; position:relative; }
    .sk-check.on::after{ content:"✓"; position:absolute; inset:-6px -2px 0 -1px; font-family:'Caveat',cursive; font-size:18px; color:var(--sk-accent,${SK.accents.terracotta}); }
    .sk-radio{ width:14px; height:14px; border:1.5px solid ${SK.ink}; border-radius:50%; display:inline-block; vertical-align:-3px; position:relative; }
    .sk-radio.on::after{ content:""; position:absolute; inset:3px; border-radius:50%; background:var(--sk-accent,${SK.accents.terracotta}); }
    .sk-tag{ font-family:'JetBrains Mono', monospace; font-size:10px; padding:2px 6px; border:1px solid ${SK.ink2}; border-radius:3px; color:${SK.ink2}; background:${SK.paper}; text-transform:uppercase; letter-spacing:.05em; }
    .sk-h1{ font-family:'Caveat', cursive; font-weight:700; font-size:34px; line-height:1; letter-spacing:-.01em; }
    .sk-h2{ font-family:'Caveat', cursive; font-weight:700; font-size:24px; line-height:1; }
    .sk-h3{ font-family:'Architects Daughter', cursive; font-weight:400; font-size:14px; letter-spacing:.04em; text-transform:uppercase; }
    .sk-body{ font-family:'Patrick Hand', cursive; font-size:14px; line-height:1.35; }
    .sk-small{ font-family:'Patrick Hand', cursive; font-size:12px; line-height:1.3; color:${SK.ink2}; }
    .sk-num{ font-family:'Architects Daughter', cursive; font-size:11px; letter-spacing:.05em; color:${SK.ink2}; }
    /* placeholder text lines */
    .sk-ph{ height:6px; background:${SK.ink3}; border-radius:3px; }
    .sk-ph.sk-ph-d{ background:repeating-linear-gradient(90deg, ${SK.ink3} 0 6px, transparent 6px 10px); height:6px; }
    .sk-ph-strong{ background:${SK.ink2}; }
    .sk-corner-fold{ position:absolute; top:0; right:0; width:22px; height:22px; background:linear-gradient(225deg, transparent 50%, rgba(0,0,0,0.08) 50%); border-bottom-left-radius:3px; }
    .sk-grid{ background-image:
        linear-gradient(rgba(0,0,0,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,0,0,0.05) 1px, transparent 1px);
      background-size:32px 32px; }
    .sk-shadow-soft{ box-shadow: 3px 4px 0 rgba(0,0,0,0.06); }
    .sk-locked{ position:relative; }
    .sk-locked::after{ content:""; position:absolute; inset:0; background:rgba(250,247,240,0.68); backdrop-filter:blur(1.5px); border-radius:inherit; pointer-events:none; }
    .sk-locked > .sk-lock-badge{ position:absolute; right:8px; top:8px; z-index:2; }
    [data-density="compact"] .sk-frame{ --sk-pad: 14px; }
    [data-density="cozy"] .sk-frame{ --sk-pad: 22px; }
  `;
  document.head.appendChild(s);

  // SVG wobble filter — gentle turbulence so borders feel hand-drawn.
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', '0'); svg.setAttribute('height', '0');
  svg.style.position = 'absolute';
  svg.innerHTML = `
    <defs>
      <filter id="sk-wobble" x="-2%" y="-2%" width="104%" height="104%">
        <feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="3" />
        <feDisplacementMap in="SourceGraphic" scale="1.6"/>
      </filter>
      <filter id="sk-wobble-strong" x="-2%" y="-2%" width="104%" height="104%">
        <feTurbulence type="fractalNoise" baseFrequency="0.025" numOctaves="2" seed="7" />
        <feDisplacementMap in="SourceGraphic" scale="2.4"/>
      </filter>
    </defs>`;
  document.body.appendChild(svg);
}

// --- Building blocks ---

const SkBox = ({ children, className='', style={}, wobble=true, ...rest }) => (
  <div className={`sk-rect ${wobble?'sk-wob':''} ${className}`} style={style} {...rest}>
    {children}
  </div>
);

const SkDashed = ({ children, className='', style={} }) => (
  <div className={`sk-rect-d sk-wob ${className}`} style={style}>{children}</div>
);

// Wavy underline for headings — drawn with SVG path.
const Squiggle = ({ width=120, color, style={} }) => (
  <svg width={width} height="6" viewBox={`0 0 ${width} 6`} style={{ display:'block', ...style }}>
    <path d={`M2 4 Q ${width/8} 1 ${width/4} 3 T ${width/2} 3 T ${3*width/4} 3 T ${width-2} 3`}
      stroke={color||SK.ink} strokeWidth="1.4" fill="none" strokeLinecap="round"/>
  </svg>
);

// Arrow with squiggle path
const Arrow = ({ d, color, width=320, height=80, dash=false }) => (
  <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ position:'absolute', left:0, top:0, pointerEvents:'none' }}>
    <path d={d} stroke={color||SK.ink2} strokeWidth="1.4" fill="none" strokeLinecap="round" strokeDasharray={dash?'4 4':'0'} markerEnd="url(#sk-arrowhead)"/>
    <defs>
      <marker id="sk-arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
        <path d="M0,0 L9,5 L0,10 z" fill={color||SK.ink2}/>
      </marker>
    </defs>
  </svg>
);

// Placeholder lines block (for body copy stand-ins)
const SkLines = ({ rows=3, widths=['100%','92%','64%'], gap=8, strong=false }) => (
  <div style={{ display:'flex', flexDirection:'column', gap }}>
    {Array.from({length:rows}).map((_,i)=>(
      <div key={i} className={`sk-ph ${strong?'sk-ph-strong':''}`} style={{ width: widths[i%widths.length] }} />
    ))}
  </div>
);

// Sketchy heading with squiggle underline
const SkHeading = ({ children, size='h1', accent=false, style={} }) => {
  const cls = size==='h1' ? 'sk-h1' : size==='h2' ? 'sk-h2' : 'sk-h3';
  return (
    <div style={{ display:'inline-flex', flexDirection:'column', alignItems:'flex-start', ...style }}>
      <span className={cls} style={accent?{ color:'var(--sk-accent)'}:undefined}>{children}</span>
      {(size==='h1'||size==='h2') && <Squiggle width={size==='h1'?160:100} color={accent?undefined:SK.ink2} style={{ marginTop:2, marginLeft:2 }}/>}
    </div>
  );
};

// Numbered section badge ('§ 3')
const SkSection = ({ n, title, sub, locked=false }) => (
  <div style={{ display:'flex', alignItems:'baseline', gap:10 }}>
    <span className="sk-stamp">§ {n}</span>
    <span className="sk-h2" style={{ fontSize:20, textDecoration: locked?'line-through':'none', textDecorationColor:SK.ink3 }}>{title}</span>
    {sub && <span className="sk-small" style={{ marginLeft:6 }}>{sub}</span>}
    {locked && <span className="sk-tag" style={{ marginLeft:8 }}>plan payant</span>}
  </div>
);

// Annotation chip — handwritten note with arrow
const SkNote = ({ children, style={}, accent=false }) => (
  <span className={accent?'sk-anno-acc':'sk-anno'} style={style}>{children}</span>
);

// Empty input field
const SkInput = ({ label, ph, w='100%', value, suffix, multiline=false, error=false }) => (
  <div style={{ width:w, display:'flex', flexDirection:'column', gap:5 }}>
    {label && <span className="sk-num">{label}</span>}
    <div className={`sk-rect ${error?'':'sk-wob'}`} style={{
      padding:'8px 10px', minHeight: multiline?64:32,
      background:SK.paper, borderColor: error?SK.accents.terracotta:undefined,
      display:'flex', alignItems:multiline?'flex-start':'center', justifyContent:'space-between',
    }}>
      <span className={value?'sk-body':'sk-body'} style={{ color: value?SK.ink:SK.ink3 }}>{value || ph}</span>
      {suffix && <span className="sk-small">{suffix}</span>}
    </div>
  </div>
);

// Dropdown caret box
const SkSelect = ({ label, value, ph, w='100%' }) => (
  <div style={{ width:w, display:'flex', flexDirection:'column', gap:5 }}>
    {label && <span className="sk-num">{label}</span>}
    <div className="sk-rect sk-wob" style={{ padding:'8px 10px', minHeight:32, display:'flex', alignItems:'center', justifyContent:'space-between' }}>
      <span className="sk-body" style={{ color: value?SK.ink:SK.ink3 }}>{value || ph}</span>
      <span className="sk-mono" style={{ fontSize:11 }}>▾</span>
    </div>
  </div>
);

// Chip / pill option
const SkChip = ({ children, on=false, dim=false }) => (
  <span className={`sk-pill sk-wob`} style={{
    background: on?'var(--sk-accent)':SK.paper,
    color: on?SK.paper:dim?SK.ink2:SK.ink,
    borderColor: on?'var(--sk-accent)':SK.ink,
    fontFamily:'Patrick Hand, cursive', fontSize:13, padding:'2px 9px',
  }}>{children}</span>
);

// Sketchy “image / asset” placeholder with X across
const SkAsset = ({ w=100, h=80, label }) => (
  <div className="sk-rect sk-wob" style={{ width:w, height:h, position:'relative', overflow:'hidden', background:SK.paper2 }}>
    <svg width="100%" height="100%" style={{ position:'absolute', inset:0 }}>
      <line x1="0" y1="0" x2="100%" y2="100%" stroke={SK.ink3} strokeWidth="1"/>
      <line x1="100%" y1="0" x2="0" y2="100%" stroke={SK.ink3} strokeWidth="1"/>
    </svg>
    {label && <span className="sk-small" style={{ position:'absolute', left:6, bottom:4 }}>{label}</span>}
  </div>
);

// Sticky-note style annotation
const SkSticky = ({ children, rotate=-2, style={} }) => (
  <div style={{
    background:'#fef3a0', padding:'8px 10px', borderRadius:2,
    transform:`rotate(${rotate}deg)`,
    boxShadow:'2px 3px 0 rgba(0,0,0,0.08)',
    fontFamily:'Caveat, cursive', fontSize:15, lineHeight:1.05,
    color:'#5a4a2a', maxWidth:200,
    ...style
  }}>{children}</div>
);

// Browser/tab chrome — minimal
const SkChrome = ({ children, w, h, label='app.neoori.fr/analyse', dark=false }) => (
  <div className="sk-rect-2 sk-wob" style={{ width:w, height:h, background:SK.paper, overflow:'hidden', display:'flex', flexDirection:'column' }}>
    <div style={{ display:'flex', alignItems:'center', gap:8, padding:'8px 12px', borderBottom:`1.5px solid ${SK.ink}`, background:SK.paper2 }}>
      <div style={{ display:'flex', gap:5 }}>
        <span style={{ width:10, height:10, borderRadius:'50%', border:`1.2px solid ${SK.ink}` }}/>
        <span style={{ width:10, height:10, borderRadius:'50%', border:`1.2px solid ${SK.ink}` }}/>
        <span style={{ width:10, height:10, borderRadius:'50%', border:`1.2px solid ${SK.ink}` }}/>
      </div>
      <div className="sk-mono" style={{ fontSize:11, color:SK.ink2, marginLeft:10 }}>{label}</div>
      <div style={{ marginLeft:'auto', display:'flex', gap:6 }}>
        <span className="sk-mono" style={{ fontSize:10, color:SK.ink3 }}>FR</span>
        <span className="sk-tag">v1.3 · bêta</span>
      </div>
    </div>
    <div className="sk-frame" style={{ flex:1, position:'relative', overflow:'hidden' }}>{children}</div>
  </div>
);

// neoori "logo" — wordmark with hand-drawn dot under the double-o
const NeooriMark = ({ size=18 }) => (
  <span style={{ display:'inline-flex', alignItems:'baseline', gap:0, position:'relative' }}>
    <span className="sk-hand" style={{ fontSize:size+8, fontWeight:700, letterSpacing:'-0.02em' }}>neoori</span>
    <svg width="32" height="6" viewBox="0 0 32 6" style={{ position:'absolute', left:size*0.95, bottom:-3 }}>
      <path d="M2 3 Q 8 1 14 3 T 28 3" stroke="var(--sk-accent)" strokeWidth="1.6" fill="none" strokeLinecap="round"/>
    </svg>
  </span>
);

// Top-strip nav inside a chrome
const SkAppBar = ({ active='Analyse', accentBadge=false }) => (
  <div style={{ display:'flex', alignItems:'center', gap:16, padding:'10px 16px', borderBottom:`1px solid ${SK.ink3}`, background:SK.paper }}>
    <NeooriMark size={14}/>
    <div style={{ display:'flex', gap:14, marginLeft:20 }}>
      {['Analyse CV','Portrait','Historique'].map(t=>(
        <span key={t} className="sk-body" style={{ fontSize:13, color: t===active?SK.ink:SK.ink2, borderBottom: t===active?`1.5px solid var(--sk-accent)`:'none', paddingBottom:2 }}>{t}</span>
      ))}
    </div>
    <span style={{ marginLeft:'auto' }} className="sk-small">MC</span>
    <span style={{ width:26, height:26, borderRadius:'50%', border:`1.5px solid ${SK.ink}`, display:'inline-flex', alignItems:'center', justifyContent:'center', fontFamily:'Caveat,cursive', fontSize:14 }}>M</span>
  </div>
);

// expose to window for other babel files
Object.assign(window, {
  SK, SkBox, SkDashed, SkLines, SkHeading, SkSection, SkNote, SkInput, SkSelect,
  SkChip, SkAsset, SkSticky, SkChrome, NeooriMark, SkAppBar, Squiggle, Arrow,
});
