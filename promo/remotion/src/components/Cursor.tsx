import React from 'react';

/** Crisp UKUI/macOS-like arrow cursor. Tip at (0,0). size = height in px */
export const Arrow: React.FC<{size?: number; pressed?: number}> = ({size = 44, pressed = 0}) => {
  const s = size / 24;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{position: 'absolute', left: -2 * s, top: -1.2 * s, overflow: 'visible',
      transform: `scale(${1 - 0.14 * pressed})`, transformOrigin: `${2 * s}px ${1.2 * s}px`, filter: 'drop-shadow(0 2px 3px rgba(0,0,0,0.45))'}}>
      <path d="M2 1.2 L2 19.6 L6.6 15.4 L9.7 22.3 L12.9 20.9 L9.9 14.1 L16.2 14.1 Z" fill="#111" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
};

export const Ripple: React.FC<{age: number; scale?: number; color?: string}> = ({age, scale = 1, color = '79,227,255'}) => {
  if (age < 0 || age > 0.6) return null;
  const p = age / 0.6;
  const e = 1 - Math.pow(1 - p, 3);
  const r = (10 + 46 * e) * scale;
  return (
    <>
      <div style={{position: 'absolute', left: -r, top: -r, width: 2 * r, height: 2 * r, borderRadius: '50%',
        border: `${3 * scale}px solid rgba(${color},${0.9 * (1 - p)})`, boxShadow: `0 0 ${18 * scale}px rgba(${color},${0.5 * (1 - p)})`}} />
      <div style={{position: 'absolute', left: -r * 0.55, top: -r * 0.55, width: 1.1 * r, height: 1.1 * r, borderRadius: '50%',
        background: `rgba(${color},${0.28 * (1 - p)})`}} />
    </>
  );
};
