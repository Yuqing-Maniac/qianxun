import React from 'react';
import {AbsoluteFill} from 'remotion';
import {FONT, MONO, scene, sStart, prog, EXPO, BACK, spr, C} from '../theme';
import {Glass, gradText} from '../components/Glass';

const Check: React.FC<{p: number; size?: number; color?: string}> = ({p, size = 54, color = '#34D399'}) => (
  <svg width={size} height={size} viewBox="0 0 54 54" style={{opacity: p > 0 ? 1 : 0, transform: `scale(${0.6 + 0.4 * Math.min(1, p)})`}}>
    <circle cx="27" cy="27" r="24" fill={`${color}2A`} stroke={color} strokeWidth="3" />
    <path d="M16 28 l7 7 l15-16" stroke={color} strokeWidth="4.5" fill="none" strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - Math.min(1, p)} />
  </svg>
);

const Chip: React.FC<{title: string; sub: string; lit: number; hue: string}> = ({title, sub, lit, hue}) => (
  <div style={{position: 'relative', width: 420, height: 250}}>
    <svg width="420" height="250" style={{position: 'absolute'}}>
      {new Array(9).fill(0).map((_, i) => <g key={i}>
        <rect x={70 + i * 34} y={4} width={12} height={24} rx={3} fill={lit > 0.5 ? hue : '#3A4670'} opacity={0.8} />
        <rect x={70 + i * 34} y={222} width={12} height={24} rx={3} fill={lit > 0.5 ? hue : '#3A4670'} opacity={0.8} />
      </g>)}
    </svg>
    <div style={{position: 'absolute', left: 30, top: 26, width: 360, height: 198, borderRadius: 22, background: 'linear-gradient(160deg, #1C2A5E, #0E1638)',
      border: `2px solid ${lit > 0.01 ? hue : 'rgba(255,255,255,0.15)'}`, boxShadow: `0 0 ${60 * lit}px ${hue}88, inset 0 0 ${40 * lit}px ${hue}33`,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6}}>
      <div style={{fontFamily: MONO, fontSize: 52, fontWeight: 700, color: '#fff', opacity: 0.5 + 0.5 * lit}}>{title}</div>
      <div style={{fontSize: 28, color: lit > 0.5 ? '#DDF3FF' : C.dim}}>{sub}</div>
    </div>
  </div>
);

const Box: React.FC<{label: string; ext: string; p: number; c: string}> = ({label, ext, p, c}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
    <svg width="110" height="110" viewBox="0 0 110 110">
      <path d="M55 8 L100 30 L100 80 L55 102 L10 80 L10 30 Z" fill={`${c}22`} stroke={c} strokeWidth="3" strokeLinejoin="round" />
      <path d="M10 30 L55 52 L100 30 M55 52 L55 102" stroke={c} strokeWidth="3" fill="none" strokeLinejoin="round" />
      <path d="M32 19 L78 41" stroke={c} strokeWidth="3" opacity="0.6" />
    </svg>
    <div>
      <div style={{fontFamily: MONO, fontSize: 40, fontWeight: 700, color: '#fff'}}>{ext}</div>
      <div style={{fontSize: 28, color: C.dim}}>{label}</div>
    </div>
    <Check p={p} />
  </div>
);

export const Offline: React.FC<{t: number}> = ({t}) => {
  const s = scene('offline');
  const lt = t - s.start;
  const p15 = sStart('p15') - s.start;
  const p16 = sStart('p16') - s.start;
  const wifi = spr(lt, 0.1, {stiffness: 160, damping: 15});
  const slash = prog(lt, p15 + 0.9, p15 + 1.3, EXPO);
  const tag = prog(lt, p15 + 1.1, p15 + 1.6, EXPO);
  const c1 = prog(lt, p15 + 2.4, p15 + 2.9, EXPO);
  const c2 = prog(lt, p15 + 3.3, p15 + 3.8, EXPO);
  const chipsIn = prog(lt, p15 + 1.8, p15 + 2.4, EXPO);
  const up = prog(lt, p16 - 0.5, p16 + 0.1, EXPO);
  const b1 = spr(lt, p16 + 0.1, {stiffness: 170, damping: 15});
  const b2 = spr(lt, p16 + 0.9, {stiffness: 170, damping: 15});
  const k1 = prog(lt, p16 + 0.6, p16 + 1.0, EXPO), k2 = prog(lt, p16 + 1.6, p16 + 2.0, EXPO);
  const topY = -120 * up;
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <AbsoluteFill style={{transform: `translateY(${topY}px)`}}>
        {/* wifi + offline */}
        <div style={{position: 'absolute', left: 960 - 330, top: 120, display: 'flex', alignItems: 'center', gap: 40, opacity: Math.min(1, wifi), transform: `scale(${0.8 + 0.2 * wifi})`}}>
          <svg width="170" height="150" viewBox="0 0 170 150">
            {[0, 1, 2].map((i) => <path key={i} d={`M${85 - (30 + i * 28)} ${100 - (16 + i * 16)} a ${42 + i * 40} ${42 + i * 40} 0 0 1 ${2 * (30 + i * 28)} 0`} stroke={slash > 0.5 ? 'rgba(255,255,255,0.35)' : '#9FD8FF'} strokeWidth="11" fill="none" strokeLinecap="round" />)}
            <circle cx="85" cy="112" r="10" fill={slash > 0.5 ? 'rgba(255,255,255,0.35)' : '#9FD8FF'} />
            <line x1="22" y1="16" x2={22 + 126 * slash} y2={16 + 118 * slash} stroke="#F87171" strokeWidth="12" strokeLinecap="round" style={{filter: 'drop-shadow(0 0 10px #F87171)'}} />
          </svg>
          <div style={{opacity: tag, transform: `translateX(${(1 - tag) * 30}px)`}}>
            <div style={{fontSize: 92, fontWeight: 900, ...gradText()}}>完全离线</div>
            <div style={{fontSize: 30, color: C.dim, marginTop: 2}}>自带运行库 · 无需联网 · 零依赖安装</div>
          </div>
        </div>
        {/* chips */}
        <div style={{position: 'absolute', left: 0, right: 0, top: 410, display: 'flex', justifyContent: 'center', gap: 120, opacity: chipsIn, transform: `translateY(${(1 - chipsIn) * 40}px)`}}>
          <Chip title="x86_64" sub="Intel · 兆芯 · 海光" lit={c1} hue="#4FA8FF" />
          <Chip title="arm64" sub="飞腾 · 鲲鹏" lit={c2} hue="#4FE3FF" />
        </div>
      </AbsoluteFill>
      {/* packages */}
      {up > 0 && (
        <Glass style={{left: 960 - 620, top: 640, width: 1240, height: 220, opacity: up, transform: `translateY(${(1 - up) * 60}px)`}}>
          <div style={{display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'space-around'}}>
            <div style={{opacity: Math.min(1, b1), transform: `scale(${0.8 + 0.2 * b1})`}}><Box ext=".deb" label="安装包 · 双击安装" p={k1} c="#60A5FA" /></div>
            <div style={{width: 1, height: 120, background: 'rgba(255,255,255,0.15)'}} />
            <div style={{opacity: Math.min(1, b2), transform: `scale(${0.8 + 0.2 * b2})`}}><Box ext=".tar.gz" label="绿色版 · 解压即用" p={k2} c="#34D399" /></div>
          </div>
        </Glass>
      )}
      {void BACK}
    </AbsoluteFill>
  );
};
