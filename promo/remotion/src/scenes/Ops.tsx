import React from 'react';
import {AbsoluteFill} from 'remotion';
import {getClip} from '../rec';
import {RecStage, Cam, WindowChrome} from '../components/RecStage';
import {FONT, scene, sStart, prog, EXPO, INOUT, BACK, spr, lerp, C} from '../theme';
import {AppIcon} from '../components/AppIcon';

const Key: React.FC<{label: string; w: number; press: number}> = ({label, w, press}) => (
  <div style={{position: 'relative', width: w, height: 120}}>
    <div style={{position: 'absolute', left: 0, top: 14, width: w, height: 106, borderRadius: 20, background: '#0D1430'}} />
    <div style={{position: 'absolute', left: 0, top: 14 * press, width: w, height: 106, borderRadius: 20,
      background: `linear-gradient(180deg, ${press > 0.5 ? '#3A5BD9' : '#2B3768'}, ${press > 0.5 ? '#203AA0' : '#1B2550'})`,
      border: `1.5px solid ${press > 0.5 ? '#7FB8FF' : 'rgba(255,255,255,0.18)'}`, boxShadow: press > 0.5 ? '0 0 40px rgba(79,160,255,0.7)' : 'inset 0 2px 0 rgba(255,255,255,0.15)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 44, fontWeight: 700, fontFamily: '"DejaVu Sans", ' + FONT}}>{label}</div>
  </div>
);

const TrayAnim: React.FC<{lt: number}> = ({lt}) => {
  // phases: window minimizes into tray (0–0.8), key press (1.0–1.4), window pops back (1.4–2.2)
  const minP = prog(lt, 0.1, 0.8, INOUT);
  const keyIn = prog(lt, 0.6, 1.0, EXPO);
  const press = prog(lt, 1.05, 1.12) * (1 - prog(lt, 1.45, 1.55));
  const back = spr(lt, 1.35, {stiffness: 170, damping: 15});
  const W = 900, H = 540;
  const trayX = 1700, trayY = 1080 - 44 - 6 + 22; // tray icon center
  const scaleW = back > 0 ? lerp(0.04, 1, Math.min(back, 1.2)) : lerp(1, 0.04, minP);
  const cx = back > 0 ? lerp(trayX, 960, Math.min(1, back)) : lerp(960, trayX, minP);
  const cy = back > 0 ? lerp(trayY, 430, Math.min(1, back)) : lerp(430, trayY, minP);
  const op = back > 0 ? Math.min(1, back * 2) : 1 - prog(lt, 0.6, 0.8);
  const trayPulse = prog(lt, 0.75, 1.0) * (1 - prog(lt, 1.3, 1.6));
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <div style={{position: 'absolute', left: cx - W / 2, top: cy - H / 2, width: W, height: H, transform: `scale(${scaleW})`, opacity: op, borderRadius: 12, overflow: 'hidden',
        background: '#F6F7FA', boxShadow: '0 40px 100px rgba(0,0,10,0.55)'}}>
        <WindowChrome w={W} />
        <div style={{margin: 12, height: 44, borderRadius: 6, border: '2px solid #3B82F6', background: '#fff', display: 'flex', alignItems: 'center', padding: '0 14px', color: '#9AA1AB', fontSize: 18}}>输入文件名即搜</div>
        {new Array(9).fill(0).map((_, i) => <div key={i} style={{margin: '0 12px', height: 40, background: i % 2 ? '#F2F5F9' : '#fff', display: 'flex', alignItems: 'center', gap: 20, paddingLeft: 14}}>
          <div style={{width: 160 + (i * 37) % 120, height: 12, borderRadius: 6, background: '#D5DCE6'}} /><div style={{width: 260, height: 12, borderRadius: 6, background: '#E6EAF0'}} /></div>)}
      </div>
      {/* taskbar */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 56, background: 'rgba(12,18,40,0.82)', borderTop: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(20px)',
        display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 120, gap: 22, color: '#DCE6FF', fontSize: 20, opacity: 0}} />
      {/* Tray area (above subtitles: float panel) */}
      <div style={{position: 'absolute', left: trayX - 150, top: trayY - 50, width: 300, height: 76, borderRadius: 20, background: 'rgba(14,22,54,0.85)', border: '1px solid rgba(255,255,255,0.14)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-around', boxShadow: '0 20px 50px rgba(0,0,0,0.4)', opacity: 0}} />
      {/* keys */}
      <div style={{position: 'absolute', left: 0, right: 0, top: 700, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 30, opacity: keyIn * (1 - prog(lt, 2.4, 2.8)), transform: `translateY(${(1 - keyIn) * 40}px)`}}>
        <Key label="Alt" w={180} press={press} />
        <div style={{fontSize: 56, color: C.dim, fontWeight: 300}}>+</div>
        <Key label="Space" w={380} press={press} />
      </div>
      {void trayPulse}
    </AbsoluteFill>
  );
};

