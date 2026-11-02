import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {TL, SMILEY} from '../theme';

const clean = (s: string) => s.replace(/[。；：，！？、]+$/u, '').replace(/[，；]/gu, '　');

export const Subtitles: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / 30;
  const cur = TL.sentences.find((s) => t >= s.start - 0.1 && t <= s.start + s.dur + 0.25);
  if (!cur) return null;
  const a = (cur.start - 0.1) * 30, b = (cur.start + cur.dur + 0.25) * 30;
  const op = interpolate(f, [a, a + 6, b - 6, b], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const y = interpolate(f, [a, a + 8], [8, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 60, pointerEvents: 'none'}}>
      <div style={{opacity: op, transform: `translateY(${y}px)`, whiteSpace: 'nowrap', fontFamily: SMILEY, fontSize: 55, lineHeight: '72px',
        color: '#FFFFFF', padding: '6px 30px 8px', borderRadius: 16, background: 'rgba(4,8,24,0.42)',
        boxShadow: '0 8px 30px rgba(0,0,0,0.25)', textShadow: '0 2px 10px rgba(0,0,0,0.65), 0 0 2px rgba(0,0,0,0.5)', letterSpacing: 1}}>
        {clean(cur.text)}
      </div>
    </AbsoluteFill>
  );
};
