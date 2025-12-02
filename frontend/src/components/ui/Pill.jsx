import React, { useRef, useEffect } from 'react';
import { gsap } from 'gsap';
import './PillNav.css';

const Pill = ({
  label,
  href = '#',
  onClick,
  isActive = false,
  baseColor = '#fff',
  pillColor = '#060010',
  hoveredTextColor = '#060010',
  pillTextColor = '#fff',
  ease = 'power3.easeOut',
  as = 'a',
  pillWidth,
  pillHeight,  
  ...props
}) => {
  const circleRef = useRef(null);
  const labelRef = useRef(null);
  const hoverLabelRef = useRef(null);
  const tlRef = useRef(null);
  const activeTweenRef = useRef(null);

  useEffect(() => {
    const circle = circleRef.current;
    const label = labelRef.current;
    const white = hoverLabelRef.current;
    const pill = circle?.parentElement;
    if (!circle || !pill) return;

    const w = pillWidth || pill.offsetWidth;
    const h = pillHeight || pill.offsetHeight;
    const R = ((w * w) / 4 + h * h) / (2 * h);
    const D = Math.ceil(2 * R) + 2;
    const delta = Math.ceil(R - Math.sqrt(Math.max(0, R * R - (w * w) / 4))) + 1;
    const originY = D - delta;

    circle.style.width = `${D}px`;
    circle.style.height = `${D}px`;
    circle.style.bottom = `-${delta}px`;

    gsap.set(circle, { xPercent: -50, scale: 0, transformOrigin: `50% ${originY}px` });
    if (label) gsap.set(label, { y: 0 });
    if (white) gsap.set(white, { y: h + 12, opacity: 0 });

    const tl = gsap.timeline({ paused: true });
    tl.to(circle, { scale: 1.2, xPercent: -50, duration: 2, ease }, 0);
    if (label) tl.to(label, { y: -(h + 8), duration: 2, ease }, 0);
    if (white) {
      gsap.set(white, { y: Math.ceil(h + 100), opacity: 0 });
      tl.to(white, { y: 0, opacity: 1, duration: 2, ease }, 0);
    }
    tlRef.current = tl;
  }, [label, ease, pillWidth, pillHeight]);

  const handleEnter = () => {
    const tl = tlRef.current;
    if (!tl) return;
    activeTweenRef.current?.kill();
    activeTweenRef.current = tl.tweenTo(tl.duration(), {
      duration: 0.3,
      ease,
      overwrite: 'auto'
    });
  };

  const handleLeave = () => {
    const tl = tlRef.current;
    if (!tl) return;
    activeTweenRef.current?.kill();
    activeTweenRef.current = tl.tweenTo(0, {
      duration: 0.2,
      ease,
      overwrite: 'auto'
    });
  };

  const Element = as;

  const cssVars = {
    '--base': baseColor,
    '--pill-bg': pillColor,
    '--hover-text': hoveredTextColor,
    '--pill-text': pillTextColor
  };

  const inlineStyle = {
    width: pillWidth ? `${pillWidth}px` : 'auto',
    height: pillHeight ? `${pillHeight}px` : 'auto',
    ...cssVars,
  };

  return (
    <Element
      href={as === 'a' ? href : undefined}
      className={`pill${isActive ? ' is-active' : ''}`}
      onClick={onClick}
      style={inlineStyle}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      {...props}
    >
      <span className="hover-circle" aria-hidden="true" ref={circleRef}></span>
      <span className="label-stack">
        <span className="pill-label" ref={labelRef}>{label}</span>
        <span className="pill-label-hover" ref={hoverLabelRef} aria-hidden="true">{label}</span>
      </span>
    </Element>
  );
};

export default Pill;
