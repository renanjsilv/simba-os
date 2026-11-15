import json, subprocess, sys
import os, tempfile
T=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib", "transcript.py")
os.chdir(tempfile.mkdtemp())
def W(*ws):  # (word,start,end)
    return [{"word":w,"start":s,"end":e} for w,s,e in ws]
def J(words, segs=None):
    segs = segs or [{"start":0,"end":9,"text":" ".join(w["word"] for w in words),"no_speech_prob":0.01,"avg_logprob":-0.2,"compression_ratio":1.0}]
    return {"text":" ".join(w["word"] for w in words),"words":words,"segments":segs}
def run(data):
    open("a.json","w").write(json.dumps(data))
    r=subprocess.run(["python3",T,"groq","a.json"],capture_output=True,text=True)
    return r.returncode, r.stdout.strip()
def text(t):
    r=subprocess.run(["python3",T,"text",t],capture_output=True,text=True)
    return r.returncode, r.stdout.strip()
ok=0; bad=0
def check(name, got, exp):
    global ok,bad
    if got==exp: ok+=1; print("ok  ",name)
    else: bad+=1; print("FAIL",name,got,"!=",exp)
check("F10 normal", run(J(W(("Abre",0,.3),("o",.3,.4),("Spotify.",.4,1)))), (0,"Abre o Spotify."))
check("F10 alucinação silêncio", run(J(W(("Obrigado.",0,1)),[{"start":0,"end":1,"text":"Obrigado.","no_speech_prob":0.7,"avg_logprob":-0.9,"compression_ratio":1}])), (0,""))
check("F10 trecho inventado no fim", run(J(W(("toca",0,.3),("rock",.3,.8),("Obrigado.",3,4)),
      [{"start":0,"end":1,"text":"toca rock","no_speech_prob":0.01,"avg_logprob":-0.2,"compression_ratio":1},
       {"start":3,"end":4,"text":"Obrigado.","no_speech_prob":0.7,"avg_logprob":-0.9,"compression_ratio":1}])), (0,"toca rock"))
check("sem palavras: usa os trechos", run({"text":"abre o YouTube","segments":[{"start":0,"end":2,"text":" abre o YouTube","no_speech_prob":0.01,"avg_logprob":-0.2,"compression_ratio":1}]}), (0,"abre o YouTube"))
check("local normal", text("  que horas são? "), (0,"que horas são?"))
check("local alucinação", text("Legendas pela comunidade Amara.org"), (0,""))
print(f"\n{ok} ok, {bad} falhas"); sys.exit(1 if bad else 0)
