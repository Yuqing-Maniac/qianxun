import React from 'react';
import {Audio, Sequence, staticFile, interpolate} from 'remotion';
import assets from './gen/assets.json';
import {TL, scene, sStart} from './theme';
import {getClip, clickTimes} from './rec';
import {queriesOf} from './scenes/Syntax';
import {r2Badges, r2Offset} from './scenes/How';

const A: any = assets;
const has = (n: string) => (A.sfx || []).includes(n);

/** music gain envelope (linear amplitude) – ducks under narration */
const musicVol = (f: number) => {
  const t = f / 30;
  let duck = 0;
  for (const s of TL.sentences) {
    const a = s.start - 0.25, b = s.start + s.dur + 0.2;
    const d = t < a - 0.35 || t > b + 0.6 ? 0 : t < a ? (t - (a - 0.35)) / 0.35 : t <= b ? 1 : 1 - (t - b) / 0.6;
    duck = Math.max(duck, Math.max(0, Math.min(1, d)));
  }
  const full = 0.85, low = 0.28;
  const fadeIn = interpolate(t, [0, 0.4], [0, 1], {extrapolateRight: 'clamp'});
  return (full + (low - full) * duck) * fadeIn;
};

type S = {t: number; f: string; v: number};

export const sfxList = (): S[] => {
  const L: S[] = [];
  const add = (t: number, f: string, v: number) => {if (has(f) && t >= 0 && t < TL.total - 0.2) L.push({t, f, v});};
  // hook: double-click folders
  [1.35, 2.25, 3.05, 3.8, 4.45].forEach((o) => {add(o - 0.28, 'click.wav', 0.35); add(o - 0.14, 'click.wav', 0.3);});
  // hook part 2 typing (Windows side + Kylin side)
  const p2 = sStart('p02') - 0.25 + 0.7;
  for (let i = 0; i < 4; i++) add(p2 + i * 0.12, 'key.wav', 0.25);
  add(p2 + 0.6, 'pop.wav', 0.3);
  const k = sStart('p02') + 2.2;
  for (let i = 0; i < 4; i++) add(k + i * 0.12, 'key.wav', 0.25);
  // search: typing (from events) + data cards
  const sS = scene('search').start;
  const r1 = getClip('R1');
  clickTimes(r1).forEach((c) => add(sS + c.t, 'click.wav', 0.3));
  r1.events.filter((e) => e.type === 'type' || e.type === 'query').forEach((e) => {const q = String(e.label ?? ''); for (let i = 0; i < Math.min(q.length, 6); i++) add(sS + e.t + i * 0.1, 'key.wav', 0.22);});
  const p05 = sStart('p05');
  add(p05 + 0.1, 'whoosh.wav', 0.22); add(p05 + 0.7, 'pop.wav', 0.25);
  // how: query beam tick, live sync badges, relaunch success
  const hS = scene('how').start;
  add(sStart('p06') - 0.85 + 2.35, 'tick.wav', 0.35);
  r2Badges().forEach((b) => add(hS + r2Offset() + b.t, 'pop.wav', 0.32));
  {const fsE = getClip('R2').events.filter((e) => e.type === 'fs'); fsE.forEach((e, j) => {const n = String(e.label ?? '').length; const avail = j === 0 ? 1.2 : e.t - fsE[j - 1].t - 0.25; const ch = Math.min(0.05, avail / n); for (let i = 0; i < n; i += 3) add(hS + r2Offset() + e.t - (n - i) * ch, 'key.wav', 0.12);});}
  add(sStart('p08') - 0.3 + 1.55 + 0.8, 'success.wav', 0.3);
  // syntax capsules
  const yS = scene('syntax').start;
  queriesOf(getClip('R3')).forEach((q) => add(yS + q.t + 0.15, 'pop.wav', 0.22));
  // filter / ops clicks
  const fS = scene('filter').start;
  clickTimes(getClip('R4')).forEach((c) => add(fS + c.t, 'click.wav', 0.3));
  const oS = scene('ops').start;
  clickTimes(getClip('R5')).forEach((c) => add(oS + c.t, 'click.wav', 0.3));
  const p14 = sStart('p14') - 0.35;
  add(p14 + 0.1, 'whoosh.wav', 0.25); add(p14 + 1.08, 'click.wav', 0.45); add(p14 + 1.4, 'whoosh.wav', 0.25);
  // offline checks
  const p15 = sStart('p15'), p16 = sStart('p16');
  add(p15 + 0.9, 'tick.wav', 0.3); add(p15 + 2.4, 'pop.wav', 0.25); add(p15 + 3.3, 'pop.wav', 0.25);
  add(p16 + 0.6, 'success.wav', 0.22); add(p16 + 1.6, 'success.wav', 0.22);
  // dedupe near-identical
  L.sort((a, b) => a.t - b.t);
  return L.filter((s, i) => !L.slice(0, i).some((o) => o.f === s.f && Math.abs(o.t - s.t) < 0.06));
};

export const AudioLayer: React.FC = () => {
  return (
    <>
      {A.music && <Audio src={staticFile(A.music)} volume={musicVol} />}
      {TL.sentences.map((s) => (
        <Sequence key={s.id} from={Math.round(s.start * 30)} durationInFrames={Math.ceil((s.dur + 0.3) * 30)} layout="none">
          <Audio src={staticFile(`audio/${s.id}.wav`)} volume={1} />
        </Sequence>
      ))}
      {sfxList().map((s, i) => (
        <Sequence key={i} from={Math.round(s.t * 30)} durationInFrames={150} layout="none">
          <Audio src={staticFile(`sfx/${s.f}`)} volume={s.v} />
        </Sequence>
      ))}
    </>
  );
};
