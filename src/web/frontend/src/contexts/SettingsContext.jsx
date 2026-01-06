import React, { createContext, useContext, useState, useEffect } from 'react';

const SettingsContext = createContext(null);

export const useSettings = () => {
    const context = useContext(SettingsContext);
    if (!context) {
        throw new Error('useSettings must be used within a SettingsProvider');
    }
    return context;
};

const DEFAULT_SETTINGS = {
    general: {
        apiUrl: 'http://localhost:8000',
        wsUrl: 'ws://localhost:1972',
        useMock: false,
    },
    dino: {
        gravity: 0.6,
        jumpStrength: 10,
        gameSpeed: 5,
        obstacleDensity: 1500,
        controlChannel: 0,
        difficulty: 'normal', // easy, normal, hard
        visuals: {
            showTrees: true,
            showClouds: true,
            showStars: true,
            dayNightCycle: true,
        }
    },
    ssvep: {
        brightness: 100, // 0-100
        refreshRate: 60,
        protocol: {
            cueDuration: 2,
            stimDuration: 5,
            restDuration: 3,
            rounds: 5,
        }
    },
    rps: {
        manualMode: false,
        difficulty: 1, // 0-2 (Easy, Medium, Hard)
    },
    calibration: {
        activeSensor: 'EMG', // EMG, EOG, EEG
        activeChannel: 0,
        yAxisRange: 200,
        zoomLevel: 1,
        timeWindow: 5, // seconds
    },
    ml: {
        emg: {
            n_estimators: 100,
            max_depth: 10,
            test_size: 0.2,
            selectedChannel: 0,
        },
        eog: {
            n_estimators: 100,
            max_depth: 10,
            test_size: 0.2,
            selectedChannel: 0,
        }
    }
};

export function SettingsProvider({ children }) {
    const [settings, setSettings] = useState(() => {
        try {
            const saved = localStorage.getItem('neurotech_settings');
            if (saved) {
                // Deep merge with defaults to ensure new fields are added if missing in old save
                const parsed = JSON.parse(saved);
                return deepMerge(DEFAULT_SETTINGS, parsed);
            }
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
        return DEFAULT_SETTINGS;
    });

    // Save to localStorage whenever settings change
    useEffect(() => {
        localStorage.setItem('neurotech_settings', JSON.stringify(settings));
    }, [settings]);

    // Update a specific setting section
    const updateSettings = (section, newValues) => {
        setSettings(prev => ({
            ...prev,
            [section]: {
                ...prev[section],
                ...newValues
            }
        }));
    };

    // Deep update helper (for nested objects like dino.visuals)
    const updateDeepSettings = (path, value) => {
        setSettings(prev => {
            const next = { ...prev };
            const keys = path.split('.');
            let current = next;
            for (let i = 0; i < keys.length - 1; i++) {
                current[keys[i]] = { ...current[keys[i]] };
                current = current[keys[i]];
            }
            current[keys[keys.length - 1]] = value;
            return next;
        });
    };

    // Reset a section or all to defaults
    const resetSettings = (section = null) => {
        if (section) {
            setSettings(prev => ({
                ...prev,
                [section]: DEFAULT_SETTINGS[section]
            }));
        } else {
            setSettings(DEFAULT_SETTINGS);
        }
    };

    return (
        <SettingsContext.Provider value={{
            settings,
            updateSettings,
            updateDeepSettings,
            resetSettings
        }}>
            {children}
        </SettingsContext.Provider>
    );
}

// Simple Deep Merge Helper
function deepMerge(target, source) {
    const result = { ...target };
    if (source) {
        for (const key in source) {
            if (source[key] instanceof Object && key in target) {
                result[key] = deepMerge(target[key], source[key]);
            } else {
                result[key] = source[key];
            }
        }
    }
    return result;
}
