"""MiniMax TTS. Key from env MM_KEY only (never written to disk)."""
import json, os, sys, urllib.request, concurrent.futures as cf
K=os.environ['MM_KEY']; S=json.load(open('script.json',encoding='utf-8'))
only=set(a for a in sys.argv[1:] if not a.startswith('--'))
def one(s):
    out=f"audio/{s['id']}.mp3"
    if only and s['id'] not in only: return s['id'],'skip'
    if os.path.exists(out) and not only and '--force' not in sys.argv: return s['id'],'exists'
    emo = 'happy' if s['chapter'] in ('title','outro','offline') else 'neutral'
    body={"model":"speech-02-hd","text":s['tts'],"stream":False,"language_boost":"Chinese",
      "voice_setting":{"voice_id":"presenter_male","speed":1.1,"vol":1.0,"pitch":0,"emotion":emo},
      "audio_setting":{"sample_rate":44100,"bitrate":256000,"format":"mp3","channel":1}}
    req=urllib.request.Request('https://api.minimax.io/v1/t2a_v2',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+K,'Content-Type':'application/json'})
    r=json.loads(urllib.request.urlopen(req,timeout=120).read())
    if r.get('base_resp',{}).get('status_code')!=0: return s['id'],'ERR '+json.dumps(r.get('base_resp'),ensure_ascii=False)
    open(out,'wb').write(bytes.fromhex(r['data']['audio'])); return s['id'],'ok'
with cf.ThreadPoolExecutor(6) as ex:
    for i,st in ex.map(one,S): print(i,st)
