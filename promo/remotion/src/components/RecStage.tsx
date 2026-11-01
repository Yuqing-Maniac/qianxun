import React from 'react';
import {AbsoluteFill, Freeze, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {Clip, Rect, cursorAt, clickTimes, rectOf} from '../rec';
import {INOUT, lerp, clamp, FONT} from '../theme';
import {Arrow, Ripple} from './Cursor';
import {MockApp} from './MockApp';
import {AppIcon} from './AppIcon';

export type Box = {x: number; y: number; w: number; h: number};
export type Cam = {t: number; rect?: Rect | string; z?: number; dur?: number; ox?: number; oy?: number; zmax?: number; pad?: number};
export const TB = 46; // title bar height (display px at base scale)

export const baseScale = (clip: Clip, box: Box, margin = 40) => Math.min((box.w - 2 * margin) / clip.width, (box.h - 2 * margin - TB) / clip.height);

/** camera state at time t: focus point in window-local base coords + zoom */
export const camAt = (clip: Clip, box: Box, cams: Cam[], t: number, k: number) => {
  const winW = clip.width * k, winH = clip.height * k + TB;
  const stateOf = (c: Cam) => {
    let fx = winW / 2, fy = winH / 2, z = c.z ?? 1;
    if (c.rect) {
      const r = typeof c.rect === 'string' ? rectOf(clip, c.rect) : c.rect;
      const pad = c.pad ?? 1.15;
      fx = (r[0] + r[2] / 2) * k; fy = TB + (r[1] + r[3] / 2) * k;
      if (c.z === undefined) z = Math.min(box.w * 0.92 / (r[2] * k * pad), (box.h - 170) / (r[3] * k * pad), c.zmax ?? 2.4);
    }
    return {fx: fx + (c.ox ?? 0), fy: fy + (c.oy ?? 0), z};
  };
  let s = stateOf(cams[0] || {t: 0});
  for (let i = 1; i < cams.length; i++) {
    const c = cams[i];
    if (t < c.t) break;
    const p = INOUT(clamp((t - c.t) / (c.dur ?? 0.9)));
    const n = stateOf(c);
    // zoom in log space for perceptual smoothness
    const z = Math.exp(lerp(Math.log(s.z), Math.log(n.z), p));
    s = {fx: lerp(s.fx, n.fx, p), fy: lerp(s.fy, n.fy, p), z};
  }
  return s;
};

export const WindowChrome: React.FC<{w: number; title?: string; dark?: boolean}> = ({w, title = '千寻 - 文件秒搜', dark}) => (
  <div style={{height: TB, width: w, display: 'flex', alignItems: 'center', background: dark ? '#20232B' : 'linear-gradient(#FFFFFF,#F4F6F9)',
    borderBottom: dark ? '1px solid #2D313B' : '1px solid #E4E7EC', fontFamily: FONT, color: dark ? '#E5E7EB' : '#1F2329', position: 'relative'}}>
    <div style={{marginLeft: 16, display: 'flex', alignItems: 'center', gap: 10}}>
      <AppIcon size={22} id={'tb' + (dark ? 'd' : 'l')} />
      <span style={{fontSize: 16, fontWeight: 500}}>{title}</span>
    </div>
    <div style={{position: 'absolute', right: 6, top: 0, height: TB, display: 'flex', alignItems: 'center', gap: 4}}>
      {[0, 1, 2].map((i) => (
        <div key={i} style={{width: 40, height: 32, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <svg width="14" height="14" viewBox="0 0 14 14" stroke={dark ? '#C8CCD4' : '#3A3F47'} strokeWidth="1.4" fill="none" strokeLinecap="round">
            {i === 0 && <line x1="2" y1="7" x2="12" y2="7" />}
            {i === 1 && <rect x="2.5" y="2.5" width="9" height="9" rx="1.5" />}
            {i === 2 && <><line x1="2.5" y1="2.5" x2="11.5" y2="11.5" /><line x1="11.5" y1="2.5" x2="2.5" y2="11.5" /></>}
          </svg>
        </div>
      ))}
    </div>
  </div>
);

/** The recording (or placeholder) at recording resolution, time-locked to clip time t */
export const RecVideo: React.FC<{clip: Clip; t: number}> = ({clip, t}) => {
  if (!clip.file) return <MockApp clip={clip} t={t} />;
  const durF = Math.floor(clip.duration * 30) - 2;
  const f = Math.min(durF, Math.max(0, Math.round(t * 30)));
  const st: React.CSSProperties = {width: clip.width, height: clip.height, position: 'absolute', left: 0, top: 0};
  // Freeze pins the decoded frame to clip time t, independent of where the scene sits on the master timeline
  return <Freeze frame={f}><OffthreadVideo src={staticFile(clip.file)} muted style={st} /></Freeze>;
};

type Props = {
  clip: Clip; t: number; cams: Cam[]; box?: Box; margin?: number;
  overlays?: (k: number) => React.ReactNode; // drawn inside camera, coords = window-local base px (use rx/ry helpers)
  screen?: (cam: {fx: number; fy: number; z: number}, toScreen: (x: number, y: number) => [number, number]) => React.ReactNode;
  enter?: number; // 0..1
  k?: number;
  hideCursor?: boolean; clipBox?: boolean; radius?: number; offsetY?: number;
};

export const RecStage: React.FC<Props> = ({clip, t, cams, box = {x: 0, y: 0, w: 1920, h: 1080}, margin = 40, overlays, screen, enter = 1, hideCursor, clipBox, radius = 14, offsetY = -60, k: kIn}) => {
  const k = kIn ?? Math.min(baseScale(clip, box, margin), 0.58);
  const winW = clip.width * k, winH = clip.height * k + TB;
  const cam = camAt(clip, box, cams, t, k);
  const cx = box.w / 2, cy = box.h / 2 + offsetY;
  const tx = cx - cam.fx * cam.z, ty = cy - cam.fy * cam.z;
  const toScreen = (x: number, y: number): [number, number] => [box.x + tx + x * cam.z, box.y + ty + y * cam.z];
  const cur = cursorAt(clip, t);
  const clicks = clickTimes(clip);
  const csize = 30 / Math.sqrt(cam.z);
  let pressed = 0;
  if (cur?.down) pressed = 1;
  return (
    <AbsoluteFill style={{left: box.x, top: box.y, width: box.w, height: box.h, overflow: clipBox ? 'hidden' : 'visible', borderRadius: clipBox ? radius : 0}}>
      <div style={{position: 'absolute', left: 0, top: 0, transformOrigin: '0 0', transform: `translate(${tx}px, ${ty}px) scale(${cam.z})`}}>
        <div style={{position: 'absolute', left: 0, top: 0, width: winW, height: winH, borderRadius: 12, overflow: 'hidden',
          boxShadow: `0 ${40 / cam.z}px ${120 / cam.z}px rgba(0,0,10,0.55), 0 0 0 1px rgba(255,255,255,0.08)`, background: '#fff', opacity: enter}}>
          <WindowChrome w={winW} />
          <div style={{position: 'absolute', left: 0, top: TB, width: clip.width, height: clip.height, transformOrigin: '0 0', transform: `scale(${k})`}}>
            <RecVideo clip={clip} t={t} />
          </div>
        </div>
        {overlays && overlays(k)}
        {!hideCursor && cur && (
          <div style={{position: 'absolute', left: cur.x * k, top: TB + cur.y * k}}>
            {clicks.map((c, i) => <div key={i} style={{position: 'absolute', left: (c.x - cur.x) * k, top: (c.y - cur.y) * k}}><Ripple age={t - c.t} scale={0.7 / Math.sqrt(cam.z)} /></div>)}
            <Arrow size={csize} pressed={pressed} />
          </div>
        )}
      </div>
      {screen && screen(cam, toScreen)}
    </AbsoluteFill>
  );
};

/** helper: recording px -> window-local base coords */
export const rx = (x: number, k: number) => x * k;
export const ry = (y: number, k: number) => TB + y * k;
export const _unused = {Sequence, useCurrentFrame};
