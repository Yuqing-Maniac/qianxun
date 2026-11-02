// node scripts/stills.mjs outdir scale frame...
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition, openBrowser} from '@remotion/renderer';
import path from 'path';
const [out, scale, ...frames] = process.argv.slice(2);
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const browser = await openBrowser('chrome', {browserExecutable: '/tmp/chromium'});
const comp = await selectComposition({serveUrl, id: 'Main', inputProps: {noAudio: true}, puppeteerInstance: browser});
for (const f of frames) {
  await renderStill({composition: comp, serveUrl, frame: +f, output: `${out}/f${String(f).padStart(4, '0')}.png`, scale: +scale, inputProps: {noAudio: true}, puppeteerInstance: browser});
  process.stdout.write(f + ' ');
}
await browser.close({silent: true});
