import React, { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useTheme } from '../../contexts/ThemeContext'
import { Github, UserPlus } from 'lucide-react'
import LiveDashboard from '../views/LiveDashboard'
import DinoView from '../views/DinoView'
import SSVEPView from '../views/SSVEPView'
import RPSGame from '../views/RPSGame'
import CalibrationView from '../views/CalibrationView'
import MLTrainingView from '../views/MLTrainingView'
import SettingsView from '../views/SettingsView'

import '../../styles/App.css';
import ScrollStack, { ScrollStackItem } from '../ui/ScrollStack';
import PillNav from '../ui/PillNav';
import Pill from '../ui/Pill';
import { ConnectionButton } from '../ui/ConnectionButton';

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [currentPage, setCurrentPage] = useState('live')
  // const [sidebarOpen, setSidebarOpen] = useState(true)
  const { status, lastMessage, lastConfig, lastEvent, latency, connect, disconnect, sendMessage, currentUrl } = useWebSocket(
    'http://localhost:5000' // Prioritize local development port
  )

  // WebSocket modal state and preset URLs
  const [wsModalOpen, setWsModalOpen] = useState(false)
  const [localWs, setLocalWs] = useState(import.meta.env.VITE_WS_URL || 'http://localhost:5000')
  const [ngrokWs, setNgrokWs] = useState(import.meta.env.VITE_NGROK_WS_URL || 'wss://squelchingly-thriftier-cecile.ngrok-free.dev')

  const { themes, currentTheme, currentThemeId, setTheme } = useTheme();
  const [authView, setAuthView] = useState(null);
  const isAuthenticated = !!user;

  // Derived nav colors from current theme
  const navColors = React.useMemo(() => ({
    base: currentTheme.colors['--accent'],
    pill: currentTheme.colors['--text'],
    pillText: currentTheme.colors['--accent'],
    hoverText: currentTheme.colors['--text']
  }), [currentTheme]);

  // Pill size calculation
  const [pillSize, setPillSize] = React.useState({ width: 0, height: 0 });
  React.useEffect(() => {
    if (!themes.length) return;
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    context.font = '16px Inter, sans-serif';

    let maxWidth = 0;
    themes.forEach(p => {
      const metrics = context.measureText(p.name);
      const w = metrics.width;
      if (w > maxWidth) maxWidth = w;
    });

    const paddedWidth = Math.ceil(maxWidth + 60);
    setPillSize({ width: paddedWidth, height: 40 });
  }, [themes]);

  useEffect(() => {
    connect()

    // Handle initial hash
    const hash = window.location.hash.replace('#', '');
    if (hash) setCurrentPage(hash);

    // Handle hash changes
    const handleHashChange = () => {
      const newHash = window.location.hash.replace('#', '');
      if (newHash) setCurrentPage(newHash);
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [])

  const handleSignupSuccess = () => {
    setAuthView(null);
  };

  const handleLoginSuccess = () => {
    setAuthView(null);
  };


  const navItems = React.useMemo(() => [
    { label: 'GRAPHS', onClick: () => setCurrentPage('live'), href: '#live' },
    { label: 'Dino', onClick: () => setCurrentPage('dino'), href: '#dino' },
    { label: 'SSVEP', onClick: () => setCurrentPage('ssvep'), href: '#ssvep' },
    { label: 'RPS', onClick: () => setCurrentPage('rps'), href: '#rps' },
    { label: 'M. L.', onClick: () => setCurrentPage('ml_training'), href: '#ml_training' },
    { label: 'Calibration', onClick: () => setCurrentPage('calibration'), href: '#calibration' },
    { label: 'Settings', onClick: () => setCurrentPage('settings'), href: '#settings' },
    {
      label: 'Theme',
      type: 'pill',
      key: 'theme-dropdown',
      href: '#',
      menu: ({ close }) => (
        <ScrollStack>
          {themes.map((t) => (
            <ScrollStackItem key={t.id}>
              <Pill
                label={t.name}
                activeHref={`#${currentPage}`}
                pillHeight={42}
                pillWidth={pillSize.width}
                active={currentThemeId === t.id}
                onClick={() => {
                  setTheme(t.id);
                  close?.();
                }}
                baseColor={t.colors['--accent']}
                pillColor={t.colors['--text']}
                hoveredTextColor={t.colors['--text']}
                pillTextColor={t.colors['--accent']}
              />
            </ScrollStackItem>
          ))}
        </ScrollStack>
      )
    }
  ], [themes, currentThemeId, pillSize.width, currentPage]);

  return (
    <div className="app-root">
      {/* Navigation */}
      <div className="header" style={{ zIndex: 50 }}>
        <div className="header-inner container">
          <div className="flex items-center gap-3">
            <div className="relative group cursor-pointer" onClick={logout} title="Click to Logout">
              <div className="absolute inset-0 bg-primary/20 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
              <video muted autoPlay loop playsInline preload="auto" aria-label="logo animation" className="w-16 h-16 relative z-10 rounded-lg border border-border bg-black object-cover">
                <source src="/Resources/brain_animation.mp4" type="video/mp4" />
              </video>
            </div>

            {/* WebSocket connect modal */}
            {wsModalOpen && (
              <div className="fixed inset-0 z-60 flex items-start justify-center bg-black/40" style={{ paddingTop: '96px' }}>
                <div className="bg-surface rounded-lg p-6 w-96">
                  <h3 className="text-sm font-bold text-muted uppercase tracking-wider mb-4">WebSocket Connection</h3>
                  <div className="mb-2">
                    <label className="text-xs font-medium text-text block mb-1">Local WS URL</label>
                    <input className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm outline-none focus:border-primary/50" value={localWs} onChange={e => setLocalWs(e.target.value)} />
                  </div>
                  <div className="mb-2">
                    <label className="text-xs font-medium text-text block mb-1">Ngrok WS URL</label>
                    <input className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm outline-none focus:border-primary/50" value={ngrokWs} onChange={e => setNgrokWs(e.target.value)} />
                  </div>
                  <div className="flex gap-2 mt-4">
                    <button className="w-full py-2 bg-primary text-primary-contrast rounded-lg font-bold text-sm shadow-glow hover:opacity-90 active:scale-95 transition-all" onClick={() => { connect(localWs); setWsModalOpen(false) }}>Connect Local</button>
                    <button className="w-full py-2 bg-primary text-primary-contrast rounded-lg font-bold text-sm shadow-glow hover:opacity-90 active:scale-95 transition-all" onClick={() => { connect(ngrokWs); setWsModalOpen(false) }}>Connect Ngrok</button>
                    <button className="w-full py-2 bg-muted text-muted-contrast rounded-lg font-bold text-sm shadow-glow hover:opacity-90 active:scale-95 transition-all" onClick={() => setWsModalOpen(false)}>Close</button>
                  </div>
                </div>
              </div>
            )}
            <div className="headline flex flex-col">
              <div className="headline-line main">
                NeuroTECH
                <br />
                <div className="headline-line sub">BCI Dashboard</div>
              </div>
            </div>
          </div>

          <nav className="nav shrink-0">
            <div className="backdrop-blur-sm bg-surface/50 border border-white/5 rounded-full p-1">
              <PillNav
                items={navItems}
                activeHref={`#${currentPage}`}
                className="custom-nav"
                ease="power2.easeOut"
                baseColor={navColors.base}
                pillColor={navColors.pill}
                hoveredPillTextColor={navColors.hoverText}
                pillTextColor={navColors.pillText}
                onLogoClick={() => setWsModalOpen(true)}
              />
            </div>
          </nav>
          <div className="w-[180px] flex justify-end shrink-0">
            <ConnectionButton
              status={status}
              latency={latency}
              connect={connect}
              disconnect={disconnect}
            />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="scrollbar-thin scrollbar-thumb-border hover:scrollbar-thumb-primary/50 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']" style={{ flex: 1, padding: '0px 0px', overflowY: 'auto' }}>

        {/* Helper to determine if we need spacers (non-full-screen pages need them to clear fixed header/footer) */}
        {(() => {
          const FULL_SCREEN_PAGES = ['live', 'dino'];
          const showSpacers = !FULL_SCREEN_PAGES.includes(currentPage);

          return (
            <>
              {showSpacers && <div className="h-[94px] shrink-0" />}

              {currentPage === 'live' && <LiveDashboard wsData={lastMessage} wsConfig={lastConfig} wsEvent={lastEvent} sendMessage={sendMessage} />}
              {currentPage === 'dino' && <DinoView wsData={lastMessage} wsEvent={lastEvent} isPaused={false} />}
              {currentPage === 'ssvep' && <SSVEPView />}
              {/* {currentPage === 'test' && <TestView wsData={lastMessage} wsEvent={lastEvent} config={lastConfig} />} */}
              {currentPage === 'rps' && <RPSGame wsEvent={lastEvent} />}
              {currentPage === 'calibration' && <CalibrationView wsData={lastMessage} wsEvent={lastEvent} config={lastConfig} />}
              {currentPage === 'ml_training' && <MLTrainingView />}
              {currentPage === 'settings' && <SettingsView />}

              {showSpacers && <div className="h-[35px] shrink-0" />}
            </>
          );
        })()}
      </div>

      {/* Footer */}
      <div className="footer">
        <span className="flex items-center gap-1">NeuroTECH - A BCI Project </span>  •  {' '}
        <a onClick={() => setAuthView('signup')} className="muted flex items-center gap-1" href="#signup" rel="noreferrer">
          Sign Up
        </a>
        {' '} • {' '}
        <a
          className="muted flex items-center gap-1"
          href="https://github.com/askh-tamrakar/NeuroTECH-BCI"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </div>
    </div>
  );
}