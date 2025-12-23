const themePresets = [
  // 🔆 Bright Yellow tones
  {
    value: 'theme-yellow-dark',
    label: 'Golden Eclipse',
    type: 'night',
    pair: 'theme-yellow',
    accent: '#E3A500',
    text: '#FFF7B0',
    colors: {
      bg: '#2C2B28',
      surface: '#3B392F',
      text: '#FFF7B0',
      muted: '#D9C974',
      primary: '#F2B01E',
      border: '#C69C00'
    }
  },
  {
    value: 'theme-yellow',
    label: 'Golden Ember',
    type: 'day',
    pair: 'theme-yellow-dark',
    accent: '#E3A500',
    text: '#2C2C2C',
    colors: {
      bg: '#FFF7B0',
      surface: '#FFE680',
      text: '#2C2C2C',
      muted: '#A18F3B',
      primary: '#F2B01E',
      border: '#C69C00'
    }
  },

  // 🌹 Rose & Pink
  {
    value: 'theme-rose',
    label: 'Crimson Rose',
    type: 'night',
    pair: 'theme-rose-day',
    accent: '#88304E',
    text: '#ffffff',
    colors: {
      bg: '#2C2C2C',
      surface: '#522546',
      text: '#ffffff',
      muted: '#e8d7df',
      primary: '#F7374F',
      border: '#6a3c59'
    }
  },
  {
    value: 'theme-rose-day',
    label: 'Rose Day',
    type: 'day',
    pair: 'theme-rose',
    accent: '#88304E',
    text: '#2C2C2C',
    colors: {
      bg: '#FFF0F5',
      surface: '#FFD1DC',
      text: '#522546',
      muted: '#88304E',
      primary: '#F7374F',
      border: '#FFB7C5'
    }
  },

  // 🌿 Earthy & Natural
  {
    value: 'theme-olive',
    label: 'Verdant Olive',
    type: 'night',
    pair: 'theme-olive-day',
    accent: '#97B067',
    text: '#f7fff8',
    colors: {
      bg: '#2F5249',
      surface: '#437057',
      text: '#f7fff8',
      muted: '#dcebdc',
      primary: '#E3DE61',
      border: '#5a8b74'
    }
  },
  {
    value: 'theme-olive-day',
    label: 'Olive Garden',
    type: 'day',
    pair: 'theme-olive',
    accent: '#5a8b74',
    text: '#1a2f25',
    colors: {
      bg: '#F1F8F6',
      surface: '#DCEBDC',
      text: '#1A2F25',
      muted: '#5A8B74',
      primary: '#6B8E23',
      border: '#97B067'
    }
  },

  {
    value: 'theme-forest',
    label: 'Emerald Forest',
    type: 'night',
    pair: 'theme-forest-day',
    accent: '#1abc9c',
    text: '#e9fff1',
    colors: {
      bg: '#0e1512',
      surface: '#14201b',
      text: '#e9fff1',
      muted: '#cfe9db',
      primary: '#2ecc71',
      border: '#1b332a'
    }
  },
  {
    value: 'theme-forest-day',
    label: 'Forest Glade',
    type: 'day',
    pair: 'theme-forest',
    accent: '#1abc9c',
    text: '#08110e',
    colors: {
      bg: '#E8F5E9',
      surface: '#C8E6C9',
      text: '#08110e',
      muted: '#4CAF50',
      primary: '#2E7D32',
      border: '#81C784'
    }
  },

  // 🌊 Cool & Oceanic
  {
    value: 'theme-ocean',
    label: 'Deep Ocean',
    type: 'night',
    pair: 'theme-ocean-day',
    accent: '#1f6feb',
    text: '#e7f6ff',
    colors: {
      bg: '#071a2c',
      surface: '#0f2e4a',
      text: '#e7f6ff',
      muted: '#b9d8ea',
      primary: '#23a6f2',
      border: '#17415f'
    }
  },
  {
    value: 'theme-ocean-day',
    label: 'Ocean Breeze',
    type: 'day',
    pair: 'theme-ocean',
    accent: '#0284c7',
    text: '#0c4a6e',
    colors: {
      bg: '#E0F2FE',
      surface: '#BAE6FD',
      text: '#0C4A6E',
      muted: '#38BDF8',
      primary: '#0284C7',
      border: '#7DD3FC'
    }
  },

  {
    value: 'theme-slate',
    label: 'Midnight Slate',
    type: 'night',
    pair: 'theme-slate-day',
    accent: '#a6adc8',
    text: '#f1f5f9',
    colors: {
      bg: '#0b0d12',
      surface: '#121723',
      text: '#f1f5f9',
      muted: '#c7d0dd',
      primary: '#7aa2f7',
      border: '#202534'
    }
  },
  {
    value: 'theme-slate-day',
    label: 'Slate Day',
    type: 'day',
    pair: 'theme-slate',
    accent: '#475569',
    text: '#0f172a',
    colors: {
      bg: '#F8FAFC',
      surface: '#E2E8F0',
      text: '#0F172A',
      muted: '#64748B',
      primary: '#3B82F6',
      border: '#CBD5E1'
    }
  },

  // 📓 Monochrome
  {
    value: 'theme-simple',
    label: 'Simple Black',
    type: 'night',
    pair: 'theme-white',
    accent: '#ffffff',
    text: '#ffffff',
    colors: {
      bg: '#000000',
      surface: '#111111',
      text: '#ffffff',
      muted: '#888888',
      primary: '#ffffff',
      border: '#333333'
    }
  },
  {
    value: 'theme-white',
    label: 'Simple White',
    type: 'day',
    pair: 'theme-simple',
    accent: '#000000',
    text: '#000000',
    colors: {
      bg: '#ffffff',
      surface: '#f5f5f5',
      text: '#000000',
      muted: '#666666',
      primary: '#000000',
      border: '#e0e0e0'
    }
  }
];

export default themePresets;