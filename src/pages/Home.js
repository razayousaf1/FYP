import React, { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { getOrCreateSessionId } from '../utils/session';
import './Home.css';

// Backend URL - change this if you deploy the backend somewhere other than localhost.
const API_BASE = 'http://localhost:8000';

/* ── small sub-components ── */

function StepCard({ num, icon, title, desc }) {
  return (
    <div className="step-card">
      <div className="step-num">{num}</div>
      <div className="step-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </div>
  );
}

function FeatureCard({ icon, title, desc, accent }) {
  return (
    <div className={`feature-card accent-${accent}`}>
      <div className={`feat-icon-wrap wrap-${accent}`}>{icon}</div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </div>
  );
}

function RiskItem({ level, urdu, roman, explanation }) {
  const badgeText = level === 'high' ? 'High Risk' : level === 'verify' ? 'Verify' : 'Note';
  return (
    <div className={`risk-item risk-${level}`}>
      <div className="risk-dot" />
      <div>
        <div className="risk-term">
          <span className="risk-urdu">{urdu}</span>
          <span className="risk-roman">({roman})</span>
          <span className={`risk-badge badge-${level}`}>{badgeText}</span>
        </div>
        <p className="risk-explain">{explanation}</p>
      </div>
    </div>
  );
}

/* ── DEMO TAB CONTENT (unchanged - used by the "See Demo" section below, not the real upload flow) ── */
const DEMO_TABS = ['Original Urdu', 'Roman Urdu', 'Risk Report'];

function DemoOriginal() {
  return (
    <div className="demo-doc">
      <div className="demo-doc-label">📄 kiraya_naama_sample.pdf — Extracted & Highlighted</div>
      <div className="demo-urdu">
        یہ کرایہ نامہ{' '}
        <span className="h-blue">یکم مارچ دو ہزار پچیس</span>{' '}کو طے پایا۔<br />
        کرایہ دار ماہانہ{' '}
        <span className="h-yellow">پچاس ہزار روپے (50,000)</span>{' '}ادا کرے گا۔<br />
        تاخیر کی صورت میں{' '}
        <span className="h-red">جرمانہ دس فیصد</span>{' '}لاگو ہوگا۔<br />
        مالک مکان معاہدہ{' '}
        <span className="h-red">فوری طور پر ختم</span>{' '}کر سکتا ہے۔<br />
        تنازعات کی صورت میں{' '}
        <span className="h-blue">لاہور کی عدالت</span>{' '}کا اختیار ہوگا۔
      </div>
      <div className="demo-legend">
        <span><span className="leg-dot dot-red" /> Penalty / Jurmana</span>
        <span><span className="leg-dot dot-yellow" /> Financial Amount</span>
        <span><span className="leg-dot dot-blue" /> Date / Jurisdiction</span>
      </div>
    </div>
  );
}

function DemoRoman() {
  return (
    <div className="demo-doc">
      <div className="demo-doc-label">🔤 Roman Urdu — Accessible Translation</div>
      <p className="roman-text">
        Yeh kiraya naama <strong>yakam March do hazar pachees</strong> ko tay paya.<br />
        Kiraya dar mahana <strong>pachaas hazar rupay (50,000)</strong> ada kare ga.<br />
        Takheer ki sorat mein <strong className="text-red">jurmana das fisad</strong> laagu hoga.<br />
        Maalik makaan muahida <strong className="text-red">fori tor par khatam</strong> kar sakta hai.<br />
        Tanazaat ki sorat mein <strong>Lahore ki adalat</strong> ka ikhtiyar hoga.
      </p>
    </div>
  );
}

function DemoRisks() {
  return (
    <div className="risk-cards-grid">
      <div className="exp-card">
        <div className="exp-tag tag-red">🔴 High Risk</div>
        <h4>Jurmana Das Fisad (10% Penalty)</h4>
        <p>A 10% late payment penalty is very high. Try to negotiate this down or ask for a grace period before the penalty kicks in.</p>
      </div>
      <div className="exp-card">
        <div className="exp-tag tag-red">🔴 High Risk</div>
        <h4>Fori Khatam (Immediate Termination)</h4>
        <p>The landlord can end the agreement at any time without notice. This is unfair — request a 30-day notice clause before signing.</p>
      </div>
      <div className="exp-card">
        <div className="exp-tag tag-yellow">🟡 Verify</div>
        <h4>Pachaas Hazar Rupay (Rs. 50,000)</h4>
        <p>Monthly rent is clearly stated. Confirm this matches what was verbally agreed before you sign the document.</p>
      </div>
      <div className="exp-card">
        <div className="exp-tag tag-blue">🔵 Note</div>
        <h4>Lahore Ki Adalat (Lahore Court)</h4>
        <p>Any disputes will go to Lahore courts. If you live elsewhere, this could be costly and inconvenient for you.</p>
      </div>
    </div>
  );
}

/* ── Renders a clause's Urdu text with FR-05/FR-08 term-level highlights,
   using the character offsets returned by the backend for each detected
   term. Falls back to plain unhighlighted text if a clause has no terms. ── */
   function renderHighlightedText(text, terms) {
    if (!terms || terms.length === 0) {
      return text;
    }
    const sorted = [...terms].sort((a, b) => a.start - b.start);
    const colorClass = { red: 'h-red', yellow: 'h-yellow', blue: 'h-blue' };
    const parts = [];
    let cursor = 0;
  
    sorted.forEach((term, i) => {
      if (term.start > cursor) {
        parts.push(<React.Fragment key={`plain-${i}`}>{text.slice(cursor, term.start)}</React.Fragment>);
      }
      parts.push(
        <span key={`term-${i}`} className={colorClass[term.color] || ''} title={term.category}>
          {text.slice(term.start, term.end)}
        </span>
      );
      cursor = Math.max(cursor, term.end);
    });
  
    if (cursor < text.length) {
      parts.push(<React.Fragment key="plain-end">{text.slice(cursor)}</React.Fragment>);
    }
    return parts;
  }



/* ── MAIN HOME COMPONENT ── */
export default function Home() {
  const [file, setFile] = useState(null);
  const [fileName, setFileName] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [showResult, setShowResult] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const fileRef = useRef();

  function handleFile(selectedFile) {
    if (selectedFile) {
      setFile(selectedFile);
      setFileName(selectedFile.name);
      setError('');
      setShowResult(false);
    }
  }

  async function handleAnalyze(e) {
    e.preventDefault();
    e.stopPropagation();

    if (!file) {
      setError('Please choose a document first.');
      return;
    }

    setAnalyzing(true);
    setShowResult(false);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', getOrCreateSessionId());

      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned an error (status ${response.status}).`);
      }

      const data = await response.json();
      setResult(data);
      setShowResult(true);
      setTimeout(() => {
        document.getElementById('result-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    } catch (err) {
      if (err.message === 'Failed to fetch') {
        setError('Could not reach the backend. Make sure it is running at ' + API_BASE + '.');
      } else {
        setError(err.message);
      }
    } finally {
      setAnalyzing(false);
    }
  }

  const riskyClauses = result ? result.clauses.filter(c => c.level !== 'note') : [];

  // FR-05: flatten every clause's term-level detections into one list,
  // separate from the clause-level riskyClauses list above.
  const allTerms = result ? result.clauses.flatMap(c => c.terms || []) : [];

  const CATEGORY_LABELS = {
    financial_amount: 'Financial Amount (Raqam)',
    penalty: 'Penalty (Jurmana)',
    termination: 'Termination',
    jurisdiction: 'Jurisdiction (Adalat)',
    date: 'Date',
  };
  const CATEGORY_ICONS = {
    financial_amount: '💰',
    penalty: '⚠️',
    termination: '🚫',
    jurisdiction: '🏛️',
    date: '📅',
  };

  return (
    <>
      {/* ── HERO ── */}
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-text">
            <div className="hero-badge">🇵🇰 Built for Pakistani Legal Documents</div>
            <h1>Understand Your <span className="green-text">Urdu Contracts</span><br />Before You Sign</h1>
            <p>
              Upload any Urdu legal document — rental agreements, business contracts, affidavits —
              and instantly get risk highlights and simplified Roman Urdu explanations.
            </p>
            <div className="hero-btns">
              <a href="#upload-section" className="btn btn-green">Upload Document ↓</a>
              <a href="#demo-section" className="btn btn-outline">See Demo</a>
            </div>
          </div>

          <div className="hero-card">
            <div className="hero-card-head">
              <span className="dot red" /><span className="dot yellow" /><span className="dot green-dot" />
              <span className="file-name-label">kiraya_naama.pdf</span>
            </div>
            <div className="hero-urdu">
              کرایہ دار کو{' '}
              <span className="h-red">جرمانہ</span>{' '}
              ادا کرنا ہوگا۔ ماہانہ کرایہ{' '}
              <span className="h-yellow">پچاس ہزار روپے</span>{' '}
              مقرر کیا گیا ہے۔
            </div>
            <div className="hero-roman-row">
              <span className="roman-label">Roman Urdu</span>
              <span>Kiraya dar ko <strong>jurmana</strong> ada karna hoga. Mahana kiraya <strong>pachaas hazar rupay</strong> muqarrar kiya gaya hai.</span>
            </div>
            <div className="hero-pills">
              <span className="pill pill-red">⚠ Jurmana (Penalty)</span>
              <span className="pill pill-yellow">💰 Pachaas Hazar Rupay</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── STEPS ── */}
      <section className="steps-section">
        <div className="centered-header">
          <div className="section-tag">How It Works</div>
          <div className="section-title">4 Simple Steps</div>
          <div className="section-sub">From a scanned Urdu document to a clear risk-highlighted summary in seconds.</div>
        </div>
        <div className="steps-grid">
          <StepCard num="1" icon="📤" title="Upload Document" desc="Upload a PDF, image, or scanned copy of your Urdu legal document." />
          <StepCard num="2" icon="🔍" title="OCR Extraction" desc="Our engine extracts all Urdu text, even from handwritten or scanned pages." />
          <StepCard num="3" icon="⚠️" title="Risk Detection" desc="AI flags penalties (jurmana), financial amounts (raqam), and unfair clauses." />
          <StepCard num="4" icon="✅" title="Roman Urdu Output" desc="Get a plain-language Roman Urdu explanation you can actually read and understand." />
        </div>
      </section>

      {/* ── UPLOAD ── */}
      <section className="upload-section" id="upload-section">
        <div className="upload-inner">
          <div className="centered-header">
            <div className="section-tag">Find Your Legal Clause</div>
            <div className="section-title">Analyze Your Document</div>
            <div className="section-sub">Upload a legal document in Urdu and see risk highlights and Roman Urdu explanations instantly.</div>
          </div>

          <div className="upload-grid">
            {/* LEFT: drop zone */}
            <div>
              <div
                className={`drop-zone ${dragOver ? 'drag-active' : ''}`}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
                onClick={() => fileRef.current.click()}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.docx"
                  style={{ display: 'none' }}
                  onChange={e => handleFile(e.target.files[0])}
                />
                <div className="dz-icon">📂</div>
                <h3>{fileName || 'Drop your document here'}</h3>
                <p>{fileName ? 'File selected — click Analyze below' : 'or click to browse files'}</p>
                <div className="file-badges">
                  {['PDF', 'PNG', 'JPG', 'DOCX', 'Scanned'].map(t => (
                    <span key={t} className="file-badge">{t}</span>
                  ))}
                </div>
              </div>

              <button className="analyze-btn" onClick={handleAnalyze} disabled={analyzing}>
                {analyzing
                  ? <><span className="spinner" /> Analyzing…</>
                  : <><span>🔎</span> Analyze Document</>
                }
              </button>
              {analyzing && <div className="loading-bar" style={{ marginTop: 8, borderRadius: 4 }} />}

              {error && (
                <div
                  style={{
                    marginTop: 12,
                    padding: '12px 16px',
                    background: '#fee2e2',
                    color: '#b91c1c',
                    borderRadius: 8,
                    fontSize: 14,
                    lineHeight: 1.5,
                  }}
                >
                  ⚠️ {error}
                </div>
              )}
            </div>

            {/* RIGHT: tips */}
            <div className="tips-box">
              <h4>⚡ Common Risk Terms to Watch</h4>
              {[
                { icon: '💸', term: 'Raqam / رقم (Amount)', desc: 'Any financial figure. Always verify amounts match what was verbally agreed.' },
                { icon: '⚠️', term: 'Jurmana / جرمانہ (Penalty)', desc: 'Fines or penalties for breaking agreement terms. Negotiate or remove if unfair.' },
                { icon: '📅', term: 'Miaad / میعاد (Duration)', desc: 'Contract duration and renewal terms that could lock you in long-term.' },
                { icon: '🏛️', term: 'Adalat / عدالت (Court)', desc: 'Which court handles disputes — could be far from where you live.' },
              ].map(t => (
                <div key={t.term} className="tip-row">
                  <span className="tip-icon">{t.icon}</span>
                  <div>
                    <strong>{t.term}</strong>
                    <span>{t.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* RESULT — now driven by the real backend response */}
          {showResult && result && (
            <div className="result-area" id="result-anchor">
              <div className="result-success-bar">
                {riskyClauses.length > 0
                  ? <>✅ Analysis complete — <strong>{riskyClauses.length} risky {riskyClauses.length === 1 ? 'clause' : 'clauses'} detected</strong> in your document</>
                  : <>✅ Analysis complete — no high-risk or warning clauses detected</>
                }
              </div>

              <div className="result-grid">
                <div className="result-block">
                  <div className="result-block-head">📝 Extracted Urdu Text</div>
                  <div className="demo-urdu" style={{ padding: '16px' }}>
                    {result.clauses.map((c, i) => (
                      <React.Fragment key={i}>
                        {renderHighlightedText(c.urdu, c.terms)}{' '}
                        </React.Fragment>
                    ))}
                  </div>
                </div>

                <div className="result-block">
                  <div className="result-block-head">🔤 Roman Urdu Translation</div>
                  <p className="roman-text" style={{ padding: '16px' }}>
                    {result.clauses.map(c => c.roman).join(' ')}
                  </p>
                </div>
              </div>

              <div className="result-block risk-block">
                <div className="result-block-head" style={{ color: 'var(--red)' }}>⚠️ Risky Terms Detected</div>
                {riskyClauses.length === 0 && (
                  <p style={{ padding: '16px', color: '#666' }}>
                    No high-risk or warning clauses were detected in this document.
                  </p>
                )}
                {riskyClauses.map((c, i) => (
                  <RiskItem
                    key={i}
                    level={c.level === 'high' ? 'high' : 'verify'}
                    urdu={c.category || c.urdu}
                    roman={c.roman}
                    explanation={c.confidence_note ? `${c.explanation} (${c.confidence_note})` : c.explanation}
                  />
                ))}
              </div>

              {/* FR-05: specific risk terms (penalty/financial/termination/jurisdiction/date),
                  separate from the clause-level list above. Reuses the exp-card/tag-{color}
                  styling already defined for the Live Demo section. */}
              <div className="result-block risk-block">
                <div className="result-block-head">🏷️ Detected Risk Terms</div>
                {allTerms.length === 0 && (
                  <p style={{ padding: '16px', color: '#666' }}>
                    No specific risk terms (penalty, financial amount, termination, jurisdiction, or date) were detected.
                  </p>
                )}
                {allTerms.length > 0 && (
                  <div className="risk-cards-grid" style={{ padding: '16px' }}>
                    {allTerms.map((t, i) => (
                      <div key={i} className="exp-card">
                        <div className={`exp-tag tag-${t.color}`}>
                          {CATEGORY_ICONS[t.category] || '🔎'} {CATEGORY_LABELS[t.category] || t.category}
                        </div>
                        <h4>{t.text}</h4>
                        <p>{t.risk_level}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <p style={{ fontSize: 12, color: '#888', marginTop: 16, padding: '0 16px' }}>
                {result.disclaimer}
              </p>

              <p style={{ fontSize: 12, color: '#888', marginTop: 16, padding: '0 16px' }}>
                {result.disclaimer}
              </p>
            </div>
          )}
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section className="features-section">
        <div className="features-inner">
          <div className="centered-header">
            <div className="section-tag">Features</div>
            <div className="section-title">Everything You Need</div>
            <div className="section-sub">Built specifically for Pakistani legal documents — Urdu first, risk-aware, and accessible to everyone.</div>
          </div>
          <div className="features-grid">
            <FeatureCard accent="green" icon="📷" title="OCR for Scanned Docs" desc="Upload photos or scans of physical documents. Our OCR accurately extracts Urdu text, including printed and typed content." />
            <FeatureCard accent="red"   icon="🚨" title="Risk Term Highlighting" desc="Automatically flags penalties, financial amounts, forfeitures, and unfair legal repercussions with color-coded highlights." />
            <FeatureCard accent="yellow" icon="🔄" title="Roman Urdu Transliteration" desc="Full document converted to Roman Urdu so anyone can read it without knowing the Urdu script." />
            <FeatureCard accent="green" icon="📝" title="Plain-Language Explanations" desc="Each risky clause gets a simple, jargon-free explanation so you know exactly what you're agreeing to." />
            <FeatureCard accent="red"   icon="📄" title="Multiple Document Types" desc="Supports rental agreements (kiraya naama), business contracts, affidavits, freelance agreements, and more." />
            <FeatureCard accent="yellow" icon="🔒" title="Privacy First" desc="Documents are processed securely. Your legal documents remain private and are not stored permanently." />
          </div>
        </div>
      </section>

      {/* ── DEMO ── */}
      <section className="demo-section" id="demo-section">
        <div className="demo-inner">
          <div className="centered-header">
            <div className="section-tag">Live Demo</div>
            <div className="section-title">See It In Action</div>
            <div className="section-sub">Example output from a sample Urdu rental agreement.</div>
          </div>

          <div className="demo-tabs">
            {DEMO_TABS.map((t, i) => (
              <button key={t} className={`demo-tab ${activeTab === i ? 'active' : ''}`} onClick={() => setActiveTab(i)}>
                {t}
              </button>
            ))}
          </div>

          <div className="demo-pane">
            {activeTab === 0 && <DemoOriginal />}
            {activeTab === 1 && <DemoRoman />}
            {activeTab === 2 && <DemoRisks />}
          </div>
        </div>
      </section>

      {/* ── WHO IS IT FOR ── */}
      <section className="usecases-section">
        <div className="usecases-inner">
          <div className="centered-header">
            <div className="section-tag">Use Cases</div>
            <div className="section-title">Who Uses Contract.AI?</div>
            <div className="section-sub">Designed for everyday Pakistanis who deal with legal documents without legal expertise.</div>
          </div>
          <div className="uc-grid">
            {[
              { icon: '🏠', title: 'Tenants & Landlords', items: ['Rental agreements (Kiraya Naama)', 'Penalty & deposit clauses', 'Termination conditions', 'Rent increase terms'] },
              { icon: '💻', title: 'Freelancers & Clients', items: ['Service agreements', 'Payment terms', 'Intellectual property clauses', 'Dispute resolution'] },
              { icon: '🏪', title: 'Small Business Owners', items: ['Supplier agreements', 'Partnership terms', 'Liability clauses', 'Non-compete conditions'] },
            ].map(uc => (
              <div key={uc.title} className="uc-card">
                <div className="uc-icon">{uc.icon}</div>
                <h3>{uc.title}</h3>
                <ul>
                  {uc.items.map(item => <li key={item}>{item}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="cta-section">
        <div className="cta-inner">
          <h2>Ready to Understand Your Contract?</h2>
          <p>Upload your document now — it only takes a few seconds.</p>
          <a href="#upload-section" className="btn btn-green" style={{ fontSize: 16, padding: '13px 32px' }}>
            Analyze a Document →
          </a>
        </div>
      </section>

      {/* ── DISCLAIMER ── */}
      <div className="disclaimer">
        <span>ℹ️</span>
        <p><strong>Disclaimer:</strong> Contract.AI is an informational tool to help you understand documents. It does not provide legal advice. For important agreements, always consult a qualified legal professional.</p>
      </div>
    </>
  );
}