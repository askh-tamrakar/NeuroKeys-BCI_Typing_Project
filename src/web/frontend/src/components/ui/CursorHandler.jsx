import React, { useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

const CursorHandler = () => {
    const { currentTheme } = useTheme();

    useEffect(() => {
        const primaryColor = currentTheme.colors['--primary'] || '#00ffff';

        const cursorSvg = `
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%" filterUnits="userSpaceOnUse">
                    <feGaussianBlur stdDeviation="4" result="blur"/>
                    <feMerge>
                        <feMergeNode in="blur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
            
            <g transform="translate(16, 16)">
                <!-- Main Arrow with Glow -->
                <path 
                    d="M2 2 L20 8 L10 10 L8 20 Z" 
                    fill="${primaryColor}"
                    fill-opacity="0.4" 
                    stroke="${primaryColor}" 
                    stroke-width="2" 
                    stroke-linejoin="round"
                    filter="url(#glow)"
                />
                
                <!-- Core Solid Shape for sharpness -->
                <path 
                    d="M2 2 L20 8 L10 10 L8 20 Z" 
                    fill="${primaryColor}"
                    fill-opacity="0.2" 
                    stroke="${primaryColor}" 
                    stroke-width="1.5" 
                    stroke-linejoin="round"
                />

                <!-- Inner Highlight -->
                <path 
                    d="M2 2 L20 8 L10 10 L8 20 Z" 
                    stroke="white" 
                    stroke-width="0.8" 
                    stroke-opacity="0.9"
                    stroke-linejoin="round"
                />
            </g>
        </svg>
        `.trim();

        const encodedSvg = encodeURIComponent(cursorSvg);
        const dataUri = `data:image/svg+xml;charset=utf-8,${encodedSvg}`;

        let styleTag = document.getElementById('neon-cursor-style');
        if (!styleTag) {
            styleTag = document.createElement('style');
            styleTag.id = 'neon-cursor-style';
            document.head.appendChild(styleTag);
        }

        // Hotspot set to 18 18 (16 offset + 2 path start)
        styleTag.textContent = `
            body, html, canvas, .recharts-wrapper, .chart-area, .signal-chart-container {
                cursor: url('${dataUri}') 18 18, auto !important;
            }
            
            button, a, [role="button"], input, select, .cursor-pointer, .clickable, .recharts-bg {
                cursor: url('${dataUri}') 18 18, pointer !important;
            }
        `;

        return () => {
            // Persist
        };
    }, [currentTheme]);

    return null;
};

export default CursorHandler;
