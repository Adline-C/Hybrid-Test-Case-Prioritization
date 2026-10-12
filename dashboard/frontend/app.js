const { useState, useEffect, useCallback, useRef } = React;

const API_BASE = "https://hybrid-test-case-prioritization.onrender.com";

function formatScore(score) {
  return Number(score).toFixed(2);
}

function scoreClass(score, threshold) {
  if (score >= threshold) return "high";
  if (score > 0) return "mid";
  return "low";
}

function rowClass(score, threshold) {
  if (score >= threshold) return "row-high";
  if (score > 0) return "row-mid";
  return "row-low";
}

function shortName(name) {
  return name.replace(/^.*::/, "");
}

// ── HistoryDots ───────────────────────────────────────────────────────────────
function HistoryDots({ history }) {
  if (!history || history.length === 0)
    return <span className="badge-no">—</span>;
  return (
    <span className="history-dots" title={history.map(h => h ? "P" : "F").join(" ")}>
      {history.slice(-5).map((h, i) => (
        <span key={i} className={h ? "dot-pass" : "dot-fail"} />
      ))}
    </span>
  );
}

// ── CopilotDrawer ─────────────────────────────────────────────────────────────
function CopilotDrawer({ testItem, changedFiles, wc, wh, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!testItem) return;
    let active = true;
    setLoading(true);
    setError(null);

    fetch(`${API_BASE}/api/copilot/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        test_name: testItem.name,
        score: testItem.score,
        changed_files: changedFiles || [],
        recent_fails: testItem.failures_in_last_5 || 0,
        w_c: wc,
        w_h: wh
      })
    })
      .then(res => {
        if (!res.ok) throw new Error("Failed to load explanation");
        return res.json();
      })
      .then(resData => {
        if (active) setData(resData);
      })
      .catch(err => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [testItem, changedFiles, wc, wh]);

  if (!testItem) return null;

  const c_impact_pct = testItem.overlap ? 100 : 0;
  const f_recency_pct = Math.round(( (testItem.failures_in_last_5 || 0) / 5.0 ) * 100);

  return (
    <>
      <div className="copilot-backdrop" onClick={onClose} />
      <div className="copilot-drawer">
        <div className="copilot-header">
          <div>
            <div className="copilot-title">⚡ AI Copilot Insights</div>
            <div style={{fontSize: '.72rem', color: 'var(--muted)', fontFamily: 'var(--mono)', marginTop: '.2rem'}}>
              {testItem.name}
            </div>
          </div>
          <button className="copilot-close" onClick={onClose}>&times;</button>
        </div>

        {loading && (
          <div className="state-box" style={{padding: '2rem 1rem'}}>
            <div className="icon"><span className="spinner"/></div>
            <p>Analyzing test telemetry & code diffs…</p>
          </div>
        )}

        {!loading && error && (
          <div className="state-box" style={{padding: '1.5rem 1rem'}}>
            <div className="icon">⚠️</div>
            <p style={{color: 'var(--red)'}}>{error}</p>
          </div>
        )}

        {!loading && data && (
          <>
            {/* Recommendation Box */}
            <div className="copilot-recommendation-box">
              <span>🎯 Action:</span> {data.recommendation}
            </div>

            {/* Explanation Section */}
            <div className="copilot-section">
              <div className="copilot-section-label">Priority Explanation</div>
              <div className="copilot-explanation-box">
                {data.explanation}
              </div>
            </div>

            {/* Risk Breakdown Section */}
            <div className="copilot-section">
              <div className="copilot-section-label">Risk Factor Breakdown</div>
              <div className="copilot-risk-bars">
                <div className="copilot-risk-item">
                  <div className="copilot-risk-header">
                    <span>Change Impact (C = {data.c_t})</span>
                    <span style={{color: testItem.overlap ? 'var(--accent)' : 'var(--muted)'}}>
                      {testItem.overlap ? 'High Risk' : 'No Overlap'}
                    </span>
                  </div>
                  <div className="copilot-bar-track">
                    <div className="copilot-bar-fill" style={{width: `${c_impact_pct}%`, background: 'var(--accent)'}} />
                  </div>
                </div>

                <div className="copilot-risk-item">
                  <div className="copilot-risk-header">
                    <span>Failure Recency (H = {data.h_t})</span>
                    <span style={{color: f_recency_pct > 0 ? 'var(--red)' : 'var(--muted)'}}>
                      {testItem.failures_in_last_5} / 5 Failures
                    </span>
                  </div>
                  <div className="copilot-bar-track">
                    <div className="copilot-bar-fill" style={{width: `${f_recency_pct}%`, background: 'var(--red)'}} />
                  </div>
                </div>
              </div>
            </div>

            {/* Formula Detail Card */}
            <div className="copilot-section" style={{marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border)'}}>
              <div className="copilot-section-label">CHART-P Score Formula</div>
              <div style={{fontFamily: 'var(--mono)', fontSize: '.75rem', color: 'var(--text2)', background: 'rgba(0,0,0,0.3)', padding: '.75rem', borderRadius: '6px'}}>
                S(t) = w_c &times; C(t) + w_h &times; H(t)<br/>
                S(t) = {wc} &times; {data.c_t} + {wh} &times; {data.h_t} = <b>{testItem.score.toFixed(2)}</b>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ── RankingTable ──────────────────────────────────────────────────────────────
function RankingTable({ tests, changedFiles, wc, wh, apfdData, onExplainTest }) {
  const threshold = (wc + wh) * 0.75;
  const high = tests.filter(t => t.score >= threshold).length;
  const mid = tests.filter(t => t.score > 0 && t.score < threshold).length;
  const atRisk = tests.filter(t => t.overlap).length;

  return (
    <>
      {/* Stats bar */}
      <div className="stats">
        <div className="stat c-accent">
          <div className="stat-val">{tests.length}</div>
          <div className="stat-lbl">Total Tests</div>
        </div>
        <div className="stat c-red">
          <div className="stat-val">{high}</div>
          <div className="stat-lbl">High Priority (Score &gt;= {threshold.toFixed(2)})</div>
        </div>
        <div className="stat c-amber">
          <div className="stat-val">{mid}</div>
          <div className="stat-lbl">Medium Priority</div>
        </div>
        <div className="stat c-green">
          <div className="stat-val">{atRisk}</div>
          <div className="stat-lbl">Touch Changed Code</div>
        </div>
      </div>

      <APFDChart apfdData={apfdData} />

      {/* Changed files */}
      {changedFiles && changedFiles.length > 0 && (
        <>
          <p style={{fontSize:'.72rem', color:'var(--muted)', marginBottom:'.5rem', fontWeight:'600', textTransform:'uppercase', letterSpacing:'.05em'}}>
            Files changed in latest commit:
          </p>
          <div className="pills">
            {changedFiles.map(f => <span key={f} className="pill">{f}</span>)}
          </div>
        </>
      )}

      {/* Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Prioritized Test Order</span>
          <span className="card-meta">Sorted by score — highest risk first</span>
        </div>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th style={{width:'52px'}}>#</th>
                <th>Test Name</th>
                <th>Score</th>
                <th>Changed File?</th>
                <th>Recent Fails</th>
                <th>Last 5 Runs</th>
                <th style={{textAlign:'right'}}>Copilot</th>
              </tr>
            </thead>
            <tbody>
              {tests.map(t => (
                <tr key={t.name} className={rowClass(t.score, threshold)}>
                  <td style={{color:'var(--muted)', fontFamily:'var(--mono)', fontWeight:'600'}}>{t.rank}</td>
                  <td>
                    <span className="test-name" title={t.name}>{shortName(t.name)}</span>
                    <div className="test-module">{t.name.split('::')[0]}</div>
                  </td>
                  <td>
                    <span className={`score-chip ${scoreClass(t.score, threshold)}`}>{formatScore(t.score)}</span>
                  </td>
                  <td>
                    {t.overlap
                      ? <span className="badge-yes">✓ YES</span>
                      : <span className="badge-no">no</span>}
                  </td>
                  <td style={{color: t.failures_in_last_5 > 0 ? 'var(--red)' : 'var(--muted)', fontFamily:'var(--mono)', fontWeight:'600'}}>
                    {t.failures_in_last_5}
                  </td>
                  <td><HistoryDots history={t.history} /></td>
                  <td style={{textAlign:'right'}}>
                    <button className="btn-copilot" onClick={() => onExplainTest(t)}>
                      ⚡ Explain
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ── ComparisonView ────────────────────────────────────────────────────────────
function ComparisonView({ data, wc, wh }) {
  if (!data) return null;
  const { before, after, detail } = data;
  const detailMap = {};
  detail.forEach(d => { detailMap[d.name] = d; });
  const threshold = (wc + wh) * 0.75;

  return (
    <>
      <div className="card" style={{marginBottom:'1.5rem'}}>
        <div className="card-header">
          <span className="card-title">Before vs. After Prioritization</span>
          <span className="card-meta">How many positions each test moved when the engine ran</span>
        </div>
        <div style={{padding:'1.2rem'}}>
          <div className="cmp-grid">
            {/* BEFORE */}
            <div>
              <div className="cmp-col-hdr">🔵 Before (alphabetical / default pytest)</div>
              {before.map((name, i) => (
                <div key={name} className="cmp-item">
                  <span className="cmp-num">{i+1}</span>
                  <span style={{flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}} title={name}>{shortName(name)}</span>
                </div>
              ))}
            </div>

            {/* AFTER */}
            <div>
              <div className="cmp-col-hdr">🟠 After (prioritized by engine)</div>
              {after.map((name, i) => {
                const d = detailMap[name];
                const moved = d ? d.moved_by : 0;
                return (
                  <div key={name} className="cmp-item">
                    <span className="cmp-num">{i+1}</span>
                    <span style={{flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}} title={name}>{shortName(name)}</span>
                    {moved > 0 && <span className="cmp-moved-pos">▲{moved}</span>}
                    {moved < 0 && <span className="cmp-moved-neg">▼{Math.abs(moved)}</span>}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Movement detail table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Movement Detail</span>
          <span className="card-meta">Positive = test was promoted (runs earlier)</span>
        </div>
        <div className="tbl-wrap">
          <table className="cmp-table">
            <thead>
              <tr>
                <th>Test</th>
                <th>Before Rank</th>
                <th>After Rank</th>
                <th>Score</th>
                <th>Moved By</th>
              </tr>
            </thead>
            <tbody>
              {detail
                .slice()
                .sort((a,b) => Math.abs(b.moved_by) - Math.abs(a.moved_by))
                .map(d => (
                  <tr key={d.name}>
                    <td className="test-name-col"><span className="test-name" title={d.name}>{shortName(d.name)}</span></td>
                    <td style={{color:'var(--muted)', fontFamily:'var(--mono)'}}>{d.before_rank}</td>
                    <td style={{fontFamily:'var(--mono)'}}>{d.after_rank}</td>
                    <td>
                      <span className={`score-chip ${scoreClass(d.score, threshold)}`}>{formatScore(d.score)}</span>
                    </td>
                    <td>
                      {d.moved_by > 0 && <span className="cmp-moved-pos">▲ {d.moved_by}</span>}
                      {d.moved_by < 0 && <span className="cmp-moved-neg">▼ {Math.abs(d.moved_by)}</span>}
                      {d.moved_by === 0 && <span style={{color:'var(--muted)'}}>—</span>}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ── APFDChart ───────────────────────────────────────────────────────────────────
const { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } = Recharts;

function APFDChart({ apfdData }) {
  if (!apfdData || apfdData.length === 0) return null;

  return (
    <div className="card" style={{marginTop: '1.5rem', marginBottom: '1.5rem', padding: '1.5rem'}}>
      <div className="card-header" style={{marginBottom: '1rem'}}>
        <span className="card-title">APFD Cumulative Fault Detection</span>
        <span className="card-meta">Comparing CHART-P vs. Random Baseline</span>
      </div>
      <div style={{width: '100%', height: 350}}>
        <ResponsiveContainer>
          <LineChart data={apfdData} margin={{top: 10, right: 30, left: 0, bottom: 0}}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2e33" />
            <XAxis dataKey="step" stroke="#8892b0" />
            <YAxis stroke="#8892b0" domain={[0, 100]} />
            <Tooltip 
              contentStyle={{backgroundColor: '#121418', borderColor: '#2a2e33', color: '#fff'}}
              itemStyle={{color: '#fff'}}
            />
            <Legend />
            <Line type="monotone" dataKey="chart_p" name="CHART-P Ranking" stroke="#FF7A00" strokeWidth={3} dot={{r: 3}} activeDot={{r: 6}} />
            <Line type="monotone" dataKey="random" name="Random Baseline" stroke="#8892b0" strokeWidth={2} dot={{r: 2}} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ── LandingPageWrapper ────────────────────────────────────────────────────────
function LandingPageWrapper({ onLaunch }) {
  const scrollToSection = (id, e) => {
    if (e) e.preventDefault();
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div style={{ background: '#0b0b0c', color: '#f4f1ec', minHeight: '100vh', fontFamily: "'Inter', sans-serif" }}>
      {/* ── Navigation Bar ── */}
      <header style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 30, background: 'rgba(11, 11, 12, 0.85)', backdropFilter: 'blur(12px)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.2rem 2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontFamily: "'Bebas Neue', sans-serif", fontSize: '1.6rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            <span style={{ width: '30px', height: '30px', borderRadius: '8px', background: 'linear-gradient(135deg, #ff5500, #ff7a00)', display: 'grid', placeItems: 'center', color: '#fff', fontSize: '1.1rem', boxShadow: '0 0 16px rgba(255,85,0,0.5)' }}>⚡</span>
            CHART-P
          </div>
          <nav style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '30px', padding: '0.3rem 0.6rem' }}>
            <a href="#features" onClick={(e) => scrollToSection('features', e)} style={{ color: 'rgba(255,255,255,0.7)', textDecoration: 'none', padding: '0.4rem 1rem', fontSize: '0.85rem', fontWeight: '500', borderRadius: '20px', transition: 'all 0.15s' }}>Features</a>
            <a href="#architecture" onClick={(e) => scrollToSection('architecture', e)} style={{ color: 'rgba(255,255,255,0.7)', textDecoration: 'none', padding: '0.4rem 1rem', fontSize: '0.85rem', fontWeight: '500', borderRadius: '20px', transition: 'all 0.15s' }}>Architecture</a>
            <a href="#benchmarks" onClick={(e) => scrollToSection('benchmarks', e)} style={{ color: 'rgba(255,255,255,0.7)', textDecoration: 'none', padding: '0.4rem 1rem', fontSize: '0.85rem', fontWeight: '500', borderRadius: '20px', transition: 'all 0.15s' }}>APFD Benchmarks</a>
          </nav>
          <div>
            <button
              onClick={onLaunch}
              style={{ background: 'linear-gradient(135deg, #ff5500, #ff7a00)', color: '#fff', border: 'none', borderRadius: '30px', padding: '0.55rem 1.4rem', fontWeight: '700', fontSize: '0.88rem', cursor: 'pointer', boxShadow: '0 0 24px rgba(255,85,0,0.5)', transition: 'all 0.18s' }}
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero Section ── */}
      <section style={{ position: 'relative', overflow: 'hidden', padding: '10rem 2rem 5rem', maxWidth: '1280px', margin: '0 auto' }}>
        {/* Background 3D Video / Image Asset */}
        <div style={{ position: 'absolute', inset: 0, zIndex: -1, overflow: 'hidden', pointerEvents: 'none' }}>
          <video
            autoPlay
            loop
            muted
            playsInline
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 0.3, pointerEvents: 'none' }}
          >
            <source src="https://www.pexels.com/download/video/27936889/" type="video/mp4" />
            <source src="https://assets.mixkit.co/videos/preview/mixkit-digital-animation-of-screens-and-code-42352-large.mp4" type="video/mp4" />
            <source src="/hero-bg.mp4" type="video/mp4" />
          </video>
          <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.8) 50%, #0B0B0C 100%)' }} />
        </div>

        <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.2em', color: '#ff7a00', marginBottom: '1.2rem' }}>CHART-P · Test Prioritization Framework</p>
        <h1 className="font-bebas" style={{ fontSize: 'clamp(3rem, 7vw, 5.5rem)', textTransform: 'uppercase', lineHeight: '0.95', letterSpacing: '0.04em', maxWidth: '1000px', margin: '0 0 1.8rem' }}>
          Transforming unordered CI suites into <span style={{ background: 'linear-gradient(135deg, #ff5500, #ff7a00)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>high-speed test pipelines.</span>
        </h1>
        <p style={{ fontSize: '1.15rem', color: 'rgba(255,255,255,0.65)', maxWidth: '650px', lineHeight: '1.6', marginBottom: '2.5rem' }}>
          Automated AST commit-diff parsing, historical recency weighting, and explainable AI scoring for Python microservices.
        </p>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '5rem' }}>
          <button
            onClick={onLaunch}
            style={{ background: 'linear-gradient(135deg, #ff5500, #ff7a00)', color: '#fff', border: 'none', borderRadius: '30px', padding: '0.85rem 2rem', fontWeight: '700', fontSize: '1rem', cursor: 'pointer', boxShadow: '0 0 32px rgba(255,85,0,0.55)', transition: 'all 0.18s' }}
          >
            Launch Workspace →
          </button>
          <button
            onClick={(e) => scrollToSection('benchmarks', e)}
            style={{ background: 'transparent', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '30px', padding: '0.85rem 2rem', fontWeight: '600', fontSize: '1rem', cursor: 'pointer', transition: 'all 0.18s' }}
          >
            View Benchmarks
          </button>
        </div>

        {/* ── Key Metrics Cards ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1px', background: 'rgba(255,255,255,0.08)', borderRadius: '16px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ background: '#141416', padding: '1.8rem' }}>
            <div className="font-bebas" style={{ fontSize: '2.8rem', letterSpacing: '0.04em', lineHeight: '1' }}>
              88.7% <span style={{ background: 'linear-gradient(135deg, #ff5500, #ff7a00)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontSize: '1.8rem' }}>MEAN APFD</span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.55)', marginTop: '0.5rem' }}>Across 30 simulated build cycles</p>
          </div>
          <div style={{ background: '#141416', padding: '1.8rem' }}>
            <div className="font-bebas" style={{ fontSize: '2.8rem', letterSpacing: '0.04em', lineHeight: '1' }}>
              &lt; 0.42s <span style={{ background: 'linear-gradient(135deg, #ff5500, #ff7a00)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontSize: '1.8rem' }}>LATENCY</span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.55)', marginTop: '0.5rem' }}>Static AST parsing vs 300s runtime execution</p>
          </div>
          <div style={{ background: '#141416', padding: '1.8rem' }}>
            <div className="font-bebas" style={{ fontSize: '2.8rem', letterSpacing: '0.04em', lineHeight: '1' }}>
              ZERO <span style={{ background: 'linear-gradient(135deg, #ff5500, #ff7a00)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontSize: '1.8rem' }}>ML OVERHEAD</span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.55)', marginTop: '0.5rem' }}>100% deterministic & offline fallback safe</p>
          </div>
        </div>
      </section>

      {/* ── Features Section ── */}
      <section id="features" style={{ padding: '6rem 2rem', borderTop: '1px solid rgba(255,255,255,0.08)', maxWidth: '1280px', margin: '0 auto' }}>
        <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.2em', color: '#ff7a00', marginBottom: '0.5rem' }}>Core Capabilities</p>
        <h2 className="font-bebas" style={{ fontSize: '3rem', letterSpacing: '0.05em', textTransform: 'uppercase', margin: '0 0 3rem' }}>Four engines, one ranked suite</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1.5rem' }}>
          {[
            ['STATIC ANALYSIS', 'AST Commit-Diff Inspection', 'Extracts modified .py imports without dynamic tracing.'],
            ['FAILURE RECENCY', 'PostgreSQL Run History', 'Weights failure patterns across N=5 CI builds.'],
            ['EXPLAINABILITY', 'AI Copilot Explanation Engine', 'Translates composite scores into natural language reasoning.'],
            ['GRAPH ENGINE', 'Interactive Knowledge Graph', 'Visualizes dependencies capped at top 200 high-risk nodes.']
          ].map(([tag, title, desc], i) => (
            <div key={tag} style={{ background: '#141416', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '1.8rem', position: 'relative' }}>
              <span style={{ fontSize: '0.7rem', fontFamily: "'JetBrains Mono', monospace", color: '#ff7a00', border: '1px solid rgba(255,122,0,0.3)', padding: '0.2rem 0.6rem', borderRadius: '12px' }}>[{tag}]</span>
              <h3 className="font-bebas" style={{ fontSize: '1.8rem', letterSpacing: '0.05em', textTransform: 'uppercase', margin: '1.2rem 0 0.5rem' }}>{title}</h3>
              <p style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.6)', lineHeight: '1.5' }}>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Benchmarks Section ── */}
      <section id="benchmarks" style={{ padding: '6rem 2rem', borderTop: '1px solid rgba(255,255,255,0.08)', maxWidth: '1280px', margin: '0 auto' }}>
        <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.2em', color: '#ff7a00', marginBottom: '0.5rem' }}>APFD Benchmarks</p>
        <h2 className="font-bebas" style={{ fontSize: '3rem', letterSpacing: '0.05em', textTransform: 'uppercase', margin: '0 0 1rem' }}>CHART-P vs Alternatives</h2>
        <p style={{ color: 'rgba(255,255,255,0.6)', marginBottom: '2.5rem' }}>Average Percentage of Faults Detected across 30 simulated build cycles.</p>
        <div style={{ background: '#141416', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase' }}>
                <th style={{ padding: '1rem 1.5rem' }}>Strategy</th>
                <th style={{ padding: '1rem 1.5rem' }}>APFD Score</th>
                <th style={{ padding: '1rem 1.5rem' }}>Latency</th>
                <th style={{ padding: '1rem 1.5rem' }}>ML Overhead</th>
              </tr>
            </thead>
            <tbody style={{ fontSize: '0.9rem' }}>
              {[
                ['Default Pytest', '51.0%', 'Baseline order', 'None'],
                ['Random Baseline', '50.4%', 'Baseline order', 'None'],
                ['Pure History', '68.6%', 'DB lookup', 'None'],
                ['Pure Change', '79.1%', '< 0.42s', 'None'],
                ['CHART-P', '88.7%', '< 0.42s', 'Zero']
              ].map(([name, score, lat, ml]) => (
                <tr key={name} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: name === 'CHART-P' ? 'rgba(255,85,0,0.1)' : 'transparent' }}>
                  <td style={{ padding: '1.2rem 1.5rem', fontWeight: name === 'CHART-P' ? '700' : '500', color: name === 'CHART-P' ? '#ff7a00' : '#fff' }}>{name}</td>
                  <td style={{ padding: '1.2rem 1.5rem', fontFamily: "'JetBrains Mono', monospace" }}>{score}</td>
                  <td style={{ padding: '1.2rem 1.5rem', fontFamily: "'JetBrains Mono', monospace", color: 'rgba(255,255,255,0.7)' }}>{lat}</td>
                  <td style={{ padding: '1.2rem 1.5rem', fontFamily: "'JetBrains Mono', monospace", color: 'rgba(255,255,255,0.7)' }}>{ml}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Architecture Section ── */}
      <section id="architecture" style={{ padding: '6rem 2rem', borderTop: '1px solid rgba(255,255,255,0.08)', maxWidth: '1280px', margin: '0 auto' }}>
        <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.2em', color: '#ff7a00', marginBottom: '0.5rem' }}>Developer API Inspector</p>
        <h2 className="font-bebas" style={{ fontSize: '3rem', letterSpacing: '0.05em', textTransform: 'uppercase', margin: '0 0 2.5rem' }}>Drop it into any CI step</h2>
        <div style={{ background: '#0f0f11', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '1.8rem', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem', color: '#ff7a00', overflowX: 'auto' }}>
          S(t<sub>i</sub>) = w<sub>c</sub> · C(t<sub>i</sub>) + w<sub>h</sub> · H(t<sub>i</sub>)
        </div>
      </section>

      {/* ── Final CTA Section ── */}
      <section style={{ padding: '7rem 2rem', textAlign: 'center', borderTop: '1px solid rgba(255,255,255,0.08)', position: 'relative', overflow: 'hidden' }}>
        <h2 className="font-bebas" style={{ fontSize: 'clamp(2.5rem, 5vw, 4.5rem)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: '0 0 2rem' }}>Rank your suite in under a second</h2>
        <button
          onClick={onLaunch}
          style={{ background: 'linear-gradient(135deg, #ff5500, #ff7a00)', color: '#fff', border: 'none', borderRadius: '30px', padding: '1rem 2.5rem', fontWeight: '700', fontSize: '1.1rem', cursor: 'pointer', boxShadow: '0 0 36px rgba(255,85,0,0.55)', transition: 'all 0.18s' }}
        >
          Launch Workspace →
        </button>
        <p style={{ fontSize: '0.75rem', fontFamily: "'JetBrains Mono', monospace", color: 'rgba(255,255,255,0.35)', marginTop: '4rem' }}>© 2026 CHART-P</p>
      </section>
    </div>
  );
}

// ── App ────────────────────────────────────────────────────────────────────────
function App() {
  const [tab, setTab]           = useState("ranking");
  const [ranking, setRanking]   = useState(null);
  const [comparison, setComparison] = useState(null);
  const [apfdData, setApfdData] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  // Theme state (dark vs light)
  const [theme, setTheme] = useState(() => localStorage.getItem("chart_p_theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("chart_p_theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === "dark" ? "light" : "dark"));
  };

  // Analyze feature
  const [repoUrl, setRepoUrl]   = useState("");
  const [isCustomRepo, setIsCustomRepo] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  // Dynamic weight state
  const [wc, setWc] = useState(2.0);
  const [wh, setWh] = useState(1.0);

  // Debounce timer ref for slider changes (300ms)
  const weightTimer = useRef(null);

  // ── fetchAll ───────────────────────────────────────────────────
  const fetchAll = useCallback(async (wcVal, whVal) => {
    const wcp = wcVal !== undefined ? wcVal : wc;
    const whp = whVal !== undefined ? whVal : wh;
    setLoading(true);
    setError(null);
    try {
      const [rRes, cRes, aRes] = await Promise.all([
        fetch(`${API_BASE}/api/ranking?w_c=${wcp}&w_h=${whp}`),
        fetch(`${API_BASE}/api/comparison?w_c=${wcp}&w_h=${whp}`),
        fetch(`${API_BASE}/api/apfd-curve?w_c=${wcp}&w_h=${whp}`),
      ]);
      if (!rRes.ok || !cRes.ok || !aRes.ok) throw new Error("API returned an error response");
      const [rData, cData, aData] = await Promise.all([rRes.json(), cRes.json(), aRes.json()]);
      setRanking(rData);
      setComparison(cData);
      setApfdData(aData);
      setLastRefresh(new Date().toLocaleTimeString());
      setIsCustomRepo(false);
    } catch (e) {
      setError(e.message || "Could not reach the API");
    } finally {
      setLoading(false);
    }
  }, [wc, wh]);

  // ── handleAnalyze ──────────────────────────────────────────────
  const handleAnalyze = async (customWc, customWh) => {
    const activeWc = customWc !== undefined ? customWc : wc;
    const activeWh = customWh !== undefined ? customWh : wh;
    if (repoUrl && repoUrl.trim()) {
      const url = repoUrl.trim();
      setAnalyzing(true);
      setError(null);
      // Immediately clear old tables
      setRanking(null);
      setComparison(null);
      try {
        const urlParams = `w_c=${activeWc}&w_h=${activeWh}&repo_url=${encodeURIComponent(url)}`;
        const res = await fetch(`${API_BASE}/api/analyze?w_c=${activeWc}&w_h=${activeWh}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ repo_url: url })
        });
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || "Analysis failed");
        }
        const data = await res.json();
        
        // Fetch APFD Curve for this specific repo
        const apfdRes = await fetch(`${API_BASE}/api/apfd-curve?${urlParams}`);
        if (apfdRes.ok) {
          const aData = await apfdRes.json();
          setApfdData(aData);
        }
        
        setRanking(data);
        setIsCustomRepo(true);

        // Build comparison from returned data
        const beforeList = [...data.tests].sort((a,b) => a.name.localeCompare(b.name)).map(t => t.name);
        const afterList  = data.tests.map(t => t.name);
        const beforePos  = {}; beforeList.forEach((n, i) => { beforePos[n] = i + 1; });
        const afterPos   = {}; afterList.forEach((n, i)  => { afterPos[n]  = i + 1; });

        const comparisonDetail = beforeList.map(name => {
          const t = data.tests.find(x => x.name === name);
          return {
            name,
            before_rank: beforePos[name],
            after_rank:  afterPos[name],
            score:       t ? t.score : 0,
            moved_by:    beforePos[name] - afterPos[name]
          };
        });

        setComparison({ before: beforeList, after: afterList, detail: comparisonDetail });
        setLastRefresh("Repo: " + url.split("/").slice(-1)[0]);
      } catch (e) {
        setError(e.message);
        setIsCustomRepo(false);
        fetchAll();
      } finally {
        setAnalyzing(false);
      }
    }
  };

  // ── Debounced weight slider changes ────────────────────────────
  const triggerRefetch = (newWc, newWh) => {
    clearTimeout(weightTimer.current);
    weightTimer.current = setTimeout(() => {
      if (isCustomRepo) {
        handleAnalyze(newWc, newWh);
      } else {
        fetchAll(newWc, newWh);
      }
    }, 300); // 300ms debounce
  };

  const handleWcChange = (newVal) => {
    setWc(newVal);
    triggerRefetch(newVal, wh);
  };

  const handleWhChange = (newVal) => {
    setWh(newVal);
    triggerRefetch(wc, newVal);
  };

  // ── Mount-only initial load (polling interval removed) ─────────
  useEffect(() => { fetchAll(); }, []); // eslint-disable-line

  const changedFiles = ranking ? ranking.changed_files : [];
  const noPythonFilesEdited = changedFiles && changedFiles.length > 0 && changedFiles.every(f => !f.endsWith('.py'));
  const highPriorityCount = ranking
    ? ranking.tests.filter(t => t.score >= (wc + wh) * 0.75).length
    : 0;
  const showBaselineNotice = noPythonFilesEdited && highPriorityCount === 0;

  const [selectedCopilotTest, setSelectedCopilotTest] = useState(null);
  const [showDashboard, setShowDashboard] = useState(() => location.hash === '#get-started' || location.hash === '#dashboard');

  useEffect(() => {
    const handleHash = () => {
      setShowDashboard(location.hash === '#get-started' || location.hash === '#dashboard');
    };
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const goToDashboard = (e) => {
    if (e) e.preventDefault();
    window.location.hash = '#dashboard';
    setShowDashboard(true);
    window.scrollTo(0, 0);
  };

  const goToLanding = (e) => {
    if (e) e.preventDefault();
    window.location.hash = '#landing';
    setShowDashboard(false);
    window.scrollTo(0, 0);
  };

  if (!showDashboard) {
    return (
      <div className="landing-view-container">
        {/* Render Figma Landing Page Component via window/global or iframe layout */}
        <LandingPageWrapper onLaunch={goToDashboard} />
      </div>
    );
  }

  return (
    <div className="shell">
      {/* ── Copilot Drawer ── */}
      {selectedCopilotTest && (
        <CopilotDrawer
          testItem={selectedCopilotTest}
          changedFiles={ranking ? ranking.changed_files : []}
          wc={wc}
          wh={wh}
          onClose={() => setSelectedCopilotTest(null)}
        />
      )}

      {/* ── Header ── */}
      <header className="header">
        <div className="logo" style={{cursor: 'pointer'}} onClick={goToLanding} title="Back to Landing Page">⚡</div>
        <div className="header-text">
          <h1 className="font-bebas" style={{fontSize: '1.6rem', letterSpacing: '0.05em'}}>Hybrid Test Prioritization Dashboard</h1>
          <p>Continuous Integration Test Optimization Engine</p>
        </div>
        <div style={{marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '1rem'}}>
          <button
            onClick={goToLanding}
            style={{
              background: 'transparent',
              border: '1px solid var(--border2)',
              color: 'var(--text2)',
              borderRadius: '20px',
              padding: '.25rem .75rem',
              fontSize: '.72rem',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all .15s'
            }}
          >
            ← Landing Page
          </button>
          <div className="badge-live">
            <span className="dot" />
            {lastRefresh ? `Updated ${lastRefresh}` : "Connecting…"}
          </div>
        </div>
      </header>

      {/* ── Repository Analysis Form ── */}
      <div className="analyze-bar">
        <div style={{flex:'1', minWidth:'260px'}}>
          <label>Analyze Public GitHub Repository</label>
          <input
            className="analyze-input"
            type="text"
            placeholder="e.g., https://github.com/username/repository"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            disabled={analyzing}
          />
        </div>
        <button
          className="btn-analyze"
          onClick={() => handleAnalyze()}
          disabled={analyzing || !repoUrl.trim()}
        >
          {analyzing ? <><span className="spinner"/>{" "}Analyzing…</> : "Analyze →"}
        </button>
      </div>

      {/* ── Non-Python Warning Banner ── */}
      {showBaselineNotice && (
        <div className="non-python-banner">
          ℹ️ Latest commit modified non-code files (.toml / .md / .rst). Showing failure-history scoring baseline.
        </div>
      )}

      {/* ── Dynamic Weight Tuning Bar ── */}
      <div className="weight-bar">
        <div className="weight-bar-title">Dynamic Weight Tuning Module</div>
        <div className="weight-controls">
          <div className="weight-control">
            <div className="weight-label">
              <span>Change Impact Weight (w_c)</span>
              <span>{wc.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0" max="5" step="0.5"
              value={wc}
              onChange={(e) => handleWcChange(parseFloat(e.target.value))}
            />
          </div>
          <div className="weight-control">
            <div className="weight-label">
              <span>Failure Recency Weight (w_h)</span>
              <span>{wh.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0" max="5" step="0.5"
              value={wh}
              onChange={(e) => handleWhChange(parseFloat(e.target.value))}
            />
          </div>
          <div className="formula-badge">
            Active Weighting: {wc.toFixed(1)} × Change + {wh.toFixed(1)} × Recency
          </div>
        </div>
      </div>

      {/* ── Analyzing overlay ── */}
      {analyzing && (
        <div className="state-box" style={{marginBottom:'1.5rem'}}>
          <div className="icon">⚙️</div>
          <p>Cloning repository, installing dependencies, and running test suite…<br />
            <small>This may take up to 5 minutes for large frameworks.</small>
          </p>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="tabs">
        <button id="tab-ranking" className={`tab ${tab==="ranking"?"active":""}`} onClick={() => setTab("ranking")}>
          📊 Ranked View
        </button>
        <button id="tab-comparison" className={`tab ${tab==="comparison"?"active":""}`} onClick={() => setTab("comparison")}>
          🔀 Before / After
        </button>
        <button id="tab-graph" className={`tab ${tab==="graph"?"active":""}`} onClick={() => setTab("graph")}>
          🕸️ Graph View
        </button>
      </div>

      {/* ── Refresh & Theme row ── */}
      <div style={{display:'flex', justifyContent:'flex-end', gap:'.6rem', marginBottom:'1rem'}}>
        <button className="btn-theme-toggle" onClick={toggleTheme} id="btn-theme-toggle">
          {theme === "dark" ? "☀️ Light Mode" : "🌙 Dark Mode"}
        </button>
        <button className="btn-refresh" onClick={isCustomRepo ? () => handleAnalyze() : () => fetchAll()} id="btn-refresh">
          ↻ Refresh now
        </button>
      </div>

      {/* ── States ── */}
      {loading && !analyzing && (
        <div className="state-box">
          <div className="icon">⏳</div>
          <p>Loading ranking data from the API…</p>
          <small>{API_BASE}</small>
        </div>
      )}

      {!loading && error && !analyzing && (
        <div className="state-box">
          <div className="icon">🔌</div>
          <p>Error in Analysis or API Server Connection.</p>
          <small>Verify API server state or your repository URL details.</small>
          <small style={{marginTop:'.6rem', color:'var(--red)'}}>{error}</small>
        </div>
      )}

      {!loading && !error && ranking && !analyzing && (
        <>
          {tab === "ranking" && (
            <RankingTable
              tests={ranking.tests}
              changedFiles={ranking.changed_files}
              wc={wc}
              wh={wh}
              apfdData={apfdData}
              onExplainTest={(testItem) => setSelectedCopilotTest(testItem)}
            />
          )}
          {tab === "comparison" && comparison && (
            <ComparisonView data={comparison} wc={wc} wh={wh} />
          )}

          {/* Interactive Force-Directed Knowledge Graph */}
          {tab === "graph" && (
            <div style={{marginTop:'2rem'}}>
              <TestGraphView
                tests={ranking.tests}
                changedFiles={ranking.changed_files}
                commitSha={ranking.commit_sha}
                repoName={ranking.repo_name}
                wc={wc}
                wh={wh}
                cooldownTicks={100}
                onEngineStop={() => console.log('Graph physics frozen')}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
