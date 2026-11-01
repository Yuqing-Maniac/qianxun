import React from 'react';
import {AbsoluteFill} from 'remotion';
import {noise2D} from '@remotion/noise';
import {FONT, MONO, prog, EXPO, BACK, INOUT, lerp, clamp, spr, sStart, C} from '../theme';
import {Arrow, Ripple} from '../components/Cursor';
import {Glass, gradText} from '../components/Glass';

const Folder: React.FC<{size?: number; hl?: number}> = ({size = 64, hl = 0}) => (
  <svg width={size} height={size * 0.82} viewBox="0 0 64 52">
    <defs><linearGradient id="fg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#6BB4FF" /><stop offset="1" stopColor="#2F7BEA" /></linearGradient></defs>
    <path d="M3 8 a4 4 0 0 1 4-4 h16 l6 6 h28 a4 4 0 0 1 4 4 v4 H3z" fill="#2A6FD6" />
    <rect x="3" y="14" width="58" height="35" rx="4" fill="url(#fg)" />
    <rect x="3" y="14" width="58" height="6" rx="3" fill="#fff" opacity="0.18" />
    {hl > 0 && <rect x="1" y="2" width="62" height="49" rx="6" fill="none" stroke="#4FE3FF" strokeWidth="2" opacity={hl} />}
  </svg>
);
const FileIco: React.FC<{size?: number; c?: string}> = ({size = 56, c = '#9AA4B2'}) => (
  <svg width={size * 0.8} height={size} viewBox="0 0 40 50"><path d="M4 2 h22 l10 10 v34 a2 2 0 0 1-2 2 H4 a2 2 0 0 1-2-2 V4 a2 2 0 0 1 2-2z" fill="#F3F5F8" stroke="#C9D0DA" /><path d="M26 2 v10 h10" fill="#E2E7EE" stroke="#C9D0DA" /><rect x="8" y="22" width="22" height="3" rx="1.5" fill={c} /><rect x="8" y="29" width="16" height="3" rx="1.5" fill={c} opacity="0.6" /></svg>
);

const PATHS = [
  ['主目录'],
  ['主目录', '文档'],
  ['主目录', '文档', '项目'],
  ['主目录', '文档', '项目', '2024'],
  ['主目录', '文档', '项目', '2024', '综合组'],
  ['主目录', '文档', '项目', '2024', '综合组', '旧版'],
];
const NAMES = [
  ['桌面', '文档', '下载', '图片', '视频', '音乐', '模板', '代码'],
  ['项目', '会议', '评审', '草稿', '笔记', '归档', '资料', '报销'],
  ['2021', '2022', '2023', '2024', '2025', '临时', '共享', '备份'],
  ['综合组', '行政', '人事', '财务', '采购', '培训', '质量', '后勤'],
  ['旧版', '新版', '对外', '内部', '图纸', '附件', '汇报', '评审'],
  ['', '', '', '', '', '', '', ''],
];

