import React from 'react';
import {AbsoluteFill, random} from 'remotion';
import {FONT, prog, EXPO, BACK, INOUT, spr, scene, clamp, C} from '../theme';
import {AppIcon} from '../components/AppIcon';
import {gradText} from '../components/Glass';

export const Title: React.FC<{t: number}> = ({t}) => {
  const s0 = scene('title').start; // 10.484 ; hit at 11.184
  const lt = t - s0;
  const dot = prog(lt, 0, 0.35, EXPO) * (1 - prog(lt, 0.55, 0.8));
  const bg = spr(lt, 0.55, {stiffness: 200, damping: 16});
  const ring = prog(lt, 0.65, 1.35, EXPO);
  const handle = prog(lt, 1.05, 1.45, EXPO);
  const lines = prog(lt, 1.25, 1.85, EXPO);
  const shift = prog(lt, 1.6, 2.4, INOUT);
  const iconSize = 300 - 60 * shift;
  const txt = prog(lt, 1.85, 2.6, EXPO);
  const sub = prog(lt, 2.3, 3.0, EXPO);
  const sweep = prog(lt, 2.5, 3.6, INOUT);
  const flash = prog(lt, 0.62, 0.7) * (1 - prog(lt, 0.7, 1.3));
  // particles burst at impact
  const parts = new Array(70).fill(0).map((_, i) => {
    const a = random('a' + i) * Math.PI * 2, sp = 200 + random('s' + i) * 700, life = 1.2 + random('l' + i) * 1.4;
    const age = lt - 0.62;
    if (age < 0 || age > life) return null;
    const e = 1 - Math.pow(1 - age / life, 3);
    const r = sp * e;
    const sz = 2 + random('z' + i) * 5;
    return <div key={i} style={{position: 'absolute', left: Math.cos(a) * r, top: Math.sin(a) * r * 0.8, width: sz, height: sz, borderRadius: sz,
      background: i % 3 ? '#9FE8FF' : '#FFFFFF', opacity: (1 - age / life) * 0.9, boxShadow: '0 0 10px #4FE3FF'}} />;
  });
  const groupX = -230 * shift;
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      {/* light rays */}
      <AbsoluteFill style={{background: `radial-gradient(40% 40% at 50% 46%, rgba(80,170,255,${0.35 * bg}) 0%, rgba(0,0,0,0) 70%)`}} />
      <AbsoluteFill style={{opacity: 0.25 * bg, background: `conic-gradient(from ${lt * 12}deg at 50% 46%, transparent 0deg, rgba(120,200,255,0.25) 10deg, transparent 22deg, transparent 60deg, rgba(120,200,255,0.18) 70deg, transparent 84deg, transparent 140deg, rgba(120,200,255,0.2) 150deg, transparent 165deg, transparent 220deg, rgba(120,200,255,0.18) 232deg, transparent 245deg, transparent 300deg, rgba(120,200,255,0.2) 310deg, transparent 325deg)`, WebkitMaskImage: 'radial-gradient(45% 45% at 50% 46%, black, transparent)'}} />
      <div style={{position: 'absolute', left: 960, top: 500}}>{parts}</div>
      {/* dot */}
      <div style={{position: 'absolute', left: 960 - 12, top: 500 - 12, width: 24, height: 24, borderRadius: 12, background: '#fff', boxShadow: '0 0 40px 16px #6CC8FF, 0 0 120px 40px rgba(60,140,255,0.6)', opacity: dot, transform: `scale(${0.3 + dot})`}} />
      {/* icon + wordmark group */}
      <div style={{position: 'absolute', left: 960 + groupX - iconSize / 2, top: 500 - iconSize / 2}}>
        <AppIcon size={iconSize} bg={bg} ring={ring} handle={handle} lines={lines} glow={bg * (0.6 + 0.4 * (1 - shift))} id="tt" />
      </div>
      <div style={{position: 'absolute', left: 960 + groupX + 150, top: 500 - 130, opacity: txt, transform: `translateX(${(1 - txt) * 40}px)`, filter: `blur(${(1 - txt) * 8}px)`}}>
        <div style={{position: 'relative', fontSize: 200, fontWeight: 900, letterSpacing: 18, lineHeight: '210px', whiteSpace: 'nowrap', ...gradText('#FFFFFF', '#A9DBFF')}}>
          千寻
          <div style={{position: 'absolute', inset: 0, background: `linear-gradient(105deg, transparent ${sweep * 140 - 30}%, rgba(255,255,255,0.95) ${sweep * 140 - 15}%, transparent ${sweep * 140}%)`,
            WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent', mixBlendMode: 'screen'}}>千寻</div>
        </div>
        <div style={{display: 'flex', alignItems: 'center', gap: 18, marginTop: 4, opacity: sub, transform: `translateY(${(1 - sub) * 16}px)`}}>
          <div style={{height: 2, width: 60 * sub, background: 'linear-gradient(90deg, transparent, #4FE3FF)'}} />
          <div style={{fontSize: 44, fontWeight: 500, color: '#CFE4FF', letterSpacing: 10, whiteSpace: 'nowrap'}}>银河麒麟 · 文件秒搜</div>
        </div>
        <div style={{fontSize: 24, letterSpacing: 14, color: 'rgba(160,200,255,0.6)', marginTop: 14, marginLeft: 82, opacity: sub, fontFamily: '"DejaVu Sans", sans-serif'}}>QIANXUN</div>
      </div>
      <AbsoluteFill style={{background: '#CFEAFF', opacity: flash * 0.35, mixBlendMode: 'screen'}} />
    </AbsoluteFill>
  );
};
export const _c = {clamp, BACK, C};
