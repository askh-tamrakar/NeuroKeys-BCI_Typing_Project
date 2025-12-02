import React, { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../hooks/useWebSocket'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import LiveView from '../views/LiveView'
import CommandVisualizer from '../views/CommandVisualizer'
import RecordingsView from '../views/RecordingsView'
import DevicesView from '../views/DevicesView'
import ChatView from '../views/ChatView'
import MockView from '../views/MockView'
import SettingsView from '../views/SettingsView'
import TestView from '../views/TestView'

import './App.css';
import { encryptText, bytesToBase64 } from './crypto';
import themePresets from './themes/presets';
import ScrollStack, { ScrollStackItem } from './components/ScrollStack';
import PillNav from './components/PillNav';
import Pill from './components/Pill';
import AuthModal from './components/Auth/AuthModal';
import EncryptText from './components/EncryptText';

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [currentPage, setCurrentPage] = useState('live')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { status, lastMessage, latency, connect, disconnect } = useWebSocket(
    import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
  )
  const [theme, setTheme] = React.useState(() => localStorage.getItem('theme') || 'theme-violet');
  const [navColors, setNavColors] = React.useState({ base: '#000000', pill: '#ffffff', pillText: '#000000', hoverText: '#ffffff' });

  // Theme management
  React.useEffect(() => {
    const root = document.documentElement;
    const existing = Array.from(root.classList).filter(c => c.startsWith('theme-'));
    if (existing.length) root.classList.remove(...existing);
    root.classList.add(theme);
    localStorage.setItem('theme', theme);

    const cs = getComputedStyle(root);
    const accent = cs.getPropertyValue('--accent').trim() || '#121212';
    const text = cs.getPropertyValue('--text').trim() || '#ffffff';
    setNavColors({ base: accent, pill: text, pillText: accent, hoverText: text });
  }, [theme]);


  useEffect(() => {
    connect()
  }, [])
  
  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar 
        currentPage={currentPage} 
        setCurrentPage={setCurrentPage}
        isOpen={sidebarOpen}
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar
          currentPage={currentPage}
          wsStatus={status}
          latency={latency}
          onConnect={connect}
          onDisconnect={disconnect}
          user={user}
          onLogout={logout}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />
        
        <div className="flex-1 overflow-y-auto p-6">
          {currentPage === 'live' && <LiveView wsData={lastMessage} />}
          {currentPage === 'commands' && <CommandVisualizer wsData={lastMessage} />}
          {currentPage === 'recordings' && <RecordingsView />}
          {currentPage === 'devices' && <DevicesView />}
          {currentPage === 'chat' && <ChatView wsData={lastMessage} />}
          {currentPage === 'mock' && <MockView />}
          {currentPage === 'settings' && <SettingsView />}
          {currentPage === 'test' && <TestView />}
        </div>
      </div>
    </div>
  )
}

