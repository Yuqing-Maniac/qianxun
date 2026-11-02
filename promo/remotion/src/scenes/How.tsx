import React from 'react';
import {AbsoluteFill, random} from 'remotion';
import {getClip, rectOf} from '../rec';
import {RecStage, Cam, rx, ry} from '../components/RecStage';
import {FONT, MONO, prog, EXPO, BACK, INOUT, scene, sStart, spr, lerp, clamp, C} from '../theme';
import {Glass, gradText} from '../components/Glass';
import {AppIcon} from '../components/AppIcon';

const TOK = ['总体方案.docx', '会议纪要.wps', 'IMG_2031.jpg', 'main.c', '评审意见.pdf', '接口表.xlsx', 'README.md', '考勤.csv', '打印日志.txt', '汇报.pptx',
  '总体方案-v3.docx', 'setup.py', '培训材料.doc', '截图.png', 'utils.h', '采购清单.et', '年度总结.pdf', '录音.mp3', '笔记.txt', '演示.mp4',
  '采购总体方案.doc', 'config.json', 'server.cpp', '月报.docx', '方案对比.xlsx', 'build.log', '统计.py', '归档.zip', '总体方案（定稿）.pdf', '照片.JPG'];

/* ---------------- p06: memory index ---------------- */
const IndexAnim: React.FC<{lt: number}> = ({lt}) => {
  // tree nodes
  const nodes = [
    {x: 230, y: 540, n: '/'},
    {x: 400, y: 330, n: 'home'}, {x: 400, y: 540, n: 'data'}, {x: 400, y: 750, n: 'media'},
    {x: 560, y: 230, n: '文档'}, {x: 560, y: 360, n: '图片'}, {x: 560, y: 470, n: '代码'}, {x: 560, y: 610, n: '项目'}, {x: 560, y: 720, n: '归档'}, {x: 560, y: 840, n: 'U盘'},
  ];
  const edges = [[0, 1], [0, 2], [0, 3], [1, 4], [1, 5], [1, 6], [2, 7], [2, 8], [3, 9]];
  const treeIn = (i: number) => prog(lt, 0.05 + i * 0.06, 0.5 + i * 0.06, EXPO);
  const leaves = [4, 5, 6, 7, 8, 9];
  const RIB = {x: 790, y: 410, w: 1010, h: 250};
  const N = 150;
  const qT = 2.35; // query beam
  const beamX = RIB.x + RIB.w * prog(lt, qT, qT + 0.9, INOUT);
  const ribIn = prog(lt, 0.2, 0.8, EXPO);
  const items = new Array(N).fill(0).map((_, i) => {
    const leaf = nodes[leaves[Math.floor(random('lf' + i) * leaves.length)]];
    const t0 = 0.35 + random('t' + i) * 1.6;
    const fl = 0.75 + random('f' + i) * 0.35;
    const row = i % 5, colI = Math.floor(i / 5);
    const tx = RIB.x + 20 + colI * 33 + (row % 2) * 12, ty = RIB.y + 34 + row * 44;
    const p = clamp((lt - t0) / fl);
    if (p <= 0) return null;
    const e = INOUT(p);
    const mx = (leaf.x + tx) / 2, my = Math.min(leaf.y, ty) - 120 - random('h' + i) * 120;
    const x = (1 - e) * (1 - e) * leaf.x + 2 * (1 - e) * e * mx + e * e * tx;
    const y = (1 - e) * (1 - e) * leaf.y + 2 * (1 - e) * e * my + e * e * ty;
    const name = TOK[i % TOK.length];
    const match = name.includes('总体方案');
    const lit = match && beamX > tx ? prog(lt, qT + (tx - RIB.x) / RIB.w * 0.9, qT + (tx - RIB.x) / RIB.w * 0.9 + 0.2) : 0;
    const landed = p >= 1;
    return {x, y, name, landed, lit, p, match};
  });
  const landedCnt = items.filter((x) => x && x.landed).length;
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <svg width={1920} height={1080} style={{position: 'absolute'}}>
        <defs><linearGradient id="edge" x1="0" x2="1"><stop offset="0" stopColor="#4FA8FF" /><stop offset="1" stopColor="#4FE3FF" /></linearGradient></defs>
        {edges.map(([a, b], i) => {
          const A = nodes[a], B = nodes[b];
          const p = treeIn(b);
          const d = `M${A.x} ${A.y} C ${A.x + 80} ${A.y}, ${B.x - 80} ${B.y}, ${B.x} ${B.y}`;
          return <path key={i} d={d} stroke="url(#edge)" strokeOpacity={0.55} strokeWidth={2.5} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />;
        })}
      </svg>
      {nodes.map((n, i) => {
        const p = treeIn(i);
        return <div key={i} style={{position: 'absolute', left: n.x, top: n.y, transform: `translate(-50%,-50%) scale(${p})`, opacity: p,
          padding: i === 0 ? '10px 18px' : '6px 14px', borderRadius: 10, background: 'rgba(20,40,100,0.75)', border: '1px solid rgba(120,180,255,0.45)',
          color: '#DCEBFF', fontSize: i === 0 ? 30 : 22, fontFamily: i < 4 ? MONO : FONT, whiteSpace: 'nowrap', boxShadow: '0 0 20px rgba(60,140,255,0.35)'}}>{i === 0 ? '/' : n.n}</div>;
      })}
      <div style={{position: 'absolute', left: 170, top: 930, fontSize: 26, color: C.dim, opacity: treeIn(0), letterSpacing: 4}}>磁盘目录树</div>
      {/* ribbon */}
      <div style={{position: 'absolute', left: RIB.x, top: RIB.y, width: RIB.w * ribIn, height: RIB.h, borderRadius: 26, overflow: 'hidden',
        background: 'linear-gradient(180deg, rgba(30,79,216,0.28), rgba(19,163,194,0.18))', border: '1px solid rgba(110,200,255,0.5)',
        boxShadow: '0 0 60px rgba(40,150,255,0.35), inset 0 0 40px rgba(80,200,255,0.15)'}}>
        <div style={{position: 'absolute', inset: 0, background: `linear-gradient(90deg, transparent ${lt * 40 % 100 - 20}%, rgba(255,255,255,0.08) ${lt * 40 % 100}%, transparent ${lt * 40 % 100 + 20}%)`}} />
      </div>
      <div style={{position: 'absolute', left: RIB.x, top: RIB.y - 64, display: 'flex', alignItems: 'center', gap: 16, opacity: ribIn}}>
        <svg width="40" height="40" viewBox="0 0 40 40"><rect x="6" y="9" width="28" height="22" rx="3" fill="none" stroke="#4FE3FF" strokeWidth="2.5" />{[0, 1, 2, 3].map((i) => <line key={i} x1={11 + i * 6} y1="4" x2={11 + i * 6} y2="9" stroke="#4FE3FF" strokeWidth="2.5" />)}{[0, 1, 2, 3].map((i) => <line key={'b' + i} x1={11 + i * 6} y1="31" x2={11 + i * 6} y2="36" stroke="#4FE3FF" strokeWidth="2.5" />)}</svg>
        <span style={{fontSize: 34, fontWeight: 700, color: '#EAF6FF'}}>内存名称索引</span>
        <span style={{fontFamily: MONO, fontSize: 26, color: '#7FD8FF', marginLeft: 12}}>{Math.round(landedCnt / N * (getClip('R1').stats?.indexed ?? 1033990)).toLocaleString('en-US')} 条</span>
      </div>
      {items.map((it, i) => it && (it.landed && !it.lit ? (
        <div key={i} style={{position: 'absolute', left: it.x - 13, top: it.y - 4, width: 26, height: 8, borderRadius: 4,
          background: it.match ? 'rgba(140,230,255,0.85)' : 'rgba(150,190,255,0.45)', boxShadow: '0 0 8px rgba(80,180,255,0.6)',
          opacity: lt > qT && !it.match ? 1 - 0.6 * prog(lt, qT, qT + 0.6) : 1}} />
      ) : (
        <div key={i} style={{position: 'absolute', left: it.x, top: it.y, transform: `translate(-50%,-50%) scale(${it.landed ? 1.25 : 0.8 + 0.4 * Math.sin(it.p * Math.PI)})`,
          fontSize: 13, whiteSpace: 'nowrap', padding: '2px 6px', borderRadius: 5, fontFamily: FONT,
          background: it.lit ? `rgba(79,227,255,${0.25 + 0.55 * it.lit})` : 'rgba(170,200,255,0.12)',
          color: it.lit ? '#FFFFFF' : `rgba(210,228,255,${it.landed ? 0.55 : 0.9})`,
          boxShadow: it.lit ? `0 0 ${18 * it.lit}px rgba(79,227,255,0.9)` : undefined, zIndex: it.lit ? 2 : 1, opacity: (it.landed ? 1 : Math.min(1, 1.6 - it.p * 0.9))}}>{it.name}</div>
      )))}
      {/* query beam */}
      {lt > qT - 0.3 && (
        <>
          <div style={{position: 'absolute', left: 1080, top: 760, width: 440, height: 70, borderRadius: 35, background: 'rgba(255,255,255,0.95)', display: 'flex', alignItems: 'center', gap: 14, padding: '0 26px',
            fontSize: 32, color: '#111', opacity: prog(lt, qT - 0.3, qT), transform: `translateY(${(1 - prog(lt, qT - 0.3, qT, EXPO)) * 30}px)`, boxShadow: '0 20px 50px rgba(0,0,0,0.35)'}}>
            <AppIcon size={38} id="qb" />总体方案
          </div>
          <div style={{position: 'absolute', left: beamX - 3, top: RIB.y - 30, width: 6, height: RIB.h + 60, borderRadius: 3, background: 'linear-gradient(transparent, #BFF6FF, transparent)',
            boxShadow: '0 0 30px 8px rgba(79,227,255,0.7)', opacity: (lt > qT ? 1 : 0) * (1 - prog(lt, qT + 0.9, qT + 1.2))}} />
          <div style={{position: 'absolute', left: 1400, top: 690, fontFamily: MONO, fontSize: 30, color: C.green, opacity: prog(lt, qT + 0.9, qT + 1.2)}}>命中 6 项 · 12 ms</div>
        </>
      )}
    </AbsoluteFill>
  );
};

