import React from 'react';
import {AbsoluteFill} from 'remotion';
import {getClip, clickTimes} from '../rec';
import {RecStage, Cam} from '../components/RecStage';
import {FONT, scene, prog, EXPO} from '../theme';
import {Capsule} from '../components/Glass';

export const Filter: React.FC<{t: number}> = ({t}) => {
  const s = scene('filter');
  const clip = getClip('R4');
  const ct = t - s.start;
  const clicks = clickTimes(clip);
  const lab = (re: RegExp) => clip.events.filter((e) => e.type === 'click' && re.test(String(e.label ?? '')));
  const tF = lab(/filter|combo|筛选/)[0]?.t ?? clicks[0]?.t ?? 1;
  const tSel = lab(/select|图片/)[0]?.t ?? tF + 1.2;
  const hs = lab(/header|大小|sort/);
  const tH = hs[0]?.t ?? tSel + 1;
  const tHd = hs[hs.length - 1]?.t ?? tH;
  const cams: Cam[] = [
    {t: 0, z: 1},
    {t: Math.max(0.1, tF - 0.8), rect: [1000, 20, 1400, 640], zmax: 1.75, dur: 0.85},
    {t: tSel + 0.3, z: 1, dur: 0.9},
  ];
  const l1 = prog(ct, tSel + 0.15, tSel + 0.5, EXPO) * (1 - prog(ct, tH - 0.2, tH + 0.05));
  const l2 = prog(ct, tH + 0.1, tH + 0.45, EXPO);
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <RecStage clip={clip} t={ct} cams={cams} />
      <div style={{position: 'absolute', left: 0, right: 0, top: 46, display: 'flex', justifyContent: 'center'}}>
        {l1 > 0 && <Capsule style={{opacity: l1, transform: `translateY(${(1 - l1) * -20}px)`}}>一键筛选 · 图片</Capsule>}
        {l2 > 0 && <Capsule color="#34D399" style={{opacity: l2, transform: `translateY(${(1 - l2) * -20}px)`, position: 'absolute'}}>点击表头 · 按大小排序</Capsule>}
      </div>
    </AbsoluteFill>
  );
};
