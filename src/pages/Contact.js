import React, { useState } from 'react';
import './Contact.css';

// ── DUMMY DATA — replace these with your real details later ──
const INFO = [
  {
    icon: '📍',
    label: 'University',
    value: 'University of Lahore',
    sub: 'Department of Computer Science & IT',
  },
  {
    icon: '👨‍🏫',
    label: 'Supervisor',
    value: 'Hafiz Ali Younas',
    sub: 'Faculty of Information Technology',
  },
  {
    icon: '📧',
    label: 'Email',
    value: 'team@contractai.com',
    sub: 'We reply within 24 hours',
    href: 'mailto:team@contractai.com',
  },
  {
    icon: '📞',
    label: 'Phone',
    value: '+92 300 0000000',
    sub: 'Mon–Fri, 9am to 5pm',
  },
];

const TEAM = [
  { name: 'Syed Yousaf Raza', role: 'Team Lead' },
  { name: 'Saad Naveed',      role: 'Backend' },
  { name: 'Abdur Rahim',      role: 'Database' },
];

// ── Replace YOUR_FORM_ID with the ID from formspree.io ──
const FORMSPREE_URL = 'https://formspree.io/f/mwvzbzko';

export default function Contact() {
  const [status, setStatus] = useState('idle'); // idle | loading | success | error

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus('loading');
    try {
      const res = await fetch(FORMSPREE_URL, {
        method: 'POST',
        body: new FormData(e.target),
        headers: { Accept: 'application/json' },
      });
      if (res.ok) {
        setStatus('success');
        e.target.reset();
      } else {
        setStatus('error');
      }
    } catch {
      setStatus('error');
    }
  }

  return (
    <div className="contact-page">

      {/* HEADER */}
      <div className="contact-header">
        <span className="contact-tag">Contact Us</span>
        <h1>Get In Touch</h1>
        <p>Have a question about Contract.AI or our FYP? We'd love to hear from you.</p>
      </div>

      <div className="contact-body">

        {/* LEFT — Contact Info */}
        <div className="contact-info">
          <h3>Contact Information</h3>

          {INFO.map((item) => (
            <div className="info-block" key={item.label}>
              <div className="info-icon">{item.icon}</div>
              <div className="info-text">
                <span className="info-label">{item.label}</span>
                {item.href
                  ? <a href={item.href} className="info-value">{item.value}</a>
                  : <p className="info-value">{item.value}</p>
                }
                <span className="info-sub">{item.sub}</span>
              </div>
            </div>
          ))}

          <div className="team-section">
            <span className="info-label">Our Team</span>
            <div className="team-list">
              {TEAM.map((m) => (
                <div className="team-chip" key={m.name}>
                  <div className="team-avatar">
                    {m.name.split(' ').map((w) => w[0]).join('').slice(0, 2)}
                  </div>
                  <div>
                    <strong>{m.name}</strong>
                    <span>{m.role}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT — Form */}
        <div className="contact-form-wrap">

          {status === 'success' ? (
            <div className="success-state">
              <div className="success-icon">✅</div>
              <h3>Message Sent!</h3>
              <p>Thanks for reaching out. We'll get back to you within 24 hours.</p>
              <button className="submit-btn" onClick={() => setStatus('idle')}>
                Send Another Message
              </button>
            </div>
          ) : (
            <>
              <div className="form-header">
                <h2>Send a Message</h2>
                <p>Fill in the form below and we'll get back to you soon.</p>
              </div>

              <form onSubmit={handleSubmit} noValidate>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="name">Full Name</label>
                    <input
                      id="name"
                      name="name"
                      type="text"
                      placeholder="e.g. Ali Raza"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="email">Email Address</label>
                    <input
                      id="email"
                      name="email"
                      type="email"
                      placeholder="e.g. ali@example.com"
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="subject">Subject</label>
                  <input
                    id="subject"
                    name="subject"
                    type="text"
                    placeholder="e.g. Feedback on Contract.AI"
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="message">Message</label>
                  <textarea
                    id="message"
                    name="message"
                    rows={5}
                    placeholder="Write your message here..."
                    required
                  />
                </div>

                {status === 'error' && (
                  <p className="error-msg">
                    ⚠️ Something went wrong. Please try again or email us directly.
                  </p>
                )}

                <button
                  type="submit"
                  className="submit-btn"
                  disabled={status === 'loading'}
                >
                  {status === 'loading'
                    ? <><span className="spinner" /> Sending…</>
                    : 'Send Message →'
                  }
                </button>

                <p className="form-note">
                  🔒 Your info is private and only used to respond to your message.
                </p>
              </form>
            </>
          )}
        </div>

      </div>
    </div>
  );
}