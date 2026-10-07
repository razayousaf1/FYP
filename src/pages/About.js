import React from 'react';
import './About.css';

function TeamCard({ name, id, email }) {
  return (
    <div className="team-card">
      <div className="avatar">{name.split(' ').map(w => w[0]).join('').slice(0, 2)}</div>
      <h3>{name}</h3>
      <span className="student-id">ID: {id}</span>
      <a href={`mailto:${email}`} className="student-email">{email}</a>
    </div>
  );
}

function TimelineItem({ phase, duration, title, items, active }) {
  return (
    <div className={`timeline-item ${active ? 'active' : ''}`}>
      <div className="tl-left">
        <div className="tl-badge">Phase {phase}</div>
        <div className="tl-duration">{duration}</div>
      </div>
      <div className="tl-dot-col">
        <div className="tl-dot" />
        <div className="tl-line" />
      </div>
      <div className="tl-right">
        <h4>{title}</h4>
        <ul>
          {items.map(it => <li key={it}>{it}</li>)}
        </ul>
      </div>
    </div>
  );
}

export default function About() {
  return (
    <>
      {/* ── PAGE HEADER ── */}
      <div className="about-header">
        <div className="about-header-inner">
          <div className="section-tag">About the Project</div>
          <h1>Contract.AI</h1>
          <p>A Final Year Project by the University of Lahore, Department of Computer Science & IT, designed to make Pakistani legal documents accessible to everyone.</p>
        </div>
      </div>

      {/* ── PROBLEM ── */}
      <section className="about-section">
        <div className="about-inner two-col">
          <div>
            <div className="section-tag">The Problem</div>
            <div className="section-title">Why This Project Exists</div>
            <p className="body-text">
              In Pakistan, a large number of legal documents — rental agreements, affidavits, service contracts,
              and freelance agreements — are written in complex Urdu. Most individuals, including tenants,
              freelancers, and small business owners, lack the legal expertise to understand what they're signing.
            </p>
            <p className="body-text" style={{ marginTop: 12 }}>
              Existing tools like Google Lens or Google Translate provide only literal translations —
              they do not identify unfair or risky terms, and they don't explain legal implications
              in a way ordinary people can understand.
            </p>
          </div>
          <div className="problem-cards">
            {[
              { icon: '📝', title: 'Complex Urdu', desc: 'Legal documents use formal Urdu that most people can\'t read or understand.' },
              { icon: '💸', title: 'Hidden Penalties', desc: 'Jurmana (penalty) clauses are buried in dense text and easy to miss.' },
              { icon: '❌', title: 'No Localized Tool', desc: 'No existing AI tool focuses on Pakistani legal documents in Urdu.' },
            ].map(c => (
              <div key={c.title} className="problem-card">
                <span className="problem-icon">{c.icon}</span>
                <div>
                  <strong>{c.title}</strong>
                  <p>{c.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── SOLUTION ── */}
      <section className="about-section bg-green-pale">
        <div className="about-inner">
          <div className="centered">
            <div className="section-tag">Our Solution</div>
            <div className="section-title">What Contract.AI Does</div>
            <p className="section-sub" style={{ margin: '0 auto 40px' }}>
              A single platform that reads, translates, and risk-flags Urdu legal documents for everyday Pakistanis.
            </p>
          </div>
          <div className="solution-grid">
            {[
              { icon: '📤', title: 'Upload Any Format', desc: 'PDF, image, scanned document — our system accepts all common formats.' },
              { icon: '🔍', title: 'OCR Text Extraction', desc: 'Optical Character Recognition pulls out Urdu text from even scanned pages.' },
              { icon: '🔄', title: 'Roman Urdu Output', desc: 'Full transliteration into Roman Urdu so anyone can read it — no Urdu script needed.' },
              { icon: '⚠️', title: 'Risk Detection', desc: 'Flags jurmana (penalties), raqam (amounts), and other high-risk legal clauses.' },
              { icon: '💬', title: 'Plain Explanations', desc: 'Each flagged term gets a simple Roman Urdu explanation of what it means for you.' },
              { icon: '🔒', title: 'Privacy Focused', desc: 'Documents are processed securely and never stored permanently.' },
            ].map(s => (
              <div key={s.title} className="solution-card">
                <div className="sol-icon">{s.icon}</div>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TECH STACK ── */}
      <section className="about-section">
        <div className="about-inner">
          <div className="centered">
            <div className="section-tag">Technology</div>
            <div className="section-title">Tech Stack</div>
            <p className="section-sub" style={{ margin: '0 auto 40px' }}>Built with modern, open-source technologies for scalability and performance.</p>
          </div>
          <div className="tech-grid">
            {[
              { layer: 'Frontend', color: 'blue', items: ['React.js', 'React Router DOM', 'CSS'] },
              { layer: 'Backend', color: 'green', items: ['Python', 'Google Cloud Functions', 'REST APIs'] },
              { layer: 'OCR / NLP', color: 'yellow', items: ['Google Cloud Vision API', 'Hugging Face Transformers', 'spaCy / NLTK'] },
              { layer: 'AI / ML', color: 'red', items: ['Firebase Firestore', 'Firebase Storage', 'Firebase Anonymous Auth'] },
            ].map(t => (
              <div key={t.layer} className={`tech-card tc-${t.color}`}>
                <div className="tech-layer">{t.layer}</div>
                <ul>
                  {t.items.map(i => <li key={i}>{i}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TIMELINE ── */}
      <section className="about-section bg-green-pale">
        <div className="about-inner">
          <div className="centered">
            <div className="section-tag">Implementation Plan</div>
            <div className="section-title">Project Timeline</div>
            <p className="section-sub" style={{ margin: '0 auto 40px' }}>8-month roadmap from design to deployment.</p>
          </div>
          <div className="timeline">
            <TimelineItem phase={1} duration="Month 1" active title="Requirement Analysis & UI Design (Current)"
              items={['Requirement gathering', 'System design', 'UI wireframes & frontend', 'Dataset planning']} />
            <TimelineItem phase={2} duration="Month 2–3" title="Frontend Development"
              items={['React.js components', 'Document upload UI', 'Clause display layout', 'Risk highlighting UI']} />
            <TimelineItem phase={3} duration="Month 4–5" title="Backend & OCR Integration"
              items={['Backend API setup', 'OCR module integration', 'Transliteration module', 'Text pre-processing']} />
            <TimelineItem phase={4} duration="Month 6–7" title="AI Risk Analysis"
              items={['Risk classifier model', 'Database setup', 'API integration', 'Frontend–backend linking']} />
            <TimelineItem phase={5} duration="Month 8" title="Testing & Deployment"
              items={['End-to-end testing', 'Performance optimization', 'Documentation', 'Final deployment']} />
          </div>
        </div>
      </section>

      {/* ── TEAM ── */}
      <section className="about-section">
        <div className="about-inner">
          <div className="centered">
            <div className="section-tag">The Team</div>
            <div className="section-title">Meet the Developers</div>
            <p className="section-sub" style={{ margin: '0 auto 40px' }}>Final Year Project students at the University of Lahore.</p>
          </div>
          <div className="team-grid">
            <TeamCard name="Syed Yousaf Raza"  id="70139122" email="70139122@student.uol.edu.pk" />
            <TeamCard name="Saad Naveed"        id="70137375" email="70137375@student.uol.edu.pk" />
            <TeamCard name="Abdur Rahim"        id="70135511" email="70135511@student.uol.edu.pk" />
          </div>
          <div className="supervisor-card">
            <div className="sup-label">Project Supervisor</div>
            <div className="sup-name">Hafiz Ali Younas</div>
            <div className="sup-dept">Department of Computer Science & IT · Faculty of Information Technology · University of Lahore</div>
          </div>
        </div>
      </section>
    </>
  );
}