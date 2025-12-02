// src/components/EncryptText.js
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import PropTypes from 'prop-types';
import './EncryptText.css';

/**
 * EncryptText
 * - Hover to scramble (encrypt). Leave to revert (decrypt).
 * - Supports sequential (progressive) scrambling and independent directions for encrypt/decrypt.
 *
 * Fix: ensure animation restarts correctly on repeated hovers by resetting
 * refs/state on mouse enter and cleaning intervals reliably.
 */
const EncryptText = ({
  text,
  speed = 40,
  maxIterations = 12,
  characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+',
  className = 'encrypt-text',
  encryptedClassName = 'encrypted',
  sequential = false,
  encryptDirection = 'start', // 'start' | 'end' | 'center'
  decryptDirection = 'start', // 'start' | 'end' | 'center'
  ...props
}) => {
  const [displayText, setDisplayText] = useState(text);
  const [isHovering, setIsHovering] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  // refs to manage state across intervals without causing re-renders
  const scrambledSetRef = useRef(new Set()); // indices that are currently scrambled
  const intervalRef = useRef(null);
  const charsArrayRef = useRef(characters.split(''));
  const encryptOrderRef = useRef([]); // order for sequential encrypt
  const decryptOrderRef = useRef([]); // order for sequential decrypt
  const encryptPointerRef = useRef(0); // pointer into encrypt order
  const decryptPointerRef = useRef(0); // pointer into decrypt order

  // keep chars array updated
  useEffect(() => {
    charsArrayRef.current = characters.split('');
  }, [characters]);

  // produce index order for given direction (non-space indices)
  const computeOrderForDirection = useCallback(
    (dir) => {
      const len = text.length;
      const indices = [];
      for (let i = 0; i < len; i++) if (text[i] !== ' ') indices.push(i);

      if (dir === 'start') return indices;
      if (dir === 'end') return indices.slice().reverse();

      // center: pick closest to middle first (tie -> right)
      const out = [];
      const middle = Math.floor(len / 2);
      const candidates = indices.slice();
      while (candidates.length) {
        let closest = -1;
        let bestDist = Infinity;
        for (let idx of candidates) {
          const dist = Math.abs(idx - middle);
          if (dist < bestDist) {
            bestDist = dist;
            closest = idx;
          } else if (dist === bestDist && idx > closest) {
            // tie break prefer right side
            closest = idx;
          }
        }
        out.push(closest);
        candidates.splice(candidates.indexOf(closest), 1);
      }
      return out;
    },
    [text]
  );

  // scramble all non-space chars randomly
  const scrambleAll = useCallback(
    (source) => {
      const chars = charsArrayRef.current;
      return source
        .split('')
        .map((ch) => (ch === ' ' ? ' ' : chars[Math.floor(Math.random() * chars.length)]))
        .join('');
    },
    []
  );

  // build the string using scrambledSetRef (sequential mode)
  const buildFromScrambledSet = useCallback(() => {
    const s = scrambledSetRef.current;
    const chars = charsArrayRef.current;
    return text
      .split('')
      .map((ch, i) => {
        if (ch === ' ') return ' ';
        if (s.has(i)) return chars[Math.floor(Math.random() * chars.length)];
        return ch;
      })
      .join('');
  }, [text]);

  // reset everything when text changes
  useEffect(() => {
    clearInterval(intervalRef.current);
    scrambledSetRef.current = new Set();
    encryptOrderRef.current = computeOrderForDirection(encryptDirection);
    decryptOrderRef.current = computeOrderForDirection(decryptDirection);
    encryptPointerRef.current = 0;
    decryptPointerRef.current = 0;
    setDisplayText(text);
    setIsAnimating(false);
    return () => clearInterval(intervalRef.current);
  }, [text, computeOrderForDirection, encryptDirection, decryptDirection]);

  // Ensure interval cleanup helper
  const clearAnimInterval = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Main animation effect depends on isHovering and other settings
  useEffect(() => {
    clearAnimInterval();
    let iteration = 0;

    if (isHovering) {
      setIsAnimating(true);

      if (sequential) {
        // sequential encryption: step through encryptOrderRef
        intervalRef.current = setInterval(() => {
          const order = encryptOrderRef.current;
          const ptr = encryptPointerRef.current;

          if (ptr >= order.length) {
            // fully scrambled
            setDisplayText(scrambleAll(text));
            clearAnimInterval();
            return;
          }

          const idx = order[ptr];
          scrambledSetRef.current.add(idx);
          encryptPointerRef.current = ptr + 1;
          setDisplayText(buildFromScrambledSet());

          if (encryptPointerRef.current >= order.length) {
            clearAnimInterval();
          }
        }, speed);
      } else {
        // non-sequential: randomize whole text each tick, stop after maxIterations
        intervalRef.current = setInterval(() => {
          setDisplayText(scrambleAll(text));
          iteration++;
          if (iteration >= maxIterations) {
            clearAnimInterval();
            setDisplayText(scrambleAll(text));
          }
        }, speed);
      }
    } else {
      // decrypt (mouse leave)
      setIsAnimating(true);

      if (sequential) {
        // sequential decryption: reveal based on decrypt order
        intervalRef.current = setInterval(() => {
          const order = decryptOrderRef.current;
          // find next scrambled index according to decrypt order
          let found = -1;
          while (decryptPointerRef.current < order.length) {
            const cand = order[decryptPointerRef.current];
            decryptPointerRef.current++;
            if (scrambledSetRef.current.has(cand)) {
              found = cand;
              break;
            }
          }

          if (found === -1) {
            // fallback: if nothing found, remove any remaining scrambled index
            const anyLeft = Array.from(scrambledSetRef.current)[0];
            if (anyLeft === undefined) {
              setDisplayText(text);
              setIsAnimating(false);
              clearAnimInterval();
              return;
            }
            scrambledSetRef.current.delete(anyLeft);
            setDisplayText(buildFromScrambledSet());
            return;
          }

          scrambledSetRef.current.delete(found);
          setDisplayText(buildFromScrambledSet());

          if (scrambledSetRef.current.size === 0) {
            setDisplayText(text);
            setIsAnimating(false);
            clearAnimInterval();
          }
        }, speed);
      } else {
        // non-sequential decrypt: randomize few times then reveal
        intervalRef.current = setInterval(() => {
          iteration++;
          if (iteration >= Math.ceil(maxIterations / 2)) {
            setDisplayText(text);
            setIsAnimating(false);
            clearAnimInterval();
          } else {
            setDisplayText(scrambleAll(text));
          }
        }, speed);
      }
    }

    return () => clearAnimInterval();
  }, [isHovering, speed, maxIterations, sequential, scrambleAll, buildFromScrambledSet, clearAnimInterval, text]);

  // NEW: handlers that reset refs/state so repeated hovers animate correctly
  const handleMouseEnter = () => {
    clearAnimInterval();
    // Reset scrambled set & pointers so the animation starts fresh
    scrambledSetRef.current = new Set();
    encryptOrderRef.current = computeOrderForDirection(encryptDirection);
    decryptOrderRef.current = computeOrderForDirection(decryptDirection);
    encryptPointerRef.current = 0;
    decryptPointerRef.current = 0;
    // Ensure starting from original text to animate into scrambled
    setDisplayText(text);
    setIsAnimating(true);
    setIsHovering(true);
  };

  const handleMouseLeave = () => {
    clearAnimInterval();
    // prepare decrypt pointers, don't fully reset encrypt pointer so decrypt can reveal correctly
    decryptPointerRef.current = 0;
    setIsHovering(false);
    // isAnimating will be cleared by effect when fully decrypted
  };

  return (
    <motion.span
      className={`wrapper ${className}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      <span className="srOnly" aria-hidden="true">
        {text}
      </span>

      <span aria-hidden="true">
        {displayText.split('').map((char, i) => {
          const currentlyEncrypted = isAnimating && (sequential ? scrambledSetRef.current.has(i) : isHovering);
          const usedClass = currentlyEncrypted ? encryptedClassName : className;
          return (
            <span key={i} className={usedClass} style={{ transition: 'color 0.25s ease' }}>
              {char}
            </span>
          );
        })}
      </span>
    </motion.span>
  );
};

EncryptText.propTypes = {
  text: PropTypes.string.isRequired,
  speed: PropTypes.number,
  maxIterations: PropTypes.number,
  characters: PropTypes.string,
  className: PropTypes.string,
  encryptedClassName: PropTypes.string,
  sequential: PropTypes.bool,
  encryptDirection: PropTypes.oneOf(['start', 'end', 'center']),
  decryptDirection: PropTypes.oneOf(['start', 'end', 'center']),
};

export default EncryptText;
