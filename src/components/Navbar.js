import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import './Navbar.css';

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="navbar">
      <NavLink to="/" className="nav-logo" onClick={() => setOpen(false)}>
        <span className="logo-box">C</span>
        Contract.AI
      </NavLink>

      <ul className={`nav-links ${open ? 'open' : ''}`}>
        <li><NavLink to="/" end onClick={() => setOpen(false)}>Home</NavLink></li>
        <li><NavLink to="/about" onClick={() => setOpen(false)}>About</NavLink></li>
        <li><NavLink to="/contact" onClick={() => setOpen(false)}>Contact</NavLink></li>
        <li><NavLink to="/history" onClick={() => setOpen(false)}>History</NavLink></li>
        <li>
          <NavLink to="/" className="nav-cta" onClick={() => setOpen(false)}>
            Analyze Document
          </NavLink>
        </li>
      </ul>

      <button className="hamburger" onClick={() => setOpen(!open)} aria-label="Toggle menu">
        <span /><span /><span />
      </button>
    </nav>
  );
}