/* ---------------- p07: terminal + recording ---------------- */
const Terminal: React.FC<{ct: number; cmds: {t: number; s: string}[]; w: number; h: number}> = ({ct, cmds, w, h}) => {
  const lines: React.ReactNode[] = [];
  cmds.forEach((c, i) => {
    const avail = i === 0 ? 1.2 : c.t - cmds[i - 1].t - 0.25;
    const CH = Math.min(0.05, avail / Math.max(1, c.s.length));
    const startType = c.t - c.s.length * CH;
    if (ct < startType - 0.1) return;
    const n = clamp(Math.floor((ct - startType) / CH), 0, c.s.length);
    const done = ct >= c.t;
    lines.push(
      <div key={i} style={{whiteSpace: 'pre-wrap', wordBreak: 'keep-all', overflowWrap: 'normal', marginBottom: 12}}>
        <span style={{color: '#60A5FA'}}>~/文档/汇报</span><span style={{color: '#9AA4B2'}}>$ </span>
        <span style={{color: '#F3F4F6'}}>{c.s.slice(0, n)}</span>
        {!done && Math.floor(ct * 3) % 2 === 0 && <span style={{background: '#E5E7EB', width: 13, height: 26, display: 'inline-block', marginLeft: 1, verticalAlign: 'middle'}} />}
        {done && <span style={{color: '#6B7280', marginLeft: 16}}>{''}</span>}
      </div>,
    );
  });
  const last = cmds[cmds.length - 1];
  if (ct > last.t + 0.15) lines.push(<div key="p" style={{whiteSpace: 'pre'}}><span style={{color: '#60A5FA'}}>~/文档/汇报</span><span style={{color: '#9AA4B2'}}>$ </span>{Math.floor(ct * 3) % 2 === 0 && <span style={{background: '#E5E7EB', width: 13, height: 28, display: 'inline-block'}} />}</div>);
  return (
    <div style={{width: w, height: h, borderRadius: 14, overflow: 'hidden', background: 'rgba(10,12,20,0.92)', boxShadow: '0 30px 90px rgba(0,0,10,0.6), 0 0 0 1px rgba(255,255,255,0.1)'}}>
      <div style={{height: 44, display: 'flex', alignItems: 'center', padding: '0 16px', background: '#1B1E27', color: '#C8CCD4', fontFamily: FONT, fontSize: 16, gap: 10}}>
        <svg width="20" height="20" viewBox="0 0 20 20"><rect x="1" y="2" width="18" height="16" rx="3" fill="#2B2F3A" /><path d="M5 7 l3 3 -3 3" stroke="#34D399" strokeWidth="1.8" fill="none" /><line x1="10" y1="13" x2="15" y2="13" stroke="#9AA4B2" strokeWidth="1.8" /></svg>
        终端 — kylin@kylin-pc
      </div>
      <div style={{padding: '22px 22px', fontFamily: MONO, fontSize: 19, lineHeight: '31px'}}>{lines}</div>
    </div>
  );
};

