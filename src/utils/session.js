// Generates (or retrieves) a random session ID stored in the browser's
// localStorage. This is NOT authentication - no login, no identity
// verification, nothing server-side to trust it against. It's purely a
// throwaway tag so the backend can group a browser's own analysis
// history together. See backend/shared/history_store.py's docstring for
// the full reasoning on why this is a deliberate, simpler substitute for
// Firebase Anonymous Auth rather than an oversight.
const SESSION_ID_KEY = 'contractai_session_id';

export function getOrCreateSessionId() {
  let sessionId = localStorage.getItem(SESSION_ID_KEY);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_ID_KEY, sessionId);
  }
  return sessionId;
}