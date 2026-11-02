import {Easing, interpolate} from 'remotion';
import timeline from './gen/timeline.json';

export const FPS = 30;
export const TL = timeline;
export const TOTAL_FRAMES = Math.ceil(timeline.total * FPS);
export const C = {
  bg0: '#060B1E', bg1: '#0B1530', indigo: '#2A2470', blue: '#1E4FD8', cyan: '#13A3C2',
  cyanHi: '#4FE3FF', text: '#EAF1FF', dim: 'rgba(214,226,255,0.62)', green: '#34D399', amber: '#FBBF24', red: '#F87171',
};
export const FONT = '"Noto Sans CJK SC", "Smiley Sans", sans-serif';
export const SMILEY = '"Smiley Sans", "Noto Sans CJK SC", sans-serif';
export const MONO = '"DejaVu Sans Mono", "Noto Sans Mono CJK SC", monospace';
export const EXPO = Easing.bezier(0.16, 1, 0.3, 1);
export const INOUT = Easing.bezier(0.65, 0, 0.35, 1);
export const BACK = Easing.bezier(0.34, 1.56, 0.64, 1);

export const sStart = (id: string) => TL.sentences.find((s) => s.id === id)!.start;
export const sEnd = (id: string) => {const s = TL.sentences.find((x) => x.id === id)!; return s.start + s.dur;};
export const scene = (id: string) => TL.scenes.find((s) => s.id === id)!;

/** clamp-interpolate t in [a,b] to [0,1] with easing */
export const prog = (t: number, a: number, b: number, ease: (x: number) => number = EXPO) =>
  interpolate(t, [a, b], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
export const clamp = (x: number, a = 0, b = 1) => Math.max(a, Math.min(b, x));
/** simple critically-damped-ish spring evaluated in seconds */
export const spr = (t: number, start: number, opts: {damping?: number; stiffness?: number; mass?: number} = {}) => {
  const dt = t - start; if (dt <= 0) return 0;
  const k = opts.stiffness ?? 170, c = opts.damping ?? 18, m = opts.mass ?? 1;
  const w0 = Math.sqrt(k / m), z = c / (2 * Math.sqrt(k * m));
  if (z < 1) {const wd = w0 * Math.sqrt(1 - z * z); return 1 - Math.exp(-z * w0 * dt) * (Math.cos(wd * dt) + (z * w0 / wd) * Math.sin(wd * dt));}
  return 1 - Math.exp(-w0 * dt) * (1 + w0 * dt);
};
export const fmtInt = (n: number) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
