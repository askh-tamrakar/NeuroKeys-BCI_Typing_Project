import React, { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../hooks/useWebSocket'
import LiveView from '../views/LiveView'
import CommandVisualizer from '../views/CommandVisualizer'
import RecordingsView from '../views/RecordingsView'
import DevicesView from '../views/DevicesView'
import ChatView from '../views/ChatView'
import MockView from '../views/MockView'
import SettingsView from '../views/SettingsView'
import TestView from '../views/TestView'

import '../../styles/App.css';
import themePresets from '../themes/presets';
import ScrollStack, { ScrollStackItem } from '../ui/ScrollStack';
import PillNav from '../ui/PillNav';
import Pill from '../ui/Pill';
import { Brain, Zap, Plug, Cable } from 'lucide-react';

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [currentPage, setCurrentPage] = useState('live')
  const [isConnectingClicked, setIsConnectingClicked] = useState(false);
  // State for 5-second connection simulation
  const [isSimulatedConnecting, setIsSimulatedConnecting] = useState(false);
  // State to manage video loading status
  const [isVideoLoaded, setIsVideoLoaded] = useState(false);

  const { status, lastMessage, latency, connect, disconnect, sendMessage } = useWebSocket(
    import.meta.env.VITE_WS_URL || 'ws://localhost:8765'
  )
  const [theme, setTheme] = React.useState(() => localStorage.getItem('theme') || 'theme-violet');
  const [navColors, setNavColors] = React.useState({ base: '#000000', pill: '#ffffff', pillText: '#000000', hoverText: '#ffffff' });
  const [authView, setAuthView] = useState(null);
  const isAuthenticated = !!user;

  // Theme management (No Change)
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

  // Pill size calculation (No Change)
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

  // Connection is user-initiated only
  useEffect(() => {
    // No auto-connect
  }, [])

  const handleConnectClick = () => {
    setIsConnectingClicked(true);
    setTimeout(() => setIsConnectingClicked(false), 200); 
    
    if (status === 'connected') {
        disconnect();
    } else {
        // 1. Start simulated connecting (overrides actual status display for 5s)
        setIsSimulatedConnecting(true); 
        
        // 2. Start actual connection attempt
        connect(); 

        // 3. End the simulated connecting phase after 5 seconds
        setTimeout(() => {
            setIsSimulatedConnecting(false);
        }, 5000); // 5000 milliseconds = 5 seconds
    }
  }

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
    { label: 'Chat', onClick: () => setCurrentPage('chat'), href: '#chat' },
    { label: 'Settings', onClick: () => setCurrentPage('settings'), href: '#settings' },
    { label: 'Test', onClick: () => setCurrentPage('test'), href: '#test' },
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
  
  // Logic to determine the status to display on the button
  const currentDisplayStatus = isSimulatedConnecting ? 'connecting' : status;

  // Helper for Connecting button icon uses the currentDisplayStatus
  const ConnectionIcon = ({ status }) => {
    if (status === 'connected') return <Cable className="w-5 h-5 text-emerald-400" />;
    if (status === 'connecting') return <Zap className="w-5 h-5 text-amber-400 animate-pulse" />;
    return <Plug className="w-5 h-5 text-red-400" />;
  };


  return (
    <div className="app-root flex flex-col min-h-screen">
      {/* Navigation */}
      <div className="topbar sticky top-0" style={{ zIndex: 50 }}>
        <div className="topbar-inner container flex flex-wrap items-center justify-between gap-4 py-3 md:py-4">
          
          {/* Top-Left Symbol/Logo Area */}
          <div className="flex items-center gap-3">
            
            {/* *** CHANGED: Increased size from w-14 h-14 to w-20 h-20 *** */}
            <div className={`relative w-20 h-20 flex items-center justify-center bg-surface/80 rounded-xl border border-border shadow-lg overflow-hidden transition-all duration-300 ${status === 'connected' ? 'shadow-primary/40' : ''}`}>
                
                {/* Video Element */}
                <video 
                    src="/Resources/brain_animation.mp4" 
                    autoPlay 
                    loop 
                    muted 
                    playsInline
                    onLoadedData={() => setIsVideoLoaded(true)}
                    onError={() => setIsVideoLoaded(false)}
                    className={`w-full h-full object-cover block transition-all duration-500 ${status === 'connected' ? 'opacity-100' : 'opacity-70'} ${!isVideoLoaded ? 'hidden' : ''}`}
                />
                
                {/* Fallback Brain Icon (Shown if video fails to load or hasn't loaded yet) */}
                {!isVideoLoaded && (
                    <Brain 
                        className={`w-10 h-10 transition-all duration-500 ${status === 'connected' ? 'text-primary' : 'text-primary/50'}`} 
                        style={{ animation: 'subtle-spin 15s linear infinite' }}
                    />
                )}

                {/* Pulse Glow for connection activity (only when actual status is connected) */}
                {status === 'connected' && (
                  <Zap 
                    className="absolute w-6 h-6 text-primary z-10" 
                    style={{ animation: 'pulse-glow 2s ease-in-out infinite' }}
                  />
                )}
            </div>
            {/* *** END CHANGED: Size increased *** */}

            {/* Text Animation is fine */}
            <div className="flex flex-col opacity-0 animate-slide-fade-in"> 
              <div className="headline text-2xl sm:text-3xl font-extrabold tracking-tight leading-tight">NeuroKeys
                <div className="accent text-lg sm:text-xl font-semibold text-muted">BCI Dashboard</div>
              </div>
            </div>
            {/* Text Animation is fine */}
          </div>

          {/* Navigation Pills - Centered/Wrapped on mobile */}
          <nav className="nav flex justify-center order-3 w-full md:order-none md:w-auto"> 
            <div className="backdrop-blur-sm bg-surface/50 border border-white/5 rounded-full p-1 shadow-inner">
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
          
          {/* Connecting Button logic uses currentDisplayStatus */}
          <button
            onClick={handleConnectClick} // Call the new handler
            className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-full border shadow-lg transition-all duration-200 ease-in-out font-bold text-sm tracking-wide w-full max-w-[200px] sm:w-auto 
              ${isConnectingClicked ? 'animate-press-down shadow-none' : 'scale-100'} // Click animation
              ${currentDisplayStatus === 'connected'
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400 hover:bg-emerald-500/30 shadow-emerald-500/50' 
                : currentDisplayStatus === 'connecting'
                  ? 'bg-amber-500/20 border-amber-500/50 text-amber-400 shadow-amber-500/20'
                  : 'bg-red-500/20 border-red-500/50 text-red-400 hover:bg-red-500/30 shadow-red-500/20'
              }`}
          >
            <ConnectionIcon status={currentDisplayStatus} />

            <span className="text-sm font-bold uppercase tracking-wider">
              {currentDisplayStatus === 'connected' ? 'CONNECTED' : currentDisplayStatus === 'connecting' ? 'CONNECTING' : 'DISCONNECTED'}
            </span>

            {/* Latency only shows when actual status is connected */}
            {status === 'connected' && (
              <>
                <div className="w-[1px] h-4 bg-current opacity-30 mx-1"></div>
                <span className="text-xs font-mono opacity-80">{latency}ms</span>
              </>
            )}
          </button>
          {/* Connecting Button logic is fine */}

        </div>
      </div>

      {/* Main Content Area */}
      <div className="container flex-grow" style={{ padding: '24px 0', overflowY: 'auto' }}>
        {currentPage === 'live' && <LiveView wsData={lastMessage} />}
        {currentPage === 'commands' && <CommandVisualizer wsData={lastMessage} />}
        {currentPage === 'recordings' && <RecordingsView />}
        {currentPage === 'devices' && <DevicesView sendMessage={sendMessage} />}
        {currentPage === 'chat' && <ChatView wsData={lastMessage} />}
        {currentPage === 'mock' && <MockView />}
        {currentPage === 'settings' && <SettingsView />}
        {currentPage === 'test' && <TestView />}
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