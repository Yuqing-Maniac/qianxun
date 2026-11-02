import React from 'react';
import {AbsoluteFill} from 'remotion';
import {getClip, rectOf, Clip} from '../rec';
import {RecStage, Cam} from '../components/RecStage';
import {FONT, MONO, prog, EXPO, scene, sStart, spr, C} from '../theme';

/** map a query string to a syntax explanation */
export const explain = (q: string): {k: string; v: string; c: string}[] => {
  const out: {k: string; v: string; c: string}[] = [];
  if (/\|/.test(q)) out.push({k: '|', v: '或', c: '#FBBF24'});
  if (/(^|\s)!/.test(q)) out.push({k: '!', v: '排除', c: '#F87171'});
  if (/\*|\?/.test(q)) out.push({k: '*', v: '通配符', c: '#A78BFA'});
  if (/ext:/i.test(q)) out.push({k: 'ext:', v: '扩展名', c: '#60A5FA'});
  if (/size:/i.test(q)) out.push({k: 'size:', v: '大小', c: '#34D399'});
  if (/dm:/i.test(q)) out.push({k: 'dm:', v: '修改日期', c: '#F472B6'});
  if (!out.length && /\S\s+\S/.test(q)) out.push({k: '空格', v: '与', c: '#4FE3FF'});
  if (!out.length) out.push({k: 'Aa', v: '关键词', c: '#4FE3FF'});
  return out;
};

/** one entry per finished query; t = moment the full text was typed (falls back to query event time) */
export const queriesOf = (clip: Clip) => {
  const qe = clip.events.filter((e) => e.type === 'query');
  const src = qe.length ? qe : clip.events.filter((e) => e.type === 'type');
  return src.map((e) => {
    const q = String(e.label ?? e.value ?? '');
    const typed = clip.events.filter((x) => x.type === 'type' && x.t <= e.t + 0.01 && (x.value?.text ?? x.label) === q);
    const t = typed.length ? typed[typed.length - 1].t : e.t;
    return {t: t + 0.05, q, res: e.t, ms: e.value?.search_ms as number | undefined, rows: e.value?.rows as number | undefined};
  });
};

