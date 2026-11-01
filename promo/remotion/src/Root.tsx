import React from 'react';
import {Composition} from 'remotion';
import {Main} from './Main';
import {TOTAL_FRAMES} from './theme';

export const Root: React.FC = () => (
  <>
    <Composition id="Main" component={Main} durationInFrames={TOTAL_FRAMES} fps={30} width={1920} height={1080} defaultProps={{noAudio: false}} />
  </>
);
