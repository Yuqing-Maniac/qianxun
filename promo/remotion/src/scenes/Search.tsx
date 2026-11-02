import React from 'react';
import {AbsoluteFill} from 'remotion';
import {getClip, rectOf} from '../rec';
import {RecStage, Cam, rx, ry} from '../components/RecStage';
import {FONT, MONO, prog, EXPO, BACK, scene, sStart, fmtInt, spr, C} from '../theme';
import {Glass, gradText} from '../components/Glass';

export const Search: React.FC<{t: number}> = ({t}) => {
  const s = scene('search');
  const clip = getClip('R1');
  const ct = t - s.start;
  const typeEv = clip.events.find((e) => e.type === 'type' || e.type === 'query');
  const tType = typeEv ? typeEv.t : sStart('p04') - s.start + 0.3;
  const p05 = sStart('p05') - s.start;
  const cams: Cam[] = [
    {t: 0, z: 0.92, oy: 30},
    {t: 0.2, z: 1, dur: 1.2},
    {t: Math.max(0.5, tType - 1.0), rect: [0, 20, 1350, 600], zmax: 2.0, dur: 1.0},
    {t: tType + 1.3, rect: [0, 40, 2400, 860], zmax: 1.35, dur: 1.2},
    {t: p05 - 0.2, z: 0.86, dur: 1.0, ox: 150, oy: 10},
  ];
  const indexed = clip.stats?.indexed ?? 1046382;
  const st: any = clip.stats ?? {};
  // full (non-incremental) query time is the honest per-search figure
  const warm = st.warm_ms ? (Object.values(st.warm_ms)[0] as number) : undefined;
  const msList = st.search_ms ?? [];
  const full = msList.length ? msList[msList.length - 1].ms_full : undefined;
  const lastMs = Math.round(full ?? warm ?? 42);
  const card = spr(ct, p05 + 0.1, {stiffness: 160, damping: 17});
  const count = prog(ct, p05 + 0.2, p05 + 1.6, EXPO);
  const card2 = spr(ct, p05 + 0.7, {stiffness: 160, damping: 17});
  const enter = prog(ct, -0.4, 0.5, EXPO);
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <AbsoluteFill style={{transform: `perspective(2200px) rotateX(${(1 - enter) * 14}deg) translateY(${(1 - enter) * 120}px)`, opacity: enter}}>
        <RecStage clip={clip} t={ct} cams={cams}
          overlays={(k) => {
            const r = rectOf(clip, 'search');
            const g = prog(ct, tType - 0.3, tType + 0.2) * (1 - prog(ct, tType + 1.4, tType + 1.9));
            return <div style={{position: 'absolute', left: rx(r[0], k) - 6, top: ry(r[1], k) - 6, width: r[2] * k + 12, height: r[3] * k + 12, borderRadius: 10,
              boxShadow: `0 0 0 2px rgba(79,227,255,${0.9 * g}), 0 0 28px rgba(79,227,255,${0.55 * g})`}} />;
          }} />
      </AbsoluteFill>
      {/* data cards for p05 */}
      {card > 0.001 && (
        <>
          <Glass strong style={{left: 1250, top: 200, width: 610, height: 230, opacity: Math.min(1, card), transform: `translateX(${(1 - card) * 80}px) scale(${0.9 + 0.1 * card})`}}>
            <div style={{padding: '30px 38px'}}>
              <div style={{fontSize: 28, color: C.dim, display: 'flex', alignItems: 'center', gap: 12}}>
                <span style={{width: 10, height: 10, borderRadius: 5, background: C.cyanHi, boxShadow: `0 0 12px ${C.cyanHi}`}} />已索引
              </div>
              <div style={{display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 6}}>
                <span style={{fontFamily: MONO, fontSize: 84, fontWeight: 700, letterSpacing: -2, whiteSpace: 'nowrap', ...gradText('#FFFFFF', '#8FDCFF')}}>{fmtInt(indexed * count)}</span>
                <span style={{fontSize: 34, color: '#CFE4FF', whiteSpace: 'nowrap'}}>个文件</span>
              </div>
            </div>
          </Glass>
          <Glass strong style={{left: 1250, top: 460, width: 610, height: 230, opacity: Math.min(1, card2), transform: `translateX(${(1 - card2) * 80}px) scale(${0.9 + 0.1 * card2})`}}>
            <div style={{padding: '30px 38px'}}>
              <div style={{fontSize: 28, color: C.dim, display: 'flex', alignItems: 'center', gap: 12}}>
                <span style={{width: 10, height: 10, borderRadius: 5, background: C.green, boxShadow: `0 0 12px ${C.green}`}} />检索耗时
              </div>
              <div style={{display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 6}}>
                <span style={{fontFamily: MONO, fontSize: 92, fontWeight: 700, ...gradText('#FFFFFF', '#9BF2C8')}}>{Math.max(1, Math.round(lastMs * prog(ct, p05 + 0.8, p05 + 1.6, EXPO)))}</span>
                <span style={{fontSize: 34, color: '#CFE4FF'}}>毫秒</span>
              </div>
              {/* speed bar */}
              <div style={{position: 'absolute', left: 38, right: 38, bottom: 28, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.1)'}}>
                <div style={{width: `${100 * prog(ct, p05 + 0.8, p05 + 1.1, EXPO)}%`, height: '100%', borderRadius: 3, background: 'linear-gradient(90deg,#34D399,#4FE3FF)', boxShadow: '0 0 14px #34D399'}} />
              </div>
            </div>
          </Glass>
        </>
      )}
    </AbsoluteFill>
  );
};
export const _s = BACK;