export const Syntax: React.FC<{t: number}> = ({t}) => {
  const s = scene('syntax');
  const clip = getClip('R3');
  const ct = t - s.start;
  const qs = queriesOf(clip);
  const NEAR: [number, number, number, number] = [0, 20, 1500, 640];
  const FAR: [number, number, number, number] = [0, 30, 2000, 820];
  const cams: Cam[] = [{t: 0, z: 0.9, oy: -70}, {t: 0.9, rect: NEAR, zmax: 1.9, dur: 1.2}];
  // push in on the search box while typing, ease back to show results after each query lands
  qs.forEach((q, i) => {
    const typeStart = clip.events.filter((e) => e.type === 'key' && e.t < q.t).slice(-1)[0]?.t ?? q.t - 0.5;
    cams.push({t: typeStart - 0.2, rect: NEAR, zmax: 1.9, dur: 0.45});
    const nxt = qs[i + 1]?.t ?? clip.duration;
    if (nxt - q.t > 1.2) cams.push({t: q.t + 0.35, rect: FAR, zmax: 1.45, dur: Math.min(0.9, nxt - q.t - 0.7)});
  });
  cams.sort((a, b) => a.t - b.t);
  // active query
  let cur = -1;
  qs.forEach((q, i) => {if (ct >= q.t - 0.05) cur = i;});
  const sR = rectOf(clip, 'search');
  const ICON_TOP = 60;
  const allK = [['空格', '与', '#4FE3FF'], ['|', '或', '#FBBF24'], ['!', '排除', '#F87171'], ['*', '通配符', '#A78BFA'], ['ext:', '扩展名', '#60A5FA'], ['size:', '大小', '#34D399'], ['dm:', '修改日期', '#F472B6']];
  const seen = new Set<string>();
  qs.forEach((q, i) => {if (i <= cur) explain(q.q).forEach((x) => seen.add(x.k));});
  const p09 = sStart('p09') - s.start;
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <RecStage clip={clip} t={ct} cams={cams}
        screen={(cam, toScreen) => {
          if (cur < 0) return null;
          const q = qs[cur];
          const ex = explain(q.q);
          const [, sy] = toScreen(0, 46 + (sR[1] + sR[3]) * 0.58);
          const a = spr(ct, q.t + 0.15, {stiffness: 230, damping: 18});
          return (
            <div style={{position: 'absolute', right: 70, top: Math.max(150, sy + 40), display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 16}}>
              <div style={{fontFamily: MONO, fontSize: 30, color: '#fff', padding: '10px 22px', borderRadius: 14, background: 'rgba(8,14,40,0.88)', border: '1px solid rgba(255,255,255,0.2)',
                opacity: Math.min(1, a), transform: `translateX(${(1 - a) * 40}px)`, boxShadow: '0 14px 40px rgba(0,0,0,0.4)', whiteSpace: 'nowrap'}}>
                {q.q}<span style={{fontFamily: FONT, fontSize: 22, color: 'rgba(200,220,255,0.7)', marginLeft: 16}}>{q.rows !== undefined ? q.rows.toLocaleString('en-US') + ' 个结果' : ''}</span>
              </div>
              {ex.map((x, j) => {
                const aj = spr(ct, q.t + 0.15 + j * 0.08, {stiffness: 230, damping: 18});
                return (
                  <div key={cur + '-' + j} style={{display: 'flex', alignItems: 'center', gap: 16, padding: '12px 30px 12px 14px', borderRadius: 999,
                    background: 'rgba(10,18,50,0.82)', border: `2px solid ${x.c}`, boxShadow: `0 0 34px ${x.c}55, 0 16px 40px rgba(0,0,0,0.4)`,
                    opacity: Math.min(1, aj), transform: `translateX(${(1 - aj) * 50}px) scale(${0.7 + 0.3 * aj})`, backdropFilter: 'blur(10px)'}}>
                    <span style={{fontFamily: MONO, fontSize: 34, fontWeight: 700, color: '#0B1530', background: x.c, borderRadius: 999, padding: '2px 16px', minWidth: 30, textAlign: 'center'}}>{x.k}</span>
                    <span style={{fontSize: 38, fontWeight: 800, color: '#fff'}}>{x.v}</span>
                  </div>
                );
              })}
              {void a}{void cam}
            </div>
          );
        }} />
      {/* top legend */}
      <div style={{position: 'absolute', left: '50%', top: 14, transform: 'translateX(-50%)', display: 'flex', justifyContent: 'center', gap: 12, padding: '10px 14px', borderRadius: 999, background: 'rgba(8,14,40,0.86)', border: '1px solid rgba(255,255,255,0.14)', boxShadow: '0 16px 50px rgba(0,0,0,0.45)', backdropFilter: 'blur(14px)', whiteSpace: 'nowrap', opacity: prog(ct, p09 + 0.2, p09 + 0.8)}}>
        <div style={{padding: '8px 18px', fontSize: 24, color: C.dim, display: 'flex', alignItems: 'center'}}>与 Everything 一致</div>
        {allK.map(([k, v, c]) => {
          const on = seen.has(k);
          return <div key={k} style={{padding: '8px 18px', borderRadius: 999, fontSize: 24, display: 'flex', gap: 8, alignItems: 'center',
            border: `1.5px solid ${on ? c : 'rgba(255,255,255,0.18)'}`, background: on ? `${c}22` : 'rgba(255,255,255,0.04)', color: on ? '#fff' : 'rgba(255,255,255,0.45)', boxShadow: on ? `0 0 18px ${c}44` : undefined}}>
            <span style={{fontFamily: MONO, color: on ? c : undefined}}>{k}</span>{v}</div>;
        })}
      </div>
    </AbsoluteFill>
  );
};
