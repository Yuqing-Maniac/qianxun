import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Background, Grain} from './components/Background';
import {Subtitles} from './components/Subtitles';
import {SceneWrap} from './components/SceneWrap';
import {AudioLayer} from './AudioLayer';
import {Hook} from './scenes/Hook';
import {Title} from './scenes/Title';
import {Search} from './scenes/Search';
import {How} from './scenes/How';
import {Syntax} from './scenes/Syntax';
import {Filter} from './scenes/Filter';
import {Ops} from './scenes/Ops';
import {Offline} from './scenes/Offline';
import {Outro} from './scenes/Outro';
import {FONT} from './theme';

export const Main: React.FC<{noAudio?: boolean}> = ({noAudio}) => {
  const f = useCurrentFrame();
  const t = f / 30;
  return (
    <AbsoluteFill lang="zh-CN" style={{fontFamily: FONT, background: '#060B1E'}}>
      <Background intensity={1} grid={t < 10.5 ? 0.3 : 0.6} />
      <SceneWrap id="hook" pre={0} enter="none" exit="zoomThrough" post={0.35}>{(t) => <Hook t={t} />}</SceneWrap>
      <SceneWrap id="title" pre={0.2} enter="fade" exit="zoomThrough" post={0.45}>{(t) => <Title t={t} />}</SceneWrap>
      <SceneWrap id="search" pre={0.45} enter="none" exit="zoomThrough" post={0.4}>{(t) => <Search t={t} />}</SceneWrap>
      <SceneWrap id="how" pre={0.4} enter="zoom" exit="zoomThrough" post={0.4}>{(t) => <How t={t} />}</SceneWrap>
      <SceneWrap id="syntax" pre={0.4} enter="zoom" exit="sink" post={0.4}>{(t) => <Syntax t={t} />}</SceneWrap>
      <SceneWrap id="filter" pre={0.4} enter="rise" exit="sink" post={0.4}>{(t) => <Filter t={t} />}</SceneWrap>
      <SceneWrap id="ops" pre={0.4} enter="rise" exit="zoomThrough" post={0.4}>{(t) => <Ops t={t} />}</SceneWrap>
      <SceneWrap id="offline" pre={0.4} enter="zoom" exit="zoomThrough" post={0.45}>{(t) => <Offline t={t} />}</SceneWrap>
      <SceneWrap id="outro" pre={0.45} enter="zoom" exit="none" post={0}>{(t) => <Outro t={t} />}</SceneWrap>
      <Grain opacity={0.06} />
      <Subtitles />
      {!noAudio && <AudioLayer />}
    </AbsoluteFill>
  );
};
