import React, { createContext, useContext, useState, useEffect } from 'react';

// Ported from index.css
const DEFAULT_THEMES = [
    {
        id: 'theme-rose',
        name: 'Crimson Rose',
        type: 'default',
        colors: {
            '--bg': '#2C2C2C',
            '--surface': '#522546',
            '--text': '#ffffff',
            '--muted': '#e8d7df',
            '--primary': '#F7374F',
            '--primary-contrast': '#2C2C2C',
            '--accent': '#88304E',
            '--border': '#6a3c59',
            '--shadow': 'rgba(0,0,0,0.35)',
            // Dino
            '--day': '#FFE4E1',
            '--night': '#2C2C2C',
            '--tree-day': '#D47995',
            '--tree-night': '#522546',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#6a3c59',
            '--sun-day': '#FFC0CB',
            '--sun-night': '#F7374F',
            '--moon-day': '#ffffff',
            '--moon-night': '#e8d7df',
            '--sky-day': '#FFE4E1',
            '--sky-night': '#2C2C2C',
        }
    },
    {
        id: 'theme-violet',
        name: 'Royal Violet',
        type: 'default',
        colors: {
            '--bg': '#030637',
            '--surface': '#3C0753',
            '--text': '#f4f0ff',
            '--muted': '#d9c8ff',
            '--primary': '#910A67',
            '--primary-contrast': '#0b0b15',
            '--accent': '#720455',
            '--border': '#4f2a6a',
            '--shadow': 'rgba(10, 6, 55, 0.45)',
            // Dino
            '--day': '#E6E6FA',
            '--night': '#030637',
            '--tree-day': '#910A67',
            '--tree-night': '#240046',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#3C0753',
            '--sun-day': '#FFD700',
            '--sun-night': '#E100FF',
            '--moon-day': '#ffffff',
            '--moon-night': '#D9C8FF',
            '--sky-day': '#E6E6FA',
            '--sky-night': '#030637',
        }
    },
    {
        id: 'theme-olive',
        name: 'Verdant Olive',
        type: 'default',
        colors: {
            '--bg': '#2F5249',
            '--surface': '#437057',
            '--text': '#f7fff8',
            '--muted': '#dcebdc',
            '--primary': '#E3DE61',
            '--primary-contrast': '#2F5249',
            '--accent': '#97B067',
            '--border': '#5a8b74',
            '--shadow': 'rgba(0,0,0,0.35)',
            // Dino
            '--day': '#F0FFF0',
            '--night': '#2F5249',
            '--tree-day': '#437057',
            '--tree-night': '#1a332d',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#5a8b74',
            '--sun-day': '#E3DE61',
            '--sun-night': '#FFB347',
            '--moon-day': '#ffffff',
            '--moon-night': '#DCEBDC',
            '--sky-day': '#E6F5E6',
            '--sky-night': '#2F5249',
        }
    },
    {
        id: 'theme-ocean',
        name: 'Deep Ocean',
        type: 'default',
        colors: {
            '--bg': '#071a2c',
            '--surface': '#0f2e4a',
            '--text': '#e7f6ff',
            '--muted': '#b9d8ea',
            '--primary': '#23a6f2',
            '--primary-contrast': '#041019',
            '--accent': '#1f6feb',
            '--border': '#17415f',
            '--shadow': 'rgba(3, 19, 33, 0.5)',
            // Dino
            '--day': '#E0F7FA',
            '--night': '#071a2c',
            '--tree-day': '#23a6f2',
            '--tree-night': '#0f2e4a',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#17415f',
            '--sun-day': '#FFD700',
            '--sun-night': '#FF7E5F',
            '--moon-day': '#ffffff',
            '--moon-night': '#B9D8EA',
            '--sky-day': '#B2EBF2',
            '--sky-night': '#071a2c',
        }
    },
    {
        id: 'theme-sunset',
        name: 'Amber Dusk',
        type: 'default',
        colors: {
            '--bg': '#1e0b12',
            '--surface': '#2b0f18',
            '--text': '#fff4ee',
            '--muted': '#ffd6c8',
            '--primary': '#ff7a59',
            '--primary-contrast': '#16070b',
            '--accent': '#ffb86b',
            '--border': '#4b1a22',
            '--shadow': 'rgba(30, 11, 18, 0.5)',
            // Dino
            '--day': '#FFF5EE',
            '--night': '#1e0b12',
            '--tree-day': '#ff7a59',
            '--tree-night': '#4b1a22',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#4b1a22',
            '--sun-day': '#ffb86b',
            '--sun-night': '#8B0000',
            '--moon-day': '#fff',
            '--moon-night': '#FFD6C8',
            '--sky-day': '#FFF5EE',
            '--sky-night': '#1e0b12',
        }
    },
    {
        id: 'theme-forest',
        name: 'Emerald Forest',
        type: 'default',
        colors: {
            '--bg': '#0e1512',
            '--surface': '#14201b',
            '--text': '#e9fff1',
            '--muted': '#cfe9db',
            '--primary': '#2ecc71',
            '--primary-contrast': '#08110e',
            '--accent': '#1abc9c',
            '--border': '#1b332a',
            '--shadow': 'rgba(0, 0, 0, 0.45)',
            // Dino
            '--day': '#E8F5E9',
            '--night': '#0e1512',
            '--tree-day': '#2ecc71',
            '--tree-night': '#08110e',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#1b332a',
            '--sun-day': '#F1C40F',
            '--sun-night': '#D35400',
            '--moon-day': '#fff',
            '--moon-night': '#CFE9DB',
            '--sky-day': '#E8F5E9',
            '--sky-night': '#0e1512',
        }
    },
    {
        id: 'theme-slate',
        name: 'Midnight Slate',
        type: 'default',
        colors: {
            '--bg': '#0b0d12',
            '--surface': '#121723',
            '--text': '#f1f5f9',
            '--muted': '#c7d0dd',
            '--primary': '#7aa2f7',
            '--primary-contrast': '#0b0d12',
            '--accent': '#a6adc8',
            '--border': '#202534',
            '--shadow': 'rgba(2, 4, 9, 0.55)',
            // Dino
            '--day': '#F1F5F9',
            '--night': '#0b0d12',
            '--tree-day': '#7aa2f7',
            '--tree-night': '#0b0d12',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#202534',
            '--sun-day': '#F9A8D4',
            '--sun-night': '#7C3AED',
            '--moon-day': '#fff',
            '--moon-night': '#C7D0DD',
            '--sky-day': '#E2E8F0',
            '--sky-night': '#0b0d12',
        }
    },
    {
        id: 'theme-mint',
        name: 'Coral Mint',
        type: 'default',
        colors: {
            '--bg': '#2A363B',
            '--surface': '#99B898',
            '--text': '#0b0f12',
            '--muted': '#ffeadc',
            '--primary': '#E84A5F',
            '--primary-contrast': '#0b0f12',
            '--accent': '#FF847C',
            '--border': '#3b4950',
            '--shadow': 'rgba(0,0,0,0.5)',
            // Dino
            '--day': '#FFDAB9',
            '--night': '#2A363B',
            '--tree-day': '#2A363B',
            '--tree-night': '#99B898',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#3b4950',
            '--sun-day': '#E84A5F',
            '--sun-night': '#C0392B',
            '--moon-day': '#fff',
            '--moon-night': '#FFEADC',
            '--sky-day': '#FFDAB9',
            '--sky-night': '#2A363B',
        }
    },
    {
        id: 'theme-blush',
        name: 'Blush Tide',
        type: 'default',
        colors: {
            '--bg': '#305F72',
            '--surface': '#F1D1B5',
            '--text': '#10222b',
            '--muted': '#f7e7dc',
            '--primary': '#F18C8E',
            '--primary-contrast': '#221a15',
            '--accent': '#56BEA6',
            '--border': '#3b7187',
            '--shadow': 'rgba(3, 19, 33, 0.5)',
            // Dino
            '--day': '#E0F2F1',
            '--night': '#305F72',
            '--tree-day': '#305F72',
            '--tree-night': '#10222b',
            '--cloud-day': '#ffffff',
            '--cloud-night': '#3b7187',
            '--sun-day': '#F18C8E',
            '--sun-night': '#C0392B',
            '--moon-day': '#fff',
            '--moon-night': '#F7E7DC',
            '--sky-day': '#B2DFDB',
            '--sky-night': '#305F72',
        }
    },
    {
        id: 'theme-vibrant',
        name: 'Vibrant Warm',
        type: 'default',
        colors: {
            '--bg': '#344E5C',
            '--surface': '#4AB19D',
            '--text': '#061016',
            '--muted': '#ffeeb9',
            '--primary': '#EF3D59',
            '--primary-contrast': '#16070b',
            '--accent': '#E17A47',
            '--border': '#3e5c6c',
            '--shadow': 'rgba(10, 19, 26, 0.5)',
            // Dino
            '--day': '#FFF8E1',
            '--night': '#344E5C',
            '--tree-day': '#344E5C',
            '--tree-night': '#061016',
            '--cloud-day': '#D9C974',
            '--cloud-night': '#3e5c6c',
            '--sun-day': '#EF3D59',
            '--sun-night': '#C0392B',
            '--moon-day': '#fff',
            '--moon-night': '#FFEEB9',
            '--sky-day': '#FFECB3',
            '--sky-night': '#344E5C',
        }
    },
    {
        id: 'theme-plum',
        name: 'Mulberry Mist',
        type: 'default',
        colors: {
            '--bg': '#1A1A1D',
            '--surface': '#3B1C32',
            '--text': '#f7ecf4',
            '--muted': '#e7cfe0',
            '--primary': '#A64D79',
            '--primary-contrast': '#0e0d10',
            '--accent': '#6A1E55',
            '--border': '#4a2a40',
            '--shadow': 'rgba(0,0,0,0.55)',
            // Dino
            '--day': '#F3E5F5',
            '--night': '#1A1A1D',
            '--tree-day': '#A64D79',
            '--tree-night': '#3B1C32',
            '--cloud-day': '#fff',
            '--cloud-night': '#4a2a40',
            '--sun-day': '#E1BEE7',
            '--sun-night': '#8E24AA',
            '--moon-day': '#fff',
            '--moon-night': '#E7CFE0',
            '--sky-day': '#F3E5F5',
            '--sky-night': '#1A1A1D',
        }
    },
    {
        id: 'theme-yellow',
        name: 'Golden Ember',
        type: 'default',
        colors: {
            '--bg': '#FFF7B0',
            '--surface': '#FFE680',
            '--text': '#2C2C2C',
            '--muted': '#A18F3B',
            '--primary': '#F2B01E',
            '--primary-contrast': '#ffffff',
            '--accent': '#E3A500',
            '--border': '#C69C00',
            '--shadow': 'rgba(0,0,0,0.25)',
            // Dino
            '--day': '#FFF7B0',
            '--night': '#2C2B28',
            '--tree-day': '#2C2B28',
            '--tree-night': '#FFE680',
            '--cloud-day': '#FFE680',
            '--cloud-night': '#554d24',
            '--sun-day': '#F2B01E',
            '--sun-night': '#F2B01E',
            '--moon-day': '#FFFFFF',
            '--moon-night': '#FFE680',
            '--sky-day': '#FFF7B0',
            '--sky-night': '#2C2B28',
        }
    },
    {
        id: 'theme-yellow-dark',
        name: 'Golden Eclipse',
        type: 'default',
        colors: {
            '--bg': '#2C2B28',
            '--surface': '#3B392F',
            '--text': '#FFF7B0',
            '--muted': '#D9C974',
            '--primary': '#F2B01E',
            '--primary-contrast': '#2C2B28',
            '--accent': '#E3A500',
            '--border': '#C69C00',
            '--shadow': 'rgba(0,0,0,0.55)',
            // Dino
            '--day': '#FFF7B0',
            '--night': '#2C2B28',
            '--tree-day': '#D9C974',
            '--tree-night': '#FFFFE0',
            '--cloud-day': '#D9C974',
            '--cloud-night': '#554d24',
            '--sun-day': '#F2B01E',
            '--sun-night': '#B8860B',
            '--moon-day': '#fff',
            '--moon-night': '#FFF7B0',
            '--sky-day': '#FFFFE0',
            '--sky-night': '#2C2B28',
        }
    },
    {
        id: 'theme-crimson',
        name: 'Crimson Blaze',
        type: 'default',
        colors: {
            '--bg': '#00224D',
            '--surface': '#5D0E41',
            '--text': '#FDECEC',
            '--muted': '#E6B7BE',
            '--primary': '#FF204E',
            '--primary-contrast': '#0F0F1F',
            '--accent': '#A0153E',
            '--border': '#3B0B2E',
            '--shadow': 'rgba(0, 0, 0, 0.5)',
            // Dino
            '--day': '#FFEBEE',
            '--night': '#00224D',
            '--tree-day': '#5D0E41',
            '--tree-night': '#000',
            '--cloud-day': '#fff',
            '--cloud-night': '#3B0B2E',
            '--sun-day': '#FF204E',
            '--sun-night': '#8B0000',
            '--moon-day': '#fff',
            '--moon-night': '#E6B7BE',
            '--sky-day': '#FFEBEE',
            '--sky-night': '#00224D',
        }
    },
    {
        id: 'theme-inferno',
        name: 'Inferno Burst',
        type: 'default',
        colors: {
            '--bg': '#52006A',
            '--surface': '#7A0B57',
            '--text': '#FFF2E5',
            '--muted': '#FFCDA6',
            '--primary': '#FFA900',
            '--primary-contrast': '#1A0B0F',
            '--accent': '#FF7600',
            '--border': '#8A1A3C',
            '--shadow': 'rgba(0, 0, 0, 0.45)',
            // Dino
            '--day': '#FFF3E0',
            '--night': '#52006A',
            '--tree-day': '#7A0B57',
            '--tree-night': '#220030',
            '--cloud-day': '#fff',
            '--cloud-night': '#8A1A3C',
            '--sun-day': '#FFA900',
            '--sun-night': '#D35400',
            '--moon-day': '#fff',
            '--moon-night': '#FFCDA6',
            '--sky-day': '#FFF3E0',
            '--sky-night': '#52006A',
        }
    },
    {
        id: 'theme-rosewood',
        name: 'Rosewood Velvet',
        type: 'default',
        colors: {
            '--bg': '#3A0519',
            '--surface': '#670D2F',
            '--text': '#FFF3F7',
            '--muted': '#E7B3C3',
            '--primary': '#A53860',
            '--primary-contrast': '#15040A',
            '--accent': '#EF88AD',
            '--border': '#53132E',
            '--shadow': 'rgba(0, 0, 0, 0.45)',
            // Dino
            '--day': '#FCE4EC',
            '--night': '#3A0519',
            '--tree-day': '#670D2F',
            '--tree-night': '#15040A',
            '--cloud-day': '#fff',
            '--cloud-night': '#53132E',
            '--sun-day': '#EF88AD',
            '--sun-night': '#880E4F',
            '--moon-day': '#fff',
            '--moon-night': '#E7B3C3',
            '--sky-day': '#F8BBD0',
            '--sky-night': '#3A0519',
        }
    },
    {
        id: 'theme-ember',
        name: 'Ember Noir',
        type: 'default',
        colors: {
            '--bg': '#1B1833',
            '--surface': '#441752',
            '--text': '#FFF9F0',
            '--muted': '#E6C9AE',
            '--primary': '#F29F58',
            '--primary-contrast': '#1A0E12',
            '--accent': '#AB4459',
            '--border': '#2C143D',
            '--shadow': 'rgba(0, 0, 0, 0.5)',
            // Dino
            '--day': '#FFFDE7',
            '--night': '#1B1833',
            '--tree-day': '#441752',
            '--tree-night': '#0a0815',
            '--cloud-day': '#fff',
            '--cloud-night': '#2C143D',
            '--sun-day': '#F29F58',
            '--sun-night': '#D35400',
            '--moon-day': '#fff',
            '--moon-night': '#E6C9AE',
            '--sky-day': '#FFFDE7',
            '--sky-night': '#1B1833',
        }
    },
    {
        id: 'theme-amethyst',
        name: 'Amethyst Dream',
        type: 'default',
        colors: {
            '--bg': '#3E1E68',
            '--surface': '#5D2F77',
            '--text': '#FFF5F9',
            '--muted': '#F9CEDC',
            '--primary': '#E45A92',
            '--primary-contrast': '#220B2D',
            '--accent': '#FFACAC',
            '--border': '#4A276F',
            '--shadow': 'rgba(10, 0, 30, 0.5)',
            // Dino
            '--day': '#EDE7F6',
            '--night': '#3E1E68',
            '--tree-day': '#E45A92',
            '--tree-night': '#220B2D',
            '--cloud-day': '#fff',
            '--cloud-night': '#4A276F',
            '--sun-day': '#FFACAC',
            '--sun-night': '#C2185B',
            '--moon-day': '#fff',
            '--moon-night': '#F9CEDC',
            '--sky-day': '#EDE7F6',
            '--sky-night': '#3E1E68',
        }
    },
];

