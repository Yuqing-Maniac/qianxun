import assets from './gen/assets.json';
import {sStart, scene} from './theme';

export type Rect = [number, number, number, number];
export type CursorPt = {t: number; x: number; y: number; down?: boolean};
export type Ev = {t: number; type: string; label?: string; value?: any; [k: string]: any};
export type Clip = {
  fps: number; width: number; height: number; scale: number; duration: number;
  cursor: CursorPt[]; events: Ev[]; rects: Record<string, Rect>;
  stats?: {indexed?: number; search_ms?: {t: number; q: string; ms: number}[]};
  file?: string; placeholder?: boolean;
};

const DEF_RECTS: Record<string, Rect> = {
  search: [14, 54, 2150, 52], filter: [2180, 54, 206, 52], results: [9, 116, 2382, 1272],
  statusbar: [0, 1395, 2400, 45], header_size: [1188, 116, 136, 42], menu: [900, 500, 520, 560],
};

const rel = (abs: number, sc: string) => abs - scene(sc).start;

/** Fallback clip descriptions (used until the real recording JSON appears) */
const fallback = (k: string): Clip => {
  const base = {fps: 30, width: 2400, height: 1440, scale: 1.5, rects: DEF_RECTS, placeholder: true};
  if (k === 'R1') {
    const t0 = rel(sStart('p04'), 'search') + 0.3;
    return {...base, duration: 9, cursor: [{t: 0, x: 1300, y: 700}, {t: t0 - 0.4, x: 600, y: 80}, {t: t0 - 0.2, x: 600, y: 80, down: true}, {t: t0, x: 600, y: 80}],
      events: [{t: t0, type: 'type', label: '总体方案'}], stats: {indexed: 1046382, search_ms: [{t: t0 + 1, q: '总体方案', ms: 23}]}};
  }
  if (k === 'R2') {
    const p = rel(sStart('p07'), 'how');
    return {...base, duration: 13, cursor: [{t: 0, x: 1800, y: 900}], events: [
      {t: p + 0.9, type: 'fs', label: 'touch ~/文档/会议纪要-1017.docx'}, {t: p + 1.2, type: 'result', label: '新建'},
      {t: p + 2.2, type: 'fs', label: 'mv 会议纪要-1017.docx 会议纪要-定稿.docx'}, {t: p + 2.5, type: 'result', label: '改名'},
      {t: p + 3.5, type: 'fs', label: 'rm 会议纪要-定稿.docx'}, {t: p + 3.8, type: 'result', label: '删除'},
    ]};
  }
  if (k === 'R3') {
    const s = (id: string) => rel(sStart(id), 'syntax');
    return {...base, duration: 14, cursor: [{t: 0, x: 1500, y: 800}], events: [
      {t: s('p09') + 0.4, type: 'query', label: '总体 方案'}, {t: s('p10') + 0.3, type: 'query', label: '方案 | 报告'},
      {t: s('p10') + 1.6, type: 'query', label: '方案 !草稿'}, {t: s('p11') + 0.2, type: 'query', label: '*.pdf'},
      {t: s('p11') + 1.4, type: 'query', label: 'ext:docx;wps'}, {t: s('p11') + 2.6, type: 'query', label: 'size:>100mb'},
      {t: s('p11') + 3.7, type: 'query', label: 'dm:today'}]};
  }
  if (k === 'R4') return {...base, duration: 6, cursor: [{t: 0, x: 1500, y: 700}, {t: 0.9, x: 2280, y: 80}, {t: 1.0, x: 2280, y: 80, down: true}, {t: 1.1, x: 2280, y: 80}, {t: 1.9, x: 2280, y: 240}, {t: 2.0, x: 2280, y: 240, down: true}, {t: 2.1, x: 2280, y: 240}, {t: 3.3, x: 1250, y: 137}, {t: 3.4, x: 1250, y: 137, down: true}, {t: 3.5, x: 1250, y: 137}], events: []};
  return {...base, duration: 10, cursor: [{t: 0, x: 1200, y: 600}, {t: 0.6, x: 700, y: 300}, {t: 0.7, x: 700, y: 300, down: true}, {t: 0.8, x: 700, y: 300}], events: []};
};

export const getClip = (k: string): Clip => {
  const real = (assets as any).rec?.[k];
  if (real) return {...real, rects: {...DEF_RECTS, ...(real.rects || {})}, file: (assets as any).recFiles[k]};
  return fallback(k);
};

export const cursorAt = (c: Clip, t: number) => {
  const pts = c.cursor;
  if (!pts || !pts.length) return null;
  if (t <= pts[0].t) return {...pts[0], down: !!pts[0].down};
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    if (t >= a.t && t <= b.t) {
      const u = b.t > a.t ? (t - a.t) / (b.t - a.t) : 1;
      const e = u * u * (3 - 2 * u);
      // short gaps are already dense samples -> linear; long gaps -> smoothstep glide
      const k = b.t - a.t > 0.12 ? e : u;
      return {t, x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k, down: !!a.down};
    }
  }
  const l = pts[pts.length - 1];
  return {...l, down: !!l.down};
};

/** times where button goes down */
export const clickTimes = (c: Clip) => {
  const out: {t: number; x: number; y: number; right?: boolean}[] = [];
  let prev = false;
  for (const p of c.cursor || []) {if (p.down && !prev) out.push({t: p.t, x: p.x, y: p.y}); prev = !!p.down;}
  for (const e of c.events || []) {
    const x = e.x ?? e.value?.x, y = e.y ?? e.value?.y;
    if ((e.type === 'click' || e.type === 'rightclick') && x !== undefined && !out.some((o) => Math.abs(o.t - e.t) < 0.15)) out.push({t: e.t, x, y, right: e.type === 'rightclick'});
  }
  return out;
};
export const rectOf = (c: Clip, name: string): Rect => c.rects[name] || DEF_RECTS[name] || [0, 0, c.width, c.height];