const BADGE: Record<string, {c: string; sym: string; txt: string}> = {
  create: {c: '#34D399', sym: '+', txt: '新建'}, rename: {c: '#FBBF24', sym: '↻', txt: '改名'}, delete: {c: '#F87171', sym: '−', txt: '删除'},
};
const kindOf = (s: string) => /新建|create|touch|add/i.test(s) ? 'create' : /改名|rename|mv|move/i.test(s) ? 'rename' : /删除|delete|rm|remove/i.test(s) ? 'delete' : 'create';

export const r2Offset = () => sStart('p07') - 0.2 - scene('how').start; // clip t=0 in how-scene time

type Badge = {t: number; kind: string; name: string};
export const r2Badges = (): Badge[] => {
  const clip = getClip('R2');
  const ev = clip.events;
  const fs = ev.filter((e) => e.type === 'fs');
  return fs.map((f, i) => {
    const nextT = fs[i + 1]?.t ?? 1e9;
    const r = ev.find((e) => e.type === 'result' && e.t > f.t && e.t < nextT);
    const kind = kindOf(String(f.label ?? ''));
    const nm = String(f.label ?? '').split(/\s+/).slice(-1)[0];
    return {t: r ? r.t : f.t + 0.5, kind, name: nm};
  });
};

const LiveSync: React.FC<{ct: number}> = ({ct}) => {
  const clip = getClip('R2');
  const fs = clip.events.filter((e) => e.type === 'fs');
  const cmds = fs.map((e) => ({t: e.t, s: String(e.label ?? e.value ?? '')}));
  const box = {x: 735, y: 150, w: 1135, h: 640};
  const cams: Cam[] = [{t: 0, rect: [0, 20, 1500, 400], z: 1.42, ox: 0, oy: 0}];
  const badges = r2Badges();
  const tin = prog(ct, -1.2, -0.5, EXPO);
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 50, top: 150, transform: `translateX(${(1 - tin) * -80}px)`, opacity: tin}}>
        <Terminal ct={ct} cmds={cmds} w={650} h={640} />
      </div>
      <div style={{position: 'absolute', left: box.x - 2, top: box.y - 2, width: box.w + 4, height: box.h + 4, borderRadius: 16, boxShadow: '0 40px 100px rgba(0,0,10,0.6), 0 0 0 1px rgba(255,255,255,0.12)'}} />
      <RecStage clip={clip} t={ct} cams={cams} box={box} margin={0} offsetY={0} clipBox radius={14} k={box.w / clip.width} />
      {(() => (
          <div style={{position: 'absolute', left: box.x, width: box.w, top: box.y + box.h + 28, display: 'flex', justifyContent: 'center', gap: 22}}>
            {badges.map((b, i) => {
              const B = BADGE[b.kind];
              const age = ct - b.t;
              if (age < 0) return null;
              const a = spr(ct, b.t, {stiffness: 260, damping: 15});
              const pulse = Math.min(1, age / 0.7);
              return (
                <div key={i} style={{position: 'relative', opacity: Math.min(1, a), transform: `translateY(${(1 - a) * 30}px) scale(${0.85 + 0.15 * a})`}}>
                  <div style={{position: 'absolute', inset: -6, borderRadius: 999, border: `3px solid ${B.c}`, opacity: 1 - pulse, transform: `scale(${1 + 0.35 * pulse})`}} />
                  <div style={{display: 'flex', alignItems: 'center', gap: 10, padding: '10px 26px', borderRadius: 999, background: 'rgba(8,14,40,0.85)', border: `2px solid ${B.c}`,
                    boxShadow: `0 0 ${30 * (1.4 - pulse)}px ${B.c}AA, 0 14px 40px rgba(0,0,0,0.45)`, color: '#fff', fontFamily: FONT, fontSize: 32, fontWeight: 800, whiteSpace: 'nowrap'}}>
                    <span style={{color: B.c, fontSize: 38, fontFamily: MONO}}>{B.sym}</span>{B.txt}
                    <span style={{fontSize: 22, fontWeight: 500, color: 'rgba(255,255,255,0.7)', marginLeft: 6}}>{(b.t - (fs[i]?.t ?? b.t)).toFixed(1)} 秒内</span>
                  </div>
                </div>
              );
            })}
          </div>
        ))()}
    </AbsoluteFill>
  );
};