export const Ops: React.FC<{t: number}> = ({t}) => {
  const s = scene('ops');
  const clip = getClip('R5');
  const ct = t - s.start;
  const p14 = sStart('p14') - s.start - 0.35;
  const rc = clip.events.find((e) => e.type === 'rightclick' || /right/i.test(String(e.label ?? '')));
  const f2 = clip.events.find((e) => e.type === 'key' && /F2/i.test(String(e.label ?? e.value ?? '')));
  const dlg = clip.events.find((e) => e.type === 'dialog');
  const tR = rc?.t ?? 0.55;
  const menu = clip.rects.menu as number[] | undefined;
  const dR = clip.rects.dialog as number[] | undefined;
  const cams: Cam[] = [{t: 0, z: 1}, {t: Math.max(0.05, tR - 0.45), rect: menu ? [menu[0] - 700, menu[1] - 80, menu[2] + 1000, menu[3] + 160] : [200, 150, 1600, 900], zmax: 1.75, dur: 0.8}];
  if (f2) cams.push({t: f2.t - 0.15, rect: dR ? [dR[0] - 650, dR[1] - 380, dR[2] + 1300, dR[3] + 600] : [500, 300, 1400, 800], zmax: 1.5, dur: 0.6});
  const hovers = clip.events.filter((e) => e.type === 'hover');
  const ITEMS = hovers.length ? hovers.map((h) => ({t: h.t, lab: String(h.label), r: clip.rects['hover_' + h.label] as number[] | undefined})) : [];
  const SHOW: Record<string, string> = {'打开': '打开', '打开所在文件夹': '定位文件夹', '复制': '复制', '重命名': '重命名 F2'};
  const v1 = 1 - prog(ct, p14 - 0.1, p14 + 0.4, INOUT);
  const v2 = prog(ct, p14, p14 + 0.4, EXPO);
  // tray icon row in top-right "panel"
  const trayX = 1700, trayY = 1080 - 44 - 6 + 22;
  const lt = ct - p14;
  const trayIn = prog(lt, 0.0, 0.4, EXPO);
  const glow = prog(lt, 0.7, 0.9) * (1 - prog(lt, 1.6, 2.2));
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      {v1 > 0 && <AbsoluteFill style={{opacity: v1}}><RecStage clip={clip} t={ct} cams={cams}
        overlays={(k) => ITEMS.map((it, i) => {
          if (!it.r) return null;
          const on = prog(ct, it.t - 0.1, it.t + 0.1) * (1 - prog(ct, (ITEMS[i + 1]?.t ?? (f2?.t ?? 4.2)) - 0.15, (ITEMS[i + 1]?.t ?? (f2?.t ?? 4.2)) + 0.05));
          if (on <= 0) return null;
          return <div key={i} style={{position: 'absolute', left: it.r[0] * k - 4, top: 46 + it.r[1] * k - 2, width: it.r[2] * k + 8, height: it.r[3] * k + 4, borderRadius: 6,
            boxShadow: `0 0 0 2px rgba(79,227,255,${on}), 0 0 22px rgba(79,227,255,${0.6 * on})`}} />;
        })}
        screen={() => {
          const cur = ITEMS.filter((it) => ct >= it.t - 0.05).slice(-1)[0];
          const end = f2?.t ?? 4.2;
          const items = ['打开', '打开所在文件夹', '复制', '重命名'];
          const op = prog(ct, (ITEMS[0]?.t ?? 1) - 0.2, (ITEMS[0]?.t ?? 1) + 0.2) * (1 - prog(ct, end + 1.2, end + 1.6));
          if (op <= 0) return null;
          return <div style={{position: 'absolute', left: 70, top: 300, display: 'flex', flexDirection: 'column', gap: 18, opacity: op}}>
            {items.map((lab, i) => {
              const it = ITEMS.find((x) => x.lab === lab);
              const done = it && ct >= it.t - 0.05;
              const active = cur?.lab === lab && ct < end + 0.1 || (lab === '重命名' && ct >= end);
              const a = it ? prog(ct, it.t - 0.1, it.t + 0.25, EXPO) : 0;
              return <div key={lab} style={{display: 'flex', alignItems: 'center', gap: 16, padding: '14px 28px 14px 18px', borderRadius: 999,
                background: active ? 'rgba(30,79,216,0.55)' : 'rgba(8,14,40,0.8)', border: `1.5px solid ${done ? '#4FE3FF' : 'rgba(255,255,255,0.15)'}`,
                boxShadow: active ? '0 0 30px rgba(79,227,255,0.45)' : '0 12px 30px rgba(0,0,0,0.35)', transform: `translateX(${(1 - a) * -20}px) scale(${active ? 1.06 : 1})`, transformOrigin: 'left center',
                color: done ? '#fff' : 'rgba(255,255,255,0.45)', fontSize: 34, fontWeight: 700, whiteSpace: 'nowrap'}}>
                <span style={{width: 34, height: 34, borderRadius: 17, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontFamily: '"DejaVu Sans Mono", monospace',
                  background: done ? '#4FE3FF' : 'rgba(255,255,255,0.12)', color: '#0B1530'}}>{i + 1}</span>{SHOW[lab]}
              </div>;
            })}
          </div>;
        }} /></AbsoluteFill>}
      {v2 > 0 && (
        <AbsoluteFill style={{opacity: v2}}>
          {/* top panel w/ tray (Kylin panel at top-right to keep subtitle zone clear) */}
          <div style={{position: 'absolute', right: 80, top: 40, height: 70, padding: '0 26px', borderRadius: 18, background: 'rgba(14,22,54,0.8)', border: '1px solid rgba(255,255,255,0.14)',
            display: 'flex', alignItems: 'center', gap: 26, color: '#DCE6FF', fontSize: 24, boxShadow: '0 20px 50px rgba(0,0,0,0.4)', opacity: trayIn, transform: `translateY(${(1 - trayIn) * -20}px)`}}>
            <svg width="28" height="28" viewBox="0 0 28 28"><path d="M4 11 a14 14 0 0 1 20 0 M8 15 a8 8 0 0 1 12 0" stroke="#DCE6FF" strokeWidth="2.4" fill="none" strokeLinecap="round" /><circle cx="14" cy="20" r="2.4" fill="#DCE6FF" /></svg>
            <svg width="28" height="28" viewBox="0 0 28 28"><path d="M5 11 h5 l6-5 v16 l-6-5 H5z" fill="#DCE6FF" /><path d="M20 10 a6 6 0 0 1 0 8" stroke="#DCE6FF" strokeWidth="2.2" fill="none" /></svg>
            <div style={{position: 'relative'}}>
              <div style={{position: 'absolute', left: -14, top: -14, width: 70, height: 70, borderRadius: 35, background: `radial-gradient(circle, rgba(79,227,255,${0.7 * glow}), transparent 70%)`}} />
              <AppIcon size={42} id="tray" />
            </div>
            <span style={{fontFamily: '"DejaVu Sans", sans-serif'}}>10:24</span>
          </div>
          <TrayAnimWrap lt={lt} />
        </AbsoluteFill>
      )}
      {void trayX}{void trayY}{void BACK}
    </AbsoluteFill>
  );
};
/* Variant of tray anim targeting the top-right panel */
const TrayAnimWrap: React.FC<{lt: number}> = ({lt}) => {
  const minP = prog(lt, 0.1, 0.8, INOUT);
  const press = prog(lt, 1.05, 1.12) * (1 - prog(lt, 1.45, 1.55));
  const keyIn = prog(lt, 0.6, 1.0, EXPO);
  const back = spr(lt, 1.4, {stiffness: 170, damping: 15});
  const W = 940, H = 560;
  const tX = 1920 - 80 - 26 - 21 - 60, tY = 40 + 35; // approx tray icon center
  const homeX = 960, homeY = 380;
  const goingBack = lt >= 1.4;
  const sc = goingBack ? lerp(0.03, 1, back) : lerp(1, 0.03, minP);
  const cx = goingBack ? lerp(tX, homeX, Math.min(1, back)) : lerp(homeX, tX, minP);
  const cy = goingBack ? lerp(tY, homeY, Math.min(1, back)) : lerp(homeY, tY, minP);
  const op = goingBack ? Math.min(1, back * 3) : 1 - prog(lt, 0.65, 0.8);
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <div style={{position: 'absolute', left: cx - W / 2, top: cy - H / 2, width: W, height: H, transform: `scale(${sc})`, opacity: op, borderRadius: 12, overflow: 'hidden',
        background: '#F6F7FA', boxShadow: '0 40px 100px rgba(0,0,10,0.55)'}}>
        <WindowChrome w={W} />
        <div style={{margin: 12, height: 44, borderRadius: 6, border: '2px solid #3B82F6', background: '#fff', display: 'flex', alignItems: 'center', padding: '0 14px', color: '#9AA1AB', fontSize: 18}}>输入文件名即搜</div>
        {new Array(10).fill(0).map((_, i) => <div key={i} style={{margin: '0 12px', height: 40, background: i % 2 ? '#F2F5F9' : '#fff', display: 'flex', alignItems: 'center', gap: 20, paddingLeft: 14}}>
          <div style={{width: 160 + (i * 37) % 120, height: 12, borderRadius: 6, background: '#D5DCE6'}} /><div style={{width: 300, height: 12, borderRadius: 6, background: '#E6EAF0'}} /><div style={{width: 80, height: 12, borderRadius: 6, background: '#E6EAF0'}} /></div>)}
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 680, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 30, opacity: keyIn * (1 - prog(lt, 1.6, 1.9)), transform: `translateY(${(1 - keyIn) * 40}px) scale(${1 - 0.1 * prog(lt, 1.6, 1.9)})`}}>
        <Key label="Alt" w={180} press={press} />
        <div style={{fontSize: 56, color: C.dim, fontWeight: 300}}>+</div>
        <Key label="Space" w={380} press={press} />
      </div>
    </AbsoluteFill>
  );
};
export const _o = TrayAnim;
