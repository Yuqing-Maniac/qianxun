import React from 'react';

/** Animated 千寻 icon. bg: 0..1 background reveal, ring: 0..1 stroke draw, handle 0..1, lines 0..1 (staggered) */
export const AppIcon: React.FC<{size: number; bg?: number; ring?: number; handle?: number; lines?: number; glow?: number; style?: React.CSSProperties; id?: string}> = ({
  size, bg = 1, ring = 1, handle = 1, lines = 1, glow = 0, style, id = 'ic',
}) => {
  const circ = 2 * Math.PI * 62;
  const hl = Math.hypot(62, 62);
  const L = [[80, 88, 136], [86, 108, 130], [94, 128, 122]];
  return (
    <svg width={size} height={size} viewBox="0 0 256 256" style={{overflow: 'visible', ...style}}>
      <defs>
        <linearGradient id={id + 'bg'} x1="0" y1="0" x2="256" y2="256" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#1E4FD8" />
          <stop offset="1" stopColor="#13A3C2" />
        </linearGradient>
        <linearGradient id={id + 'hl'} x1="0" y1="0" x2="0" y2="256" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#fff" stopOpacity="0.28" />
          <stop offset="0.5" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <filter id={id + 'gl'} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="10" />
        </filter>
      </defs>
      {glow > 0 && <rect x="8" y="8" width="240" height="240" rx="52" fill="#2E8BFF" opacity={0.55 * glow} filter={`url(#${id}gl)`} />}
      <g style={{transformOrigin: '128px 128px', transform: `scale(${0.4 + 0.6 * bg})`}} opacity={bg}>
        <rect x="0" y="0" width="256" height="256" rx="52" ry="52" fill={`url(#${id}bg)`} />
        <rect x="0" y="0" width="256" height="256" rx="52" ry="52" fill={`url(#${id}hl)`} />
      </g>
      <g fill="none" stroke="#FFFFFF" strokeLinecap="round">
        <circle cx="108" cy="108" r="62" strokeWidth="22" strokeDasharray={circ} strokeDashoffset={circ * (1 - ring)} transform="rotate(-135 108 108)" opacity={ring > 0.001 ? 1 : 0} />
        <line x1="152" y1="152" x2="214" y2="214" strokeWidth="22" strokeDasharray={hl} strokeDashoffset={hl * (1 - handle)} opacity={handle > 0.001 ? 1 : 0} />
      </g>
      <g stroke="#FFFFFF" strokeWidth="12" strokeLinecap="round" opacity="0.9">
        {L.map(([x1, y, x2], i) => {
          const p = Math.max(0, Math.min(1, lines * 3 - i));
          if (p <= 0) return null;
          return <line key={i} x1={x1} y1={y} x2={x1 + (x2 - x1) * p} y2={y} />;
        })}
      </g>
    </svg>
  );
};
