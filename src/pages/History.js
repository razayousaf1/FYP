import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getOrCreateSessionId } from '../utils/session';
import './History.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function timeAgo(unixSeconds) {
  const seconds = Math.floor(Date.now() / 1000 - unixSeconds);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function HistoryCard({ record }) {
  const { risk_summary, term_summary, clause_count, created_at } = record;
  return (
    <div className="history-card">
      <div className="history-card-head">
        <span className="history-time">{timeAgo(created_at)}</span>
        <span className="history-clause-count">{clause_count} clause{clause_count === 1 ? '' : 's'} analyzed</span>
      </div>
      <div className="history-counts">
        <span className="hcount hcount-high">🔴 {risk_summary.high || 0} High Risk</span>
        <span className="hcount hcount-verify">🟡 {risk_summary.verify || 0} Verify</span>
        <span className="hcount hcount-note">🔵 {risk_summary.note || 0} Note</span>
      </div>
      {term_summary.total > 0 && (
        <div className="history-terms">
          {term_summary.total} risk term{term_summary.total === 1 ? '' : 's'} detected
          {Object.keys(term_summary.by_category || {}).length > 0 && (
            <span className="history-categories">
              {' '}({Object.entries(term_summary.by_category).map(([cat, n]) => `${cat}: ${n}`).join(', ')})
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export default function History() {
  const [records, setRecords] = useState(null); // null = loading, [] = loaded-empty
  const [error, setError] = useState('');

  useEffect(() => {
    const sessionId = getOrCreateSessionId();

    fetch(`${API_BASE}/history?session_id=${encodeURIComponent(sessionId)}`)
      .then(res => {
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        return res.json();
      })
      .then(data => setRecords(data.records))
      .catch(err => {
        setError('Could not reach the backend. Make sure it is running at ' + API_BASE + '.');
        setRecords([]);
      });
  }, []);

  return (
    <div className="history-page">
      <div className="history-header">
        <span className="history-tag">Your Activity</span>
        <h1>Recent Analysis History</h1>
        <p>
          Documents you've analyzed in this browser over the last hour. After that,
          results are no longer shown here and the underlying record is deleted -
          see our privacy note below.
        </p>
      </div>

      <div className="history-body">
        {records === null && <p className="history-loading">Loading…</p>}

        {error && <div className="history-error">⚠️ {error}</div>}

        {records !== null && records.length === 0 && !error && (
          <div className="history-empty">
            <div className="history-empty-icon">🕐</div>
            <h3>No recent analyses</h3>
            <p>Documents you analyze will show up here for up to 1 hour.</p>
            <Link to="/" className="history-cta">Analyze a Document →</Link>
          </div>
        )}

        {records && records.length > 0 && (
          <div className="history-list">
            {records.map(r => <HistoryCard key={r.record_id} record={r} />)}
          </div>
        )}
      </div>

      <div className="history-disclaimer">
        <span>🔒</span>
        <p>
          <strong>Privacy note:</strong> we only store a summary of each analysis
          (risk counts, not your document or its extracted text), tied to a random
          ID in your browser - not your identity. Summaries are hidden from view
          after 1 hour and the underlying record is deleted from our database.
        </p>
      </div>
    </div>
  );
}