/* ---------------- p08: cache + relaunch ---------------- */
const Relaunch: React.FC<{lt: number}> = ({lt}) => {
  const disk = prog(lt, 0, 0.5, EXPO);
  const write = prog(lt, 0.3, 1.3, INOUT);
  const arrow = prog(lt, 1.2, 1.7, EXPO);
  const t0 = 1.55;
  const ring = prog(lt, t0 + 0.1, t0 + 0.8, (x) => x); // 0.7 s linear fill
  const appIn = spr(lt, t0, {stiffness: 180, damping: 16});
  const done = prog(lt, t0 + 0.8, t0 + 1.1, BACK);
  const R = 120, circ = 2 * Math.PI * R;
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      {/* disk */}
      <div style={{position: 'absolute', left: 300, top: 300, opacity: disk, transform: `scale(${0.85 + 0.15 * disk})`}}>
        <svg width="320" height="360" viewBox="0 0 320 360">
          <defs><linearGradient id="dk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2A3A70" /><stop offset="1" stopColor="#141D40" /></linearGradient></defs>
          <rect x="20" y="20" width="280" height="320" rx="28" fill="url(#dk)" stroke="rgba(120,180,255,0.5)" strokeWidth="2" />
          <circle cx="160" cy="150" r="90" fill="none" stroke="rgba(120,180,255,0.3)" strokeWidth="2" />
          <circle cx="160" cy="150" r="60" fill="none" stroke="rgba(120,180,255,0.22)" strokeWidth="2" />
          <circle cx="160" cy="150" r="14" fill="#4FE3FF" />
          <g transform={`rotate(${lt * 600} 160 150)`}><path d="M160 150 L160 60" stroke="#4FE3FF" strokeWidth="3" opacity="0.6" /></g>
          <rect x="50" y="280" width="220" height="14" rx="7" fill="rgba(255,255,255,0.1)" />
          <rect x="50" y="280" width={220 * write} height="14" rx="7" fill="#4FE3FF" />
        </svg>
        <div style={{textAlign: 'center', marginTop: 8, fontFamily: MONO, fontSize: 26, color: '#BFE6FF'}}>index.cache</div>
        <div style={{textAlign: 'center', marginTop: 4, fontSize: 26, color: C.dim}}>{write < 1 ? '写入索引缓存…' : '已落盘 ✓'}</div>
      </div>
      {/* flowing arrow */}
      <svg width="400" height="80" style={{position: 'absolute', left: 700, top: 440, opacity: arrow}}>
        <defs><linearGradient id="ar" x1="0" x2="1"><stop offset="0" stopColor="#4FE3FF" stopOpacity="0" /><stop offset="1" stopColor="#4FE3FF" /></linearGradient></defs>
        <path d="M10 40 H360" stroke="url(#ar)" strokeWidth="5" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - arrow} />
        <path d="M340 22 L370 40 L340 58" stroke="#4FE3FF" strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity={arrow} />
        <text x="185" y="20" fill="#BFE6FF" fontSize="24" textAnchor="middle" fontFamily={FONT}>再次启动</text>
      </svg>
      {/* app relaunch ring */}
      <div style={{position: 'absolute', left: 1180, top: 230, width: 480, height: 480, opacity: Math.min(1, appIn), transform: `scale(${0.8 + 0.2 * appIn})`}}>
        <svg width="480" height="480" style={{position: 'absolute'}}>
          <circle cx="240" cy="240" r={R} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="14" />
          <circle cx="240" cy="240" r={R} fill="none" stroke="#4FE3FF" strokeWidth="14" strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - ring)} transform="rotate(-90 240 240)" style={{filter: 'drop-shadow(0 0 12px #4FE3FF)'}} />
        </svg>
        <div style={{position: 'absolute', left: 240 - 70, top: 240 - 70}}><AppIcon size={140} id="rl" glow={done} /></div>
        <div style={{position: 'absolute', left: 0, right: 0, top: 400, textAlign: 'center', fontFamily: MONO, fontSize: 64, fontWeight: 700, ...gradText('#FFFFFF', '#8FDCFF')}}>
          {(0.7 * ring).toFixed(1)} 秒
        </div>
      </div>
      <div style={{position: 'absolute', left: 1180, width: 480, top: 770, textAlign: 'center', opacity: done, transform: `scale(${0.8 + 0.2 * done})`}}>
        <span style={{display: 'inline-block', padding: '10px 30px', borderRadius: 999, background: 'rgba(52,211,153,0.15)', border: '2px solid #34D399', color: '#D1FAE5', fontSize: 36, fontWeight: 800, boxShadow: '0 0 30px rgba(52,211,153,0.4)'}}>二次启动 &lt; 1 秒</span>
      </div>
    </AbsoluteFill>
  );
};

