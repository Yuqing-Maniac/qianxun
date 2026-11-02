import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Clip} from '../rec';

/** Placeholder rendering of the real 千寻 main window at recording resolution (2400x1440, scale 1.5). */
const FILES: [string, string, string, string][] = [
  ['信息化建设总体方案-v3.docx', '/home/kylin/文档/项目/2024/综合组', '2.4 MB', '2026-10-15 16:20'],
  ['总体方案评审意见.wps', '/home/kylin/文档/评审/2025', '186 KB', '2026-09-28 10:02'],
  ['办公楼改造总体方案.pdf', '/data/资料/方案库', '12.7 MB', '2026-08-03 09:41'],
  ['总体方案-汇报版.pptx', '/home/kylin/桌面', '28.1 MB', '2026-10-12 21:13'],
  ['总体方案草稿.docx', '/home/kylin/文档/草稿', '640 KB', '2026-07-19 14:55'],
  ['档案数字化总体方案.doc', '/data/归档/2023/档案', '1.1 MB', '2025-11-02 11:30'],
  ['总体方案附件-接口表.xlsx', '/home/kylin/文档/项目/2024/综合组', '312 KB', '2026-10-15 16:22'],
  ['总体方案（报批稿）.pdf', '/home/kylin/下载', '8.9 MB', '2026-10-17 08:47'],
  ['年会活动总体方案说明.txt', '/home/kylin/文档/笔记', '14 KB', '2026-06-08 19:20'],
  ['总体方案编写规范.docx', '/data/资料/规范', '520 KB', '2025-03-14 15:00'],
  ['培训体系总体方案-v1.wps', '/data/归档/2022/培训', '2.0 MB', '2024-12-01 10:12'],
  ['总体方案评审纪要.docx', '/home/kylin/文档/会议', '96 KB', '2026-10-10 17:31'],
  ['总体方案技术路线图.png', '/home/kylin/图片/汇报', '3.6 MB', '2026-09-30 22:06'],
  ['门户网站总体方案.md', '/home/kylin/代码/portal/doc', '22 KB', '2026-05-27 13:44'],
  ['总体方案-批注版.pdf', '/home/kylin/文档/评审/2025', '9.4 MB', '2026-09-29 08:15'],
  ['总体方案背景资料.zip', '/data/资料/方案库', '86.3 MB', '2026-04-11 16:58'],
  ['采购管理总体方案.docx', '/data/项目/采购', '1.8 MB', '2026-02-20 09:09'],
  ['总体方案模板.dotx', '/home/kylin/模板', '48 KB', '2024-08-08 08:08'],
  ['总体方案演示.mp4', '/home/kylin/视频', '74.2 MB', '2026-10-01 20:40'],
  ['总体方案-终稿备份.docx', '/media/kylin/U盘/备份', '2.4 MB', '2026-10-16 23:59'],
  ['总体方案问题清单.et', '/home/kylin/文档/项目/2024/综合组', '64 KB', '2026-10-14 11:11'],
  ['总体方案对比分析.xlsx', '/data/资料/方案库', '410 KB', '2026-03-05 15:25'],
  ['总体方案修改说明.docx', '/home/kylin/文档/草稿', '77 KB', '2026-10-13 18:46'],
  ['总体方案参考文献.txt', '/home/kylin/文档/笔记', '9 KB', '2026-01-17 10:33'],
  ['总体方案效果图.jpg', '/home/kylin/图片/汇报', '5.1 MB', '2026-09-30 22:07'],
  ['总体方案（定稿）.pdf', '/home/kylin/文档/项目/2024/综合组', '10.2 MB', '2026-10-16 18:00'],
  ['总体方案讲稿.txt', '/home/kylin/桌面', '6 KB', '2026-10-12 21:40'],
  ['总体方案-附图.vsdx', '/home/kylin/文档/项目/2024/综合组', '1.3 MB', '2026-10-15 16:25'],
  ['总体方案录音.mp3', '/home/kylin/音乐/录音', '9.8 MB', '2026-10-11 15:02'],
  ['总体方案答疑.docx', '/home/kylin/文档/会议', '120 KB', '2026-10-10 17:50'],
  ['总体方案目录.md', '/home/kylin/代码/portal/doc', '3 KB', '2026-05-27 13:47'],
  ['总体方案封面.png', '/home/kylin/图片/汇报', '880 KB', '2026-09-30 22:01'],
];

