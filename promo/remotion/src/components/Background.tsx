import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {noise2D} from '@remotion/noise';
import {C} from '../theme';

const BLOBS = [
  {c: 'rgba(30,79,216,0.55)', r: 900, x: 0.18, y: 0.25, s: 'a'},
  {c: 'rgba(76,52,190,0.45)', r: 1000, x: 0.85, y: 0.2, s: 'b'},
  {c: 'rgba(19,163,194,0.32)', r: 800, x: 0.75, y: 0.85, s: 'c'},
  {c: 'rgba(42,36,112,0.6)', r: 1100, x: 0.25, y: 0.9, s: 'd'},
];

/** Global branded background: navy→indigo, drifting gradient blobs, dot grid, vignette, grain */
export const Background: React.FC<{intensity?: number; hue?: number; grid?: number}> = ({intensity = 1, hue = 0, grid = 0.5}) => {
  const f = useCurrentFrame();
  const t = f / 30;
  return (
    <AbsoluteFill style={{background: `radial-gradient(120% 90% at 50% 40%, ${C.bg1} 0%, ${C.bg0} 70%)`, overflow: 'hidden'}}>
      <AbsoluteFill style={{filter: hue ? `hue-rotate(${hue}deg)` : undefined, opacity: intensity}}>
        {BLOBS.map((b, i) => {
          const nx = noise2D(b.s + 'x', t * 0.05, i) * 260;
          const ny = noise2D(b.s + 'y', t * 0.05, i + 3) * 180;
          const sc = 1 + noise2D(b.s + 's', t * 0.07, 9) * 0.15;
          return (
            <div key={i} style={{position: 'absolute', left: b.x * 1920 - b.r / 2 + nx, top: b.y * 1080 - b.r / 2 + ny, width: b.r, height: b.r,
              transform: `scale(${sc})`, background: `radial-gradient(circle at 50% 50%, ${b.c} 0%, rgba(0,0,0,0) 68%)`}} />
          );
        })}
      </AbsoluteFill>
      <AbsoluteFill style={{opacity: grid * 0.5,
        backgroundImage: 'radial-gradient(rgba(160,190,255,0.22) 1px, transparent 1.4px)', backgroundSize: '36px 36px',
        backgroundPosition: `${(t * 6) % 36}px ${(t * 3) % 36}px`,
        WebkitMaskImage: 'radial-gradient(70% 60% at 50% 45%, black 0%, transparent 100%)'}} />
      <AbsoluteFill style={{background: 'radial-gradient(130% 100% at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,8,0.65) 100%)'}} />
    </AbsoluteFill>
  );
};

export const Grain: React.FC<{opacity?: number}> = ({opacity = 0.07}) => {
  const f = useCurrentFrame();
  const ox = (f * 73) % 256, oy = (f * 151) % 256;
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity, mixBlendMode: 'overlay',
      backgroundImage: `url(${staticFile('grain.png')})`, backgroundSize: '256px 256px', backgroundPosition: `${ox}px ${oy}px`}} />
  );
};
export const _img = Img;