const ThemeContext = createContext(null);

export function useTheme() {
    return useContext(ThemeContext);
}

export function ThemeProvider({ children }) {
    // Load themes from storage (combines default + user created)
    const [themes, setThemes] = useState(() => {
        const saved = localStorage.getItem('bci_all_themes');
        if (saved) return JSON.parse(saved);
        return DEFAULT_THEMES;
    });

    // Current theme ID
    const [currentThemeId, setCurrentThemeId] = useState(() => {
        const saved = localStorage.getItem('theme');
        // Note: old code used 'theme-rose' class names.
        // We can support that as an ID.
        // If the saved theme is not in our list, fallback to first one.
        return saved || DEFAULT_THEMES[0].id;
    });

    // Derived current theme object
    const currentTheme = themes.find(t => t.id === currentThemeId) || themes[0];

    useEffect(() => {
        // Save current theme selection
        localStorage.setItem('theme', currentThemeId);

        // Save all themes (data)
        localStorage.setItem('bci_all_themes', JSON.stringify(themes));

        // Apply variables to root
        const root = document.documentElement;

        // First, remove old class-based theme hooks if any remain (from old app version)
        root.className = 'root';

        // Add specific class for Tailwind specificity if needed, though variables are usually enough
        // We add 'theme-active' just in case we need a hook
        root.classList.add('theme-active');

        // Apply all CSS variables
        Object.entries(currentTheme.colors).forEach(([key, value]) => {
            root.style.setProperty(key, value);
        });

        // Semantic Overrides helper (dino etc) that might resort to defaults in CSS if missing
        // We just ensure our themes have them all.

    }, [currentTheme, currentThemeId, themes]);

    const addTheme = (name) => {
        const id = `theme-custom-${Date.now()}`;
        const newTheme = {
            id,
            name,
            type: 'custom',
            colors: { ...currentTheme.colors } // Clone current as base
        };
        setThemes([...themes, newTheme]);
        setCurrentThemeId(id);
        return id;
    };

    const updateTheme = (id, updates) => {
        setThemes(prev => prev.map(t => {
            if (t.id !== id) return t;
            // Merge updates
            return { ...t, ...updates };
        }));
    };

    const updateThemeColor = (id, colorKey, value) => {
        setThemes(prev => prev.map(t => {
            if (t.id !== id) return t;
            return {
                ...t,
                colors: { ...t.colors, [colorKey]: value }
            };
        }));
    };

    const removeTheme = (id) => {
        const themeToDelete = themes.find(t => t.id === id);
        if (!themeToDelete || themeToDelete.type === 'default') {
            alert('Cannot delete default themes!');
            return;
        }

        const newThemes = themes.filter(t => t.id !== id);
        setThemes(newThemes);

        if (currentThemeId === id) {
            setCurrentThemeId(newThemes[0].id);
        }
    };

    const resetThemes = () => {
        if (window.confirm('Are you sure you want to reset all themes to default? Custom themes will be lost.')) {
            setThemes(DEFAULT_THEMES);
            setCurrentThemeId(DEFAULT_THEMES[0].id);
        }
    };

    return (
        <ThemeContext.Provider value={{
            themes,
            currentTheme,
            currentThemeId,
            setTheme: setCurrentThemeId,
            addTheme,
            updateTheme,
            updateThemeColor,
            removeTheme,
            resetThemes
        }}>
            {children}
        </ThemeContext.Provider>
    );
}
