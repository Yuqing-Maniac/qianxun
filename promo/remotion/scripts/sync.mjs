// Sync external assets (recordings, music, sfx) into public/ and write src/gen/assets.json
import fs from 'fs'; import path from 'path';
const Q='/home/claude/video/q', RM=Q+'/rm';
const out={rec:{},recFiles:{},music:null,sfx:[],sfxReadme:null};
const lock=fs.existsSync(Q+'/rec/RECORDING.lock');
const cp=(a,b)=>{const sa=fs.statSync(a); if(!fs.existsSync(b)||fs.statSync(b).size!==sa.size||fs.statSync(b).mtimeMs<sa.mtimeMs){fs.mkdirSync(path.dirname(b),{recursive:true});fs.copyFileSync(a,b);}};
for(const k of ['R1','R2','R3','R4','R5']){
  const j=`${Q}/rec/${k}.json`, v=`${Q}/rec/${k}.mp4`;
  if(fs.existsSync(j)&&fs.existsSync(v)){
    try{ const d=JSON.parse(fs.readFileSync(j,'utf8')); cp(v,`${RM}/public/rec/${k}.mp4`); out.rec[k]=d; out.recFiles[k]=`rec/${k}.mp4`; }catch(e){console.error('bad',k,e.message)}
  }
}
if(fs.existsSync(Q+'/music/bgm.wav')){cp(Q+'/music/bgm.wav',RM+'/public/music/bgm.wav'); out.music='music/bgm.wav';}
if(fs.existsSync(Q+'/music/sfx')) for(const f of fs.readdirSync(Q+'/music/sfx')) if(/\.(wav|mp3)$/i.test(f)){cp(`${Q}/music/sfx/${f}`,`${RM}/public/sfx/${f}`); out.sfx.push(f);}
fs.writeFileSync(RM+'/src/gen/assets.json',JSON.stringify(out,null,1));
console.log('lock',lock,'rec',Object.keys(out.rec),'music',out.music,'sfx',out.sfx);
