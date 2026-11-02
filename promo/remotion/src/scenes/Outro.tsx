import React from 'react';
import {AbsoluteFill, random} from 'remotion';
import {FONT, SMILEY, scene, sStart, prog, EXPO, INOUT, spr, TL} from '../theme';
import {AppIcon} from '../components/AppIcon';
import {gradText} from '../components/Glass';

export const Outro: React.FC<{t: number}> = ({t}) => {
  const s = scene('outro');
  const lt = t - s.start;
  const p17 = sStart('p17') - s.start;
  const ic = spr(lt, 0.15, {stiffness: 140, damping: 14});
  const name = prog(lt, 0.5, 1.2, EXPO);
  const quote = prog(lt, p17 + 1.0, p17 + 1.9, EXPO);
  const sub = prog(lt, p17 + 2.2, p17 + 2.9, EXPO);
  const fadeOut = prog(t, TL.total - 1.6, TL.total - 0.1, INOUT);
  const sweep = prog(lt, p17 + 1.2, p17 + 2.6, INOUT);
  const qtxt = '千寻之深，一寻即得';
  const stars = new Array(60).fill(0).map((_, i) => {
    const x = random('x' + i) * 1920, y0 = random('y' + i) * 1080;
    const y = (y0 - lt * (12 + random('v' + i) * 30) + 1080) % 1080;
    const sz = 1 + random('s' + i) * 2.5;
    return <div key={i} style={{position: 'absolute', left: x, top: y, width: sz, height: sz, borderRadius: sz, background: '#BFE6FF', opacity: (0.2 + 0.5 * random('o' + i)) * prog(lt, 0, 1.2)}} />;
  });
  return (
    <AbsoluteFill style={{fontFamily: FONT, opacity: 1 - fadeOut}}>
      {stars}
      <AbsoluteFill style={{background: `radial-gradient(35% 40% at 50% 38%, rgba(60,150,255,${0.3 * Math.min(1, ic)}), transparent 70%)`}} />
      <div style={{position: 'absolute', left: 960 - 110, top: 150, transform: `scale(${0.6 + 0.4 * ic}) translateY(${(1 - Math.min(1, ic)) * 40}px)`, opacity: Math.min(1, ic)}}>
        <AppIcon size={220} glow={0.8 + 0.2 * Math.sin(lt * 2)} id="out" />
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 400, textAlign: 'center', fontSize: 130, fontWeight: 900, letterSpacing: 24, opacity: name, transform: `translateY(${(1 - name) * 30}px)`, filter: `blur(${(1 - name) * 8}px)`, ...gradText('#FFFFFF', '#A9DBFF')}}>千寻</div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 590, display: 'flex', justifyContent: 'center', gap: 6}}>
        {qtxt.split('').map((ch, i) => {
          const p = prog(lt, p17 + 1.0 + i * 0.08, p17 + 1.6 + i * 0.08, EXPO);
          return <span key={i} style={{fontFamily: SMILEY, fontSize: 76, color: '#EAF6FF', opacity: p, transform: `translateY(${(1 - p) * 24}px)`, filter: `blur(${(1 - p) * 6}px)`, display: 'inline-block',
            textShadow: `0 0 ${30 * (1 - Math.abs(sweep * 12 - i))}px rgba(120,210,255,0.9)`}}>{ch}</span>;
        })}
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 720, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 22, opacity: sub, transform: `translateY(${(1 - sub) * 16}px)`}}>
        <div style={{height: 1.5, width: 120, background: 'linear-gradient(90deg, transparent, rgba(160,210,255,0.7))'}} />
        <div style={{fontSize: 34, letterSpacing: 8, color: '#BFD8FF', whiteSpace: 'nowrap'}}>银河麒麟 · 文件秒搜 · 离线可用</div>
        <div style={{height: 1.5, width: 120, background: 'linear-gradient(270deg, transparent, rgba(160,210,255,0.7))'}} />
      </div>
      {void quote}
    </AbsoluteFill>
  );
};