const FMWindow: React.FC<{level: number; w: number; h: number; hlIdx?: number; hl?: number; scroll?: number; empty?: number}> = ({level, w, h, hlIdx = -1, hl = 0, scroll = 0, empty = 0}) => {
  const crumbs = PATHS[level];
  const names = NAMES[level];
  return (
    <div style={{width: w, height: h, borderRadius: 12, overflow: 'hidden', background: '#FFFFFF', fontFamily: FONT, color: '#1F2329',
      boxShadow: '0 30px 90px rgba(0,0,15,0.55), 0 0 0 1px rgba(255,255,255,0.1)'}}>
      <div style={{height: 46, display: 'flex', alignItems: 'center', background: 'linear-gradient(#FFF,#F3F5F8)', borderBottom: '1px solid #E4E7EC', paddingLeft: 14, gap: 10, position: 'relative'}}>
        <div style={{display: 'flex', gap: 6, color: '#8A929D', fontSize: 18}}><span>‹</span><span>›</span></div>
        <div style={{display: 'flex', alignItems: 'center', height: 30, padding: '0 12px', background: '#EEF1F5', borderRadius: 6, fontSize: 15, gap: 6, maxWidth: w - 230, overflow: 'hidden', whiteSpace: 'nowrap'}}>
          {crumbs.map((c, i) => <React.Fragment key={i}>{i > 0 && <span style={{color: '#A0A7B1'}}>›</span>}<span style={{color: i === crumbs.length - 1 ? '#1E4FD8' : '#4B5563', fontWeight: i === crumbs.length - 1 ? 600 : 400}}>{c}</span></React.Fragment>)}
        </div>
        <div style={{position: 'absolute', right: 10, display: 'flex', gap: 18, color: '#5B6470', fontSize: 15}}><span>—</span><span>☐</span><span>✕</span></div>
      </div>
      <div style={{display: 'flex', height: h - 46}}>
        <div style={{width: 150, background: '#F7F8FA', borderRight: '1px solid #ECEEF2', padding: '14px 0', fontSize: 15, color: '#4B5563'}}>
          {['主目录', '桌面', '文档', '下载', '图片', '计算机', '回收站'].map((s, i) => <div key={s} style={{padding: '8px 22px', background: i === 2 && level > 0 ? '#E6EEFF' : undefined, color: i === 2 && level > 0 ? '#1E4FD8' : undefined}}>{s}</div>)}
        </div>
        <div style={{flex: 1, position: 'relative', overflow: 'hidden'}}>
          <div style={{position: 'absolute', left: 0, right: 0, top: -scroll, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', rowGap: 18, padding: 22}}>
            {(level < 5 ? [...names, ...names.map((n) => n + '-备份')] : []).map((n, i) => (
              <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, fontSize: 14, padding: 6, borderRadius: 8,
                background: i === hlIdx ? `rgba(30,79,216,${0.14 * hl})` : undefined}}>
                {i % 5 === 4 && level > 1 ? <FileIco size={52} /> : <Folder size={60} hl={i === hlIdx ? hl : 0} />}
                <span>{n}</span>
              </div>
            ))}
          </div>
          {level === 5 && (
            <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, opacity: empty, color: '#8A929D'}}>
              <svg width="90" height="90" viewBox="0 0 90 90"><circle cx="38" cy="38" r="24" fill="none" stroke="#B8C0CC" strokeWidth="6" /><line x1="56" y1="56" x2="78" y2="78" stroke="#B8C0CC" strokeWidth="7" strokeLinecap="round" /></svg>
              <div style={{fontSize: 20}}>该文件夹为空</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/** Hook scene 0–10.48 */
export const Hook: React.FC<{t: number}> = ({t}) => {
  const p2 = sStart('p02') - 0.25; // contrast starts
  // --- part 1: drilling windows ---
  const opens = [0.35, 1.35, 2.25, 3.05, 3.8, 4.45];
  const W = 900, H = 560;
  const part1Out = prog(t, p2 - 0.2, p2 + 0.5, INOUT);
  const stress = clamp((t - 2.5) / 2.5);
  const shake = t > 3.6 && t < p2 ? noise2D('sh', t * 9, 0) * 6 * stress : 0;
  // cursor path (screen coords), double clicks on a folder in the top window just before the next open
  const winPos = (i: number) => ({x: 300 + i * 70, y: 120 + i * 48});
  const target = (i: number) => {const wp = winPos(i); const col = [3, 0, 3, 0, 0][i] ?? 0; return {x: wp.x + 150 + 22 + (W - 150 - 44) / 4 * (col + 0.5), y: wp.y + 46 + 22 + 50};};
  let cx = 1500, cy = 900;
  const keys: {t: number; x: number; y: number}[] = [{t: 0, x: 1500, y: 900}];
  for (let i = 0; i < 5; i++) {const tg = target(i); keys.push({t: opens[i + 1] - 0.35, x: tg.x, y: tg.y}); keys.push({t: opens[i + 1] - 0.05, x: tg.x, y: tg.y});}
  keys.push({t: 5.0, x: winPos(5).x + 560, y: winPos(5).y + 320});
  keys.push({t: 5.4, x: winPos(5).x + 520, y: winPos(5).y + 380});
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i], b = keys[i + 1];
    if (t >= a.t && t <= b.t) {const u = INOUT((t - a.t) / Math.max(0.001, b.t - a.t)); cx = lerp(a.x, b.x, u); cy = lerp(a.y, b.y, u);}
    if (t > keys[keys.length - 1].t) {cx = keys[keys.length - 1].x; cy = keys[keys.length - 1].y;}
  }
  const clickTs = opens.slice(1).flatMap((o) => [o - 0.28, o - 0.14]);
  const pressed = clickTs.some((c) => t >= c && t < c + 0.07) ? 1 : 0;

  // --- part 2: contrast ---
  const c2 = prog(t, p2, p2 + 0.8, EXPO);
  const typeStart = p2 + 0.7;
  const q = '总体方案';
  const typed = q.slice(0, clamp(Math.floor((t - typeStart) / 0.12) + 1, 0, 4));
  const resP = prog(t, typeStart + 0.55, typeStart + 0.9, EXPO);
  const kStart = sStart('p02') + 2.2;
  const kTyped = q.slice(0, clamp(Math.floor((t - kStart) / 0.12) + 1, 0, 4));
  const qm = 0.55 + 0.45 * Math.abs(Math.sin((t - kStart) * 4));

  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      {/* part 1 */}
      {part1Out < 1 && (
        <AbsoluteFill style={{opacity: 1 - part1Out, transform: `translate(${shake}px, ${shake * 0.4}px) scale(${1 - 0.08 * part1Out})`, filter: part1Out > 0 ? `blur(${part1Out * 10}px)` : undefined}}>
          {opens.map((o, i) => {
            if (t < o) return null;
            const s = spr(t, o, {stiffness: 220, damping: 22});
            const wp = winPos(i);
            const top = i === opens.filter((x) => t >= x).length - 1;
            const lvl = i;
            const hlIdx = i < 5 ? [3, 0, 3, 0, 0][i] : -1;
            const hl = i < 5 ? prog(t, opens[i + 1] - 0.4, opens[i + 1] - 0.2) : 0;
            const scroll = i === 4 ? 0 : 0;
            return (
              <div key={i} style={{position: 'absolute', left: wp.x, top: wp.y, opacity: s, transform: `scale(${0.9 + 0.1 * s})`, transformOrigin: 'top left', filter: top ? undefined : `brightness(${0.75})`}}>
                <FMWindow level={lvl} w={W} h={H} hlIdx={hlIdx} hl={hl} scroll={scroll} empty={prog(t, opens[5] + 0.2, opens[5] + 0.6)} />
              </div>
            );
          })}
          {/* growing frustration: question marks + time */}
          {t > 3.2 && [0, 1, 2].map((i) => {
            const a = prog(t, 3.3 + i * 0.5, 3.8 + i * 0.5, BACK);
            return <div key={i} style={{position: 'absolute', left: [1320, 1460, 1390][i], top: [210, 330, 470][i], fontSize: [90, 64, 110][i], fontWeight: 900, color: '#FF7A7A',
              opacity: a * 0.9, transform: `scale(${a}) rotate(${[-12, 10, -4][i]}deg)`, textShadow: '0 0 30px rgba(255,90,90,0.6)'}}>？</div>;
          })}
          <div style={{position: 'absolute', left: 120, top: 70, display: 'flex', alignItems: 'center', gap: 14, opacity: prog(t, 1.0, 1.6), fontFamily: MONO, color: 'rgba(220,230,255,0.75)', fontSize: 26}}>
            <span style={{width: 12, height: 12, borderRadius: 6, background: '#FF6B6B', boxShadow: '0 0 12px #FF6B6B'}} />
            已翻找 {String(Math.floor(clamp(t - 0.3, 0, 99) * 14.7)).padStart(2, '0')} 秒 · 第 {Math.min(6, opens.filter((x) => t >= x).length)} 层目录
          </div>
          <div style={{position: 'absolute', left: cx, top: cy}}>
            {clickTs.map((c, i) => <Ripple key={i} age={t - c} scale={0.8} />)}
            <Arrow size={40} pressed={pressed} />
          </div>
        </AbsoluteFill>
      )}

      {/* part 2: contrast */}
      {c2 > 0 && (
        <AbsoluteFill>
          <div style={{position: 'absolute', left: 960 - 2, top: 140, width: 4, height: 700, background: 'linear-gradient(transparent, rgba(160,200,255,0.5), transparent)', opacity: c2, transform: `scaleY(${c2})`}} />
          <div style={{position: 'absolute', left: 960 - 40, top: 450, width: 80, textAlign: 'center', fontSize: 36, fontWeight: 900, color: 'rgba(200,220,255,0.6)', opacity: c2, fontFamily: SMILEYFALLBACK}}>VS</div>
          {/* left: Windows */}
          <Glass style={{left: 130, top: 170, width: 700, height: 600, transform: `translateX(${(1 - c2) * -120}px)`, opacity: c2}}>
            <div style={{padding: '36px 44px'}}>
              <div style={{fontSize: 26, color: C.dim, letterSpacing: 4}}>WINDOWS</div>
              <div style={{fontSize: 58, fontWeight: 900, marginTop: 4, ...gradText()}}>Everything</div>
              <div style={{marginTop: 30, height: 64, borderRadius: 14, background: 'rgba(255,255,255,0.92)', display: 'flex', alignItems: 'center', padding: '0 22px', color: '#111', fontSize: 30, gap: 12}}>
                <svg width="28" height="28" viewBox="0 0 28 28"><circle cx="12" cy="12" r="8" stroke="#555" strokeWidth="3" fill="none" /><line x1="18" y1="18" x2="25" y2="25" stroke="#555" strokeWidth="3" strokeLinecap="round" /></svg>
                {typed}<span style={{width: 2, height: 32, background: '#111', opacity: Math.floor(t * 3) % 2}} />
              </div>
              <div style={{marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10}}>
                {['信息化建设总体方案-v3.docx', '办公楼改造总体方案.pdf', '总体方案-汇报版.pptx', '总体方案评审纪要.docx'].map((n, i) => {
                  const p = prog(t, typeStart + 0.55 + i * 0.06, typeStart + 0.95 + i * 0.06);
                  return <div key={i} style={{height: 50, borderRadius: 10, background: 'rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', padding: '0 18px', fontSize: 24, gap: 14, opacity: p, transform: `translateY(${(1 - p) * 14}px)`}}>
                    <span style={{width: 10, height: 10, borderRadius: 5, background: C.cyanHi}} />{n}</div>;
                })}
              </div>
              <div style={{marginTop: 22, display: 'flex', alignItems: 'center', gap: 14, fontSize: 30, color: C.green, opacity: resP, transform: `scale(${0.8 + 0.2 * resP})`, transformOrigin: 'left center'}}>
                <svg width="40" height="40" viewBox="0 0 40 40"><circle cx="20" cy="20" r="18" fill="rgba(52,211,153,0.18)" stroke="#34D399" strokeWidth="2.5" /><path d="M12 20 l6 6 l11-12" stroke="#34D399" strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="30" strokeDashoffset={30 * (1 - resP)} /></svg>
                秒出结果
              </div>
            </div>
          </Glass>
          {/* right: Kylin */}
          <Glass style={{left: 1090, top: 170, width: 700, height: 600, transform: `translateX(${(1 - c2) * 120}px)`, opacity: c2}}>
            <div style={{padding: '36px 44px', height: '100%', boxSizing: 'border-box', position: 'relative'}}>
              <div style={{fontSize: 26, color: C.dim, letterSpacing: 4}}>KYLIN OS</div>
              <div style={{fontSize: 58, fontWeight: 900, marginTop: 4, ...gradText('#FFFFFF', '#FFC9C9')}}>银河麒麟</div>
              <div style={{marginTop: 30, height: 64, borderRadius: 14, background: 'rgba(255,255,255,0.92)', display: 'flex', alignItems: 'center', padding: '0 22px', color: '#111', fontSize: 30, gap: 12}}>
                <svg width="28" height="28" viewBox="0 0 28 28"><circle cx="12" cy="12" r="8" stroke="#555" strokeWidth="3" fill="none" /><line x1="18" y1="18" x2="25" y2="25" stroke="#555" strokeWidth="3" strokeLinecap="round" /></svg>
                {t > kStart ? kTyped : <span style={{color: '#9AA1AB'}}>搜索文件…</span>}
              </div>
              <div style={{position: 'absolute', left: 0, right: 0, top: 250, bottom: 40, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
                <div style={{fontSize: 210, fontWeight: 900, lineHeight: 1, color: '#FF8A8A', opacity: t > kStart + 0.5 ? qm : 0.25,
                  textShadow: `0 0 ${50 * qm}px rgba(255,100,100,0.7)`, transform: `scale(${t > kStart + 0.5 ? 0.95 + 0.08 * qm : 0.9})`}}>？</div>
                <div style={{fontSize: 28, color: 'rgba(255,200,200,0.8)', marginTop: 6, opacity: prog(t, kStart + 0.8, kStart + 1.3)}}>无处可寻</div>
              </div>
            </div>
          </Glass>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
const SMILEYFALLBACK = '"Smiley Sans", sans-serif';
