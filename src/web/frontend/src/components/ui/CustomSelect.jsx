import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import soundHandler from '../../handlers/SoundHandler';

export default function CustomSelect({
    value,
    onChange,
    options = [],
    disabled = false,
    placeholder = "Select...",
    className = ""
}) {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef(null);

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelect = (optionValue) => {
        if (!disabled) {
            onChange(optionValue);
            setIsOpen(false);
        }
    };

    return (
        <div
            ref={containerRef}
            className={`relative w-full ${disabled ? 'opacity-50 pointer-events-none' : ''} ${className}`}
        >
            {/* Trigger Button */}
            <button
                type="button"
                onClick={() => { soundHandler.playClick(); setIsOpen(!isOpen); }}
                onMouseEnter={() => soundHandler.playHover()}
                className={`
                    w-full px-3 py-2 flex items-center justify-between
                    bg-bg border border-border rounded-lg text-sm
                    hover:border-primary/50 transition-all duration-200
                    focus:outline-none focus:ring-1 focus:ring-primary/50
                    ${isOpen ? 'border-primary/50 ring-1 ring-primary/50' : ''}
                `}
            >
                <span className={`truncate ${!value ? 'text-muted' : 'text-text'}`}>
                    {options.find(opt => (typeof opt === 'object' ? opt.value : opt) === value)?.label || value || placeholder}
                </span>
                <ChevronDown
                    size={16}
                    className={`ml-2 text-muted transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                />
            </button>

            {/* Dropdown Menu */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -5, scale: 0.98 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -5, scale: 0.98 }}
                        transition={{ duration: 0.15, ease: "easeOut" }}
                        className="absolute left-0 right-0 top-full mt-1 z-50 bg-surface border border-border rounded-lg shadow-xl overflow-hidden max-h-60 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']"
                    >
                        <div className="py-1">
                            {options.map((option) => {
                                const optionValue = typeof option === 'object' ? option.value : option;
                                const optionLabel = typeof option === 'object' ? option.label : option;
                                const isSelected = value === optionValue;

                                return (
                                    <button
                                        key={optionValue}
                                        type="button"
                                        onClick={() => { soundHandler.playClick(); handleSelect(optionValue); }}
                                        onMouseEnter={() => soundHandler.playHover()}
                                        className={`
                                            w-full px-3 py-2 text-sm text-left flex items-center justify-between
                                            transition-colors duration-150
                                            ${isSelected
                                                ? 'bg-primary/10 text-primary font-medium'
                                                : 'text-text hover:bg-accent'
                                            }
                                        `}
                                    >
                                        <span>{optionLabel}</span>
                                        {isSelected && <Check size={14} />}
                                    </button>
                                );
                            })}
                            {options.length === 0 && (
                                <div className="px-3 py-2 text-sm text-muted text-center italic">
                                    No options
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
