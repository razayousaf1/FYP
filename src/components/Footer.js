import React from 'react';
import { Link } from 'react-router-dom';
import './Footer.css';

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <div className="footer-logo">
            <span className="logo-box">C</span>
            Contract.AI
          </div>
          <p>Smart Urdu legal document analyzer built for Pakistan. FYP Phase 1 – University of Lahore.</p>
        </div>

        <div className="footer-col">
          <h4>Pages</h4>
          <Link to="/">Home</Link>
          <Link to="/about">About</Link>
          <Link to="/contact">Contact</Link>
        </div>

        <div className="footer-col">
          <h4>Team</h4>
          <span>Syed Yousaf Raza</span>
          <span>Saad Naveed</span>
          <span>Abdur Rahim</span>
        </div>

        <div className="footer-col">
          <h4>Supervisor</h4>
          <span>Hafiz Ali Younas</span>
          <span style={{marginTop: 12}}>Department of CS & IT</span>
          <span>Faculty of IT – UOL</span>
        </div>
      </div>
      <div className="footer-bottom">
        © 2025 Contract.AI · University of Lahore Final Year Project
      </div>
    </footer>
  );
}