function App() {
  
  // File handling
  function onFileChange(ev) {
    const file = ev.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const isTxt = /\.txt$/i.test(file.name);
    if (!isTxt) {
      alert('Please upload a .txt file');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setFileText(String(reader.result || ''));
    reader.readAsText(file);
  }

  async function onEncrypt() {
    if (!fileText) {
      alert('Please select a .txt file');
      return;
    }
    if (!password || password.length < 6) {
      alert('Use a password with at least 6 characters');
      return;
    }
    setBusy(true);
    try {
      const bytes = await encryptText(fileText, password);
      const b64 = bytesToBase64(bytes);
      setResultB64(b64);
    } catch (e) {
      console.error(e);
      alert('Encryption failed');
    } finally {
      setBusy(false);
    }
  }

  function downloadEncrypted() {
    if (!resultB64) return;
    const blob = new Blob([resultB64], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const base = fileName.replace(/\.txt$/i, '') || 'encrypted';
    a.download = base + '.enc.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // Handle successful auth
  const handleSignupSuccess = () => {
    console.log('Signup successful!');
    setIsAuthenticated(true);
    setAuthView(null);
    // Optionally redirect or show welcome message
  };

  const handleLoginSuccess = () => {
    console.log('Login successful!');
    setIsAuthenticated(true);
    setAuthView(null);
    // Optionally redirect or show welcome message
  };

  // Pill size calculation
  const [pillSize, setPillSize] = React.useState({ width: 0, height: 0 });
  React.useEffect(() => {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    context.font = '16px Inter, sans-serif';

    let maxWidth = 0;
    themePresets.forEach(p => {
      const metrics = context.measureText(p.label);
      const w = metrics.width;
      if (w > maxWidth) maxWidth = w;
    });

    const paddedWidth = Math.ceil(maxWidth + 60);
    setPillSize({ width: paddedWidth, height: 40 });
  }, []);

  return (
    <div className="app-root">
      {/* Navigation */}
      <div className="topbar">
        <div className="topbar-inner container">
          <div className="brand">
            <video muted autoPlay loop playsInline preload="auto" aria-label="logo animation">
              <source src="./Resources/Encryption.mp4" type="video/mp4" />
            </video>
            <div className="title">
              Encrypt <br /> Your Data
            </div>
          </div>

          <nav className="nav">
            <div className="pill-nav" style={{ background: 'transparent', border: 'none', boxShadow: 'none', padding: 0 }}>
              <PillNav
                items={[
                  { label: 'Home', href: '#top' },
                  { label: 'About', href: '#about' },
                  { label: 'How it Works', href: '#how' },
                  {
                    label: isAuthenticated ? 'Logout' : 'Login',
                    onClick: () => {
                      if (isAuthenticated) {
                        setIsAuthenticated(false);
                        alert('Logged out successfully');
                      } else {
                        setAuthView('login');
                      }
                    }
                  },
                  {
                    label: 'Theme',
                    type: 'pill',
                    key: 'theme-dropdown',
                    menu: ({ close }) => (
                      <ScrollStack>
                        {themePresets.map((p) => (
                          <ScrollStackItem key={p.value}>
                            <Pill
                              label={p.label}
                              pillHeight={42}
                              pillWidth={pillSize.width}
                              active={theme === p.value}
                              onClick={() => {
                                setTheme(p.value);
                                close?.();
                              }}
                              baseColor={p.accent}
                              pillColor={p.text}
                              hoveredTextColor={p.text}
                              pillTextColor={p.accent}
                            />
                          </ScrollStackItem>
                        ))}
                      </ScrollStack>
                    )
                  }
                ]}
                activeHref={typeof window !== 'undefined' ? window.location.hash || '#top' : '#top'}
                className="custom-nav"
                ease="power2.easeOut"
                baseColor={navColors.base}
                pillColor={navColors.pill}
                hoveredPillTextColor={navColors.hoverText}
                pillTextColor={navColors.pillText}
              />
            </div>
          </nav>

          <button
            className="btn-encrypting"
            onClick={() => document.getElementById('encrypt-card')?.scrollIntoView({ behavior: 'smooth' })}
          >
            Start Encrypting
          </button>
        </div>
      </div>

      {/* Main Content */}
      <main className="container" style={{ flex: 1 }}>
        {/* Hero Section */}
        <section className="hero">
          <div className="hero-grid">
            <div>
              <h1 className="headline">
                CRYPTIC
                <br />
                <span className="accent">ENCRYPTOR</span>
              </h1>
              <p className="lede">
                <EncryptText
                  text="Step into the Shadows where Secrets Burn."
                  sequential
                  revealDirection="start"
                  speed={60}
                  maxIterations={10}
                />
                <br />
                <EncryptText
                  text="With Encryption Born from the Abyss,"
                  sequential
                  revealDirection="start"
                  speed={60}
                  maxIterations={12}
                />
                <br />
                <EncryptText
                  text="your Data becomes Untouchable."
                  sequential
                  revealDirection="start"
                  speed={60}
                  maxIterations={12}
                />
                <br />
                <EncryptText
                  text="Dare to Hide… If you Can."
                  sequential
                  revealDirection="start"
                  speed={60}
                  maxIterations={12}
                />
              </p>

              <div className="cta">
                <button
                  className="btn btn-primary"
                  onClick={() => setAuthView('signup')}
                >
                  Get Started →
                </button>
                <a className="btn btn-secondary" href="#encrypt-card">
                  Experience Generator
                </a>
              </div>
            </div>

            <div>
              <div className="mosaic">
                <div className="mosaic-item">
                  <video src="/Encryption.svg" alt="preview" />
                </div>
                <div className="mosaic-item">
                  <video src="/lock.mp4" muted autoPlay loop playsInline />
                </div>
                <div className="mosaic-item">
                  <img src="/encryption-file.png" alt="file" />
                </div>
                <div className="mosaic-item">
                  <video src="/door.mp4" muted autoPlay loop playsInline />
                </div>
                <div className="mosaic-item">
                  <img src="/encryption-file.png" alt="file 2" />
                </div>
                <div className="mosaic-item">
                  <img src="/encryption.png" alt="preview 2" />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Encryption Card */}
        <div className="grid">
          <div className="card" id="encrypt-card">
            <div className="row two">
              <div>
                <label className="muted">Upload .txt file</label>
                <div className="file-drop">
                  <input
                    type="file"
                    accept=".txt"
                    onChange={onFileChange}
                    style={{ display: 'none' }}
                    id="fileInput"
                  />
                  <label htmlFor="fileInput" className="btn" style={{ cursor: 'pointer' }}>
                    Choose File
                  </label>
                  <div style={{ marginTop: 12 }} className="file-name">
                    {fileName || 'No file selected'}
                  </div>
                </div>
              </div>
              <div>
                <label className="muted">Password</label>
                <input
                  className="input"
                  placeholder="Enter password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <div className="muted" style={{ marginTop: 8, fontSize: 13 }}>
                  AES‑256 GCM with PBKDF2(SHA-256, 100k)
                </div>
              </div>
            </div>

            <div className="actions" style={{ marginTop: 20 }}>
              <button className="btn" onClick={onEncrypt} disabled={busy}>
                {busy ? 'Encrypting...' : 'Encrypt'}
              </button>
              <button className="btn" onClick={downloadEncrypted} disabled={!resultB64}>
                Download .enc.txt
              </button>
            </div>

            {!!resultB64 && (
              <div style={{ marginTop: 20 }}>
                <label className="muted">Preview (base64, truncated)</label>
                <div className="input" style={{ height: 120, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                  {resultB64.slice(0, 512)}
                  {resultB64.length > 512 ? '...' : ''}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <div className="footer">
        Built with Web Crypto API •{' '}
        <a onClick={() => setAuthView('signup')} className="muted" href="#signup" rel="noreferrer">
          Sign Up
        </a>
        {' '} •{' '}
        <a
          className="muted"
          href="https://github.com/askh-tamrakar/"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </div>

      {/* Auth Modal */}
      {authView && (
        <AuthModal
          type={authView}
          open={!!authView}
          onClose={() => setAuthView(null)}
          onSuccess={() => {
            if (authView === 'signup') {
              handleSignupSuccess();
            } else if (authView === 'login') {
              handleLoginSuccess();
            }
          }}
        />
      )}
    </div>
  );
}