import React from 'react';
import {FONT} from '../theme';

export const Glass: React.FC<{style?: React.CSSProperties; children?: React.ReactNode; strong?: boolean}> = ({style, children, strong}) => (
  <div style={{position: 'absolute', borderRadius: 24, background: strong ? 'linear-gradient(160deg, rgba(40,60,130,0.72), rgba(14,22,58,0.78))' : 'linear-gradient(160deg, rgba(255,255,255,0.12), rgba(255,255,255,0.04))',
    border: '1px solid rgba(255,255,255,0.16)', boxShadow: '0 30px 80px rgba(0,0,20,0.45), inset 0 1px 0 rgba(255,255,255,0.18)',
    backdropFilter: 'blur(22px)', WebkitBackdropFilter: 'blur(22px)', fontFamily: FONT, color: '#EAF1FF', ...style}}>
    {children}
  </div>
);

export const Capsule: React.FC<{children: React.ReactNode; color?: string; style?: React.CSSProperties}> = ({children, color = '#4FE3FF', style}) => (
  <div style={{display: 'inline-flex', alignItems: 'center', gap: 12, padding: '12px 26px', borderRadius: 999, background: 'rgba(12,22,60,0.72)',
    border: `1.5px solid ${color}88`, boxShadow: `0 0 30px ${color}33, 0 14px 40px rgba(0,0,0,0.35)`, backdropFilter: 'blur(14px)', fontFamily: FONT,
    color: '#EAF1FF', fontSize: 34, fontWeight: 700, whiteSpace: 'nowrap', ...style}}>
    {children}
  </div>
);

/** gradient text helper */
export const gradText = (a = '#FFFFFF', b = '#9FD8FF'): React.CSSProperties => ({background: `linear-gradient(180deg, ${a}, ${b})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent'});
