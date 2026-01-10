import React, { useState, useEffect } from 'react'
import { useTheme } from '../../contexts/ThemeContext'
import {
  Settings,
  Palette,
  Globe,
  Database,
  Plus,
  Trash2,
  Save,
  RefreshCw,
  Copy
} from 'lucide-react'

// Helper for color inputs
const ColorInput = ({ label, value, onChange }) => (
  <div className="flex items-center justify-between p-3 bg-bg/50 rounded-xl border border-border/50">
    <label className="text-sm font-medium text-text">{label}</label>
    <div className="flex items-center gap-3">
      <span className="text-xs font-mono text-muted uppercase">{value}</span>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-8 h-8 rounded-lg overflow-hidden cursor-pointer border-none p-0 bg-transparent"
        title={`Change ${label}`}
      />
    </div>
  </div>
);

export default function SettingsView() {
  const {
    themes,
    currentTheme,
    currentThemeId,
    setTheme,
    addTheme,
    updateTheme,
    updateThemeColor,
    removeTheme,
    resetThemes
  } = useTheme()

  // Local settings state
  const [apiUrl, setApiUrl] = useState(() => localStorage.getItem('api_url') || 'http://localhost:8000')
  const [wsUrl, setWsUrl] = useState(() => localStorage.getItem('ws_url') || 'ws://localhost:1972')
  const [useMock, setUseMock] = useState(() => localStorage.getItem('use_mock') === 'true')

  // Editor state
  const [isEditingName, setIsEditingName] = useState(false);
  const [tempName, setTempName] = useState('');

  // Auto-save settings
  useEffect(() => {
    localStorage.setItem('api_url', apiUrl)
    localStorage.setItem('ws_url', wsUrl)
    localStorage.setItem('use_mock', useMock)
  }, [apiUrl, wsUrl, useMock])

  const handleCreateTheme = () => {
    const newId = addTheme(`Custom Theme ${themes.length + 1}`);
    // Auto-scroll or focus?
  };

  const handleDuplicateTheme = () => {
    const newId = addTheme(`${currentTheme.name} (Copy)`);
    // Ideally we would copy the colors here, but addTheme currently clones the *current* theme colors
    // so it already does exactly what we want!
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-20">

      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <div className="p-3 bg-primary/20 rounded-2xl text-primary">
          <Settings size={32} />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-text">Settings</h1>
          <p className="text-muted">Manage your workspace preferences</p>
        </div>
      </div>

      {/* Theme Section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-text flex items-center gap-2">
            <Palette size={20} className="text-primary" />
            Appearance
          </h2>
          <div className="flex gap-2">
            <button
              onClick={resetThemes}
              className="px-3 py-1.5 text-xs font-bold text-muted hover:text-text hover:bg-surface rounded-lg transition-colors"
            >
              Reset Defaults
            </button>
            <button
              onClick={handleCreateTheme}
              className="flex items-center gap-2 px-4 py-2 bg-surface hover:bg-primary hover:text-primary-contrast border border-border rounded-xl font-bold transition-all shadow-sm"
            >
              <Plus size={16} />
              New Theme
            </button>
          </div>
        </div>

        <div className="card p-6 bg-surface space-y-6">

          {/* Theme Selector */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {themes.map(t => (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className={`
                  relative group p-3 rounded-xl border-2 transition-all text-left space-y-2
                  ${currentThemeId === t.id
                    ? 'border-primary bg-primary/5 shadow-glow'
                    : 'border-transparent bg-bg hover:border-border'
                  }
                `}
              >
                <div className="flex gap-1.5 mb-2">
                  <div className="w-4 h-4 rounded-full shadow-sm" style={{ background: t.colors['--bg'] }} />
                  <div className="w-4 h-4 rounded-full shadow-sm" style={{ background: t.colors['--primary'] }} />
                  <div className="w-4 h-4 rounded-full shadow-sm" style={{ background: t.colors['--accent'] }} />
                </div>
                <div className="font-bold text-sm truncate w-full" style={{ color: currentThemeId === t.id ? 'var(--primary)' : 'var(--text)' }}>
                  {t.name}
                </div>
                {t.type === 'custom' && (
                  <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="w-2 h-2 rounded-full bg-primary" />
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* Theme Editor (Only for current theme) */}
          <div className="mt-8 border-t border-border pt-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                {isEditingName ? (
                  <input
                    autoFocus
                    type="text"
                    className="bg-bg border border-primary text-text font-bold text-lg px-2 py-1 rounded-lg outline-none"
                    value={tempName}
                    onChange={e => setTempName(e.target.value)}
                    onBlur={() => {
                      updateTheme(currentThemeId, { name: tempName || currentTheme.name });
                      setIsEditingName(false);
                    }}
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        updateTheme(currentThemeId, { name: tempName || currentTheme.name });
                        setIsEditingName(false);
                      }
                    }}
                  />
                ) : (
                  <h3
                    className={`text-lg font-bold ${currentTheme.type === 'custom' ? 'cursor-pointer hover:underline decoration-dashed decoration-muted' : ''}`}
                    onClick={() => {
                      if (currentTheme.type === 'custom') {
                        setTempName(currentTheme.name);
                        setIsEditingName(true);
                      }
                    }}
                    title={currentTheme.type === 'custom' ? 'Click to rename' : 'Built-in theme'}
                  >
                    {currentTheme.name}
                    {currentTheme.type === 'custom' && <span className="ml-2 text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full">Custom</span>}
                  </h3>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleDuplicateTheme}
                  className="p-2 text-muted hover:text-text hover:bg-bg rounded-lg transition-colors"
                  title="Duplicate Theme"
                >
                  <Copy size={18} />
                </button>
                {currentTheme.type === 'custom' && (
                  <button
                    onClick={() => removeTheme(currentThemeId)}
                    className="p-2 text-red-400 hover:text-red-500 hover:bg-red-400/10 rounded-lg transition-colors"
                    title="Delete Theme"
                  >
                    <Trash2 size={18} />
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-muted uppercase tracking-wider mb-2">Core Colors</h4>
                <ColorInput label="Background" value={currentTheme.colors['--bg']} onChange={(v) => updateThemeColor(currentThemeId, '--bg', v)} />
                <ColorInput label="Surface" value={currentTheme.colors['--surface']} onChange={(v) => updateThemeColor(currentThemeId, '--surface', v)} />
                <ColorInput label="Text" value={currentTheme.colors['--text']} onChange={(v) => updateThemeColor(currentThemeId, '--text', v)} />
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-bold text-muted uppercase tracking-wider mb-2">Brand Colors</h4>
                <ColorInput label="Primary" value={currentTheme.colors['--primary']} onChange={(v) => updateThemeColor(currentThemeId, '--primary', v)} />
                <ColorInput label="Accent" value={currentTheme.colors['--accent']} onChange={(v) => updateThemeColor(currentThemeId, '--accent', v)} />
                <ColorInput label="Border" value={currentTheme.colors['--border']} onChange={(v) => updateThemeColor(currentThemeId, '--border', v)} />
              </div>
            </div>

            {currentTheme.type === 'default' && (
              <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/20 text-blue-200 text-sm rounded-lg flex items-center gap-2">
                <Settings size={14} />
                <span>Standard themes are read-only. Duplicate this theme to customize it.</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Network Section */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-text flex items-center gap-2">
          <Globe size={20} className="text-primary" />
          Network & Data
        </h2>

        <div className="card p-6 bg-surface space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-bold text-text">API Endpoint</label>
              <div className="flex bg-bg border border-border rounded-xl focus-within:ring-2 ring-primary/50 transition-all overflow-hidden">
                <input
                  type="text"
                  value={apiUrl}
                  onChange={e => setApiUrl(e.target.value)}
                  className="flex-1 px-4 py-3 bg-transparent outline-none text-text placeholder-muted"
                  placeholder="http://localhost:8000"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-bold text-text">WebSocket Endpoint</label>
              <div className="flex bg-bg border border-border rounded-xl focus-within:ring-2 ring-primary/50 transition-all overflow-hidden">
                <input
                  type="text"
                  value={wsUrl}
                  onChange={e => setWsUrl(e.target.value)}
                  className="flex-1 px-4 py-3 bg-transparent outline-none text-text placeholder-muted"
                  placeholder="ws://localhost:1972"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between p-4 bg-bg rounded-xl border border-border">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${useMock ? 'bg-amber-500/20 text-amber-500' : 'bg-muted/20 text-muted'}`}>
                <Database size={20} />
              </div>
              <div>
                <h4 className="font-bold text-text">Mock Data Mode</h4>
                <p className="text-xs text-muted">Generate fake signals for testing without hardware</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" checked={useMock} onChange={e => setUseMock(e.target.checked)} className="sr-only peer" />
              <div className="w-11 h-6 bg-border peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
            </label>
          </div>
        </div>
      </section>

      {/* Info Section */}
      <section className="space-y-4">
        <div className="card p-6 bg-surface/50 border-dashed">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-text">NeuroTECH BCI Dashboard</h3>
              <p className="text-sm text-muted">v2.0.0 • Early Access Build</p>
            </div>
            <div className="text-right">
              <p className="text-xs font-mono text-muted mb-1">Session ID: {Math.random().toString(36).substring(7)}</p>
              <div className="flex gap-2 justify-end">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs font-bold text-green-500">System Active</span>
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>
  )
}