export const MockApp: React.FC<{clip: Clip; t: number}> = ({clip, t}) => {
  // current query text from events
  let q = '';
  for (const e of clip.events) {
    if ((e.type === 'type' || e.type === 'query') && t >= e.t) {
      const full = String(e.label ?? e.value ?? '');
      const n = Math.min(full.length, Math.floor((t - e.t) / 0.09) + 1);
      q = full.slice(0, n);
    }
  }
  const kw = q.replace(/[!|*:]/g, ' ').trim().split(/\s+/)[0] || '';
  const rows = q ? FILES.filter((_, i) => (i * 7 + q.length * 3) % 5 !== 0 || q.length < 3) : FILES.slice(0, 0);
  const shown = (q ? rows : FILES).slice(0, 34);
  const ms = 18 + (q.length * 5) % 19;
  const S = 1.5;
  const fs = 13 * S;
  const col = [495, 690, 135, 300];
  return (
    <AbsoluteFill style={{background: '#F6F7FA', fontFamily: '"Noto Sans CJK SC", sans-serif', fontSize: fs, color: '#1F2329'}}>
      <div style={{height: 40, display: 'flex', alignItems: 'center', gap: 30, paddingLeft: 18, background: '#FFFFFF', borderBottom: '1px solid #E3E6EB'}}>
        {['文件(F)', '搜索(S)', '工具(T)', '帮助(H)'].map((m) => <span key={m}>{m}</span>)}
      </div>
      <div style={{position: 'absolute', left: 9, top: 49, right: 9, height: 58, display: 'flex', gap: 12}}>
        <div style={{flex: 1, background: '#fff', border: '2px solid #3B82F6', borderRadius: 6, display: 'flex', alignItems: 'center', paddingLeft: 16, fontSize: fs * 1.15, color: q ? '#111' : '#9AA1AB'}}>
          {q || '输入文件名即搜　空格=与　|=或　!=非　*.pdf　ext:docx　size:>10mb　dm:today　（F1 查看语法）'}
          {q && Math.floor(t * 2) % 2 === 0 && <span style={{width: 2, height: 30, background: '#111', marginLeft: 2}} />}
        </div>
        <div style={{width: 200, background: '#fff', border: '1px solid #CBD2DB', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 14px'}}>
          <span>全部</span><span style={{color: '#666'}}>▾</span>
        </div>
      </div>
      <div style={{position: 'absolute', left: 9, top: 116, right: 9, bottom: 52, background: '#fff', border: '1px solid #DDE1E7', overflow: 'hidden'}}>
        <div style={{display: 'flex', height: 42, alignItems: 'center', background: '#F1F3F6', borderBottom: '1px solid #DDE1E7', fontWeight: 500}}>
          {['名称', '路径', '大小', '修改时间'].map((h, i) => <div key={h} style={{width: col[i], paddingLeft: 12, borderRight: '1px solid #DDE1E7', height: '100%', display: 'flex', alignItems: 'center'}}>{h}{i === 0 ? '  ▴' : ''}</div>)}
        </div>
        {shown.map((r, i) => (
          <div key={i} style={{display: 'flex', height: 36, alignItems: 'center', background: i % 2 ? '#F7F9FC' : '#fff'}}>
            {r.map((c, j) => <div key={j} style={{width: col[j], paddingLeft: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: j === 1 ? '#5B6470' : undefined}}>
              {j === 0 && kw && c.includes(kw) ? <>{c.split(kw)[0]}<b style={{color: '#1E4FD8', background: 'rgba(30,79,216,0.12)'}}>{kw}</b>{c.split(kw).slice(1).join(kw)}</> : c}
            </div>)}
          </div>
        ))}
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 45, background: '#EEF0F3', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', color: '#4B5563'}}>
        <span>{q ? `${shown.length} 个结果　·　${ms} 毫秒` : '1,046,382 个对象'}</span><span>实时监控中 · 已索引 1,046,382</span>
      </div>
      <div style={{position: 'absolute', right: 30, top: 160, padding: '8px 18px', borderRadius: 8, background: 'rgba(255,170,0,0.15)', color: '#A16207', fontSize: 22}}>占位画面 · 等待录屏</div>
    </AbsoluteFill>
  );
};
