import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {scene, prog, EXPO, INOUT} from '../theme';

/** Mounts a scene in [start-pre, end+post]; gives the child absolute time t. Applies enter/exit transitions. */
export const SceneWrap: React.FC<{id: string; pre?: number; post?: number; enter?: 'fade' | 'zoom' | 'rise' | 'none'; exit?: 'fade' | 'zoomThrough' | 'none' | 'sink'; children: (t: number) => React.ReactNode}> = ({id, pre = 0.4, post = 0.4, enter = 'zoom', exit = 'zoomThrough', children}) => {
  const f = useCurrentFrame();
  const t = f / 30;
  const s = scene(id);
  if (t < s.start - pre || t > s.end + post) return null;
  const pin = enter === 'none' ? 1 : prog(t, s.start - pre, s.start + pre * 0.9, EXPO);
  const pout = exit === 'none' ? 0 : prog(t, s.end - post * 0.8, s.end + post, INOUT);
  let sc = 1, op = 1, blur = 0, ty = 0;
  if (enter === 'zoom') {sc *= 0.94 + 0.06 * pin; op *= pin; blur += (1 - pin) * 10;}
  if (enter === 'fade') op *= pin;
  if (enter === 'rise') {ty += (1 - pin) * 60; op *= pin; blur += (1 - pin) * 6;}
  if (exit === 'zoomThrough') {sc *= 1 + 0.18 * pout; op *= 1 - pout; blur += pout * 14;}
  if (exit === 'fade') op *= 1 - pout;
  if (exit === 'sink') {sc *= 1 - 0.06 * pout; op *= 1 - pout; blur += pout * 8;}
  return (
    <AbsoluteFill style={{opacity: op, transform: `translateY(${ty}px) scale(${sc})`, filter: blur > 0.3 ? `blur(${blur}px)` : undefined}}>
      {children(t)}
    </AbsoluteFill>
  );
};
