import React, { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../hooks/useWebSocket'
import LiveDashboard from '../views/LiveDashboard'
import CommandVisualizer from '../views/CommandVisualizer'
import RecordingsView from '../views/RecordingsView'
import DevicesView from '../views/DevicesView'
//import ChatView from '../views/ChatView'
//import SettingsView from '../views/SettingsView'
//import TestView from '../views/TestView'
import DinoView from '../views/DinoView'

import '../../styles/App.css';
import themePresets from '../themes/presets';
import ScrollStack, { ScrollStackItem } from '../ui/ScrollStack';
import PillNav from '../ui/PillNav';
import Pill from '../ui/Pill';

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [currentPage, setCurrentPage] = useState('live')
  // const [sidebarOpen, setSidebarOpen] = useState(true)
  const { status, lastMessage, latency, connect, disconnect, sendMessage } = useWebSocket(
    import.meta.env.VITE_WS_URL || 'http://localhost:5000'
  )
  const [theme, setTheme] = React.useState(() => localStorage.getItem('theme') || 'theme-violet');
  const [navColors, setNavColors] = React.useState({ base: '#000000', pill: '#ffffff', pillText: '#000000', hoverText: '#ffffff' });
  const [authView, setAuthView] = useState(null);
  const isAuthenticated = !!user;

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

  useEffect(() => {
    connect()
  }, [])

  const handleSignupSuccess = () => {
    setAuthView(null);
  };

  const handleLoginSuccess = () => {
    setAuthView(null);
  };

  const navItems = React.useMemo(() => [
    { label: 'Live', onClick: () => setCurrentPage('live'), href: '#live' },
    { label: 'Commands', onClick: () => setCurrentPage('commands'), href: '#commands' },
    { label: 'Recordings', onClick: () => setCurrentPage('recordings'), href: '#recordings' },
    { label: 'Devices', onClick: () => setCurrentPage('devices'), href: '#devices' },
    //{ label: 'Chat', onClick: () => setCurrentPage('chat'), href: '#chat' },
    //{ label: 'Settings', onClick: () => setCurrentPage('settings'), href: '#settings' },
    //{ label: 'Test', onClick: () => setCurrentPage('test'), href: '#test' },
    { label: 'Dino', onClick: () => setCurrentPage('dino'), href: '#dino' },
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
  ], [theme, pillSize.width]);

  return (
    <div className="app-root">
      {/* Navigation */}
      <div className="topbar" style={{ zIndex: 50 }}>
        <div className="topbar-inner container">
          <div className="flex items-center gap-3">
            <div className="relative group">
              <div className="absolute inset-0 bg-primary/20 blur-lg rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
              <video muted autoPlay loop playsInline preload="auto" aria-label="logo animation" className="w-10 h-10 relative z-10 rounded-lg border border-border bg-black object-cover">
                <source src="/Resources/Encryption.mp4" type="video/mp4" />
              </video>
            </div>
            <div className="flex flex-col">
              <div className="headline">NeuroKeys
                <br />
                <div className="accent">BCI Dashboard</div>
              </div>
            </div>
          </div>

          <nav className="nav">
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
              />
            </div>
          </nav>

          <button
            onClick={() => status === 'connected' ? disconnect() : connect()}
            className={`flex items-center justify-center gap-2 w-36 py-2 rounded-full border transition-all duration-300 ${status === 'connected' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20' :
              status === 'connecting' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' :
                'bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20'
              }`}
          >
            <div className={`w-2 h-2 rounded-full ${status === 'connected' ? 'bg-emerald-500 shadow-[0_0_8px_currentColor]' :
              status === 'connecting' ? 'bg-amber-500 animate-pulse' :
                'bg-red-500'
              }`}></div>

            <span className="text-xs font-bold uppercase tracking-wider">
              {status === 'connected' ? 'Connected' : status === 'connecting' ? 'Connecting' : 'Disconnected'}
            </span>

            {status === 'connected' && (
              <>
                <div className="w-[1px] h-3 bg-current opacity-20 mx-1"></div>
                <span className="text-xs font-mono opacity-80">{latency}ms</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="container" style={{ flex: 1, padding: '24px 0', overflowY: 'auto' }}>
        {currentPage === 'live' && <LiveDashboard wsData={lastMessage} sendMessage={sendMessage} />}
        {currentPage === 'commands' && <CommandVisualizer wsData={lastMessage} />}
        {currentPage === 'recordings' && <RecordingsView />}
        {currentPage === 'devices' && <DevicesView sendMessage={sendMessage} />}
        {currentPage === 'chat' && <ChatView wsData={lastMessage} />}
        {currentPage === 'mock' && <MockView />}
        {currentPage === 'settings' && <SettingsView />}
        {currentPage === 'test' && <TestView />}
        {currentPage === 'dino' && <DinoView />}
      </div>

      {/* Footer */}
      <div className="footer">
        NeuroKeys: BCI Typing Project •{' '}
        <a onClick={() => setAuthView('signup')} className="muted" href="#signup" rel="noreferrer">
          Sign Up
        </a>
        {' '} •{' '}
        <a
          className="muted"
          href="https://github.com/askh-tamrakar/NeuroKeys-BCI_Typing_Project"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </div>
    </div>
  );
}