export const How: React.FC<{t: number}> = ({t}) => {
  const s = scene('how');
  const lt = t - s.start;
  const a = sStart('p06') - s.start - 0.85; // p06 anim start (tree visible during transition)
  const b = sStart('p07') - s.start - 0.45; // switch to p07
  const c = sStart('p08') - s.start - 0.3;
  const v1 = 1 - prog(lt, b - 0.2, b + 0.35, INOUT);
  const v2 = prog(lt, b - 0.1, b + 0.45, EXPO) * (1 - prog(lt, c - 0.2, c + 0.3, INOUT));
  const v3 = prog(lt, c, c + 0.5, EXPO);
  return (
    <AbsoluteFill>
      {v1 > 0 && <AbsoluteFill style={{opacity: v1, transform: `scale(${1 + 0.08 * (1 - v1)})`, filter: v1 < 1 ? `blur(${(1 - v1) * 8}px)` : undefined}}><IndexAnim lt={lt - a} /></AbsoluteFill>}
      {v2 > 0 && <AbsoluteFill style={{opacity: v2, transform: `scale(${0.96 + 0.04 * v2})`}}><LiveSync ct={lt - r2Offset()} /></AbsoluteFill>}
      {v3 > 0 && <AbsoluteFill style={{opacity: v3, transform: `scale(${0.95 + 0.05 * v3})`}}><Relaunch lt={lt - c} /></AbsoluteFill>}
    </AbsoluteFill>
  );
};
export const _h = {rectOf, rx, ry, lerp, Glass};
