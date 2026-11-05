import json, subprocess, sys
import os, tempfile
T=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib", "transcript.py")
os.chdir(tempfile.mkdtemp())
def W(*ws):  # (word,start,end)
    return [{"word":w,"start":s,"end":e} for w,s,e in ws]
def J(words, segs=None):
    segs = segs or [{"start":0,"end":9,"text":" ".join(w["word"] for w in words),"no_speech_prob":0.01,"avg_logprob":-0.2,"compression_ratio":1.0}]
    return {"text":" ".join(w["word"] for w in words),"words":words,"segments":segs}
def run(data, *args, trig=None):
    open("a.json","w").write(json.dumps(data))
    extra=[]
    if trig is not None:
        open("b.json","w").write(json.dumps(trig)); extra=["--gatilho","b.json"]
    r=subprocess.run(["python3",T,"groq","a.json",*args,*extra],capture_output=True,text=True)
    return r.returncode, r.stdout.strip()
ok=0; bad=0
def check(name, got, exp):
    global ok,bad
    if got==exp: ok+=1; print("ok  ",name)
    else: bad+=1; print("FAIL",name,got,"!=",exp)
check("F10 normal", run(J(W(("Abre",0,.3),("o",.3,.4),("Spotify.",.4,1)))), (0,"Abre o Spotify."))
check("F10 alucinação silêncio", run(J(W(("Obrigado.",0,1)),[{"start":0,"end":1,"text":"Obrigado.","no_speech_prob":0.7,"avg_logprob":-0.9,"compression_ratio":1}])), (0,""))
check("wake: Draco + pedido", run(J(W(("Draco,",1.2,1.7),("que",2.1,2.3),("horas",2.3,2.6),("são?",2.6,3))),"--wake","2.0"), (0,"que horas são?"))
check("wake: conversa antes do Draco", run(J(W(("tá",0.1,.3),("bom.",.3,.6),("Draco",1.1,1.6),("abre",2.2,2.5),("o",2.5,2.6),("YouTube",2.6,3))),"--wake","2.0"), (0,"abre o YouTube"))
check("wake: sem Draco", run(J(W(("Muito",0.2,.5),("obrigada",.5,1),("pelo",1,1.2),("convite.",1.2,2)))," --wake".strip(),"2.0"), (2,""))
check("wake: 'fraco' não vale", run(J(W(("ele",.2,.4),("tá",.4,.6),("fraco",.6,1.1),("hoje",2.2,2.6))),"--wake","2.0"), (2,""))
check("wake: Draco só no fim (pedido de outra pessoa)", run(J(W(("abre",0.2,.5),("o",.5,.6),("Spotify",.6,1),("e",3,3.1),("chama",3.1,3.4),("o",3.4,3.5),("Draco",3.5,4))),"--wake","2.0"), (2,""))
check("wake: Drako grafia", run(J(W(("Drako,",1.3,1.8),("toca",2.2,2.5),("música",2.5,3))),"--wake","2.0"), (0,"toca música"))
check("wake: só Draco", run(J(W(("Draco.",1.3,1.8))),"--wake","2.0"), (3,""))
check("wake: nome perdido, gatilho ouviu", run(J(W(("abri",2.3,2.6),("o",2.6,2.7),("Spotify",2.7,3.2))),"--wake","2.0",trig={"text":" Draco","segments":[{"text":" Draco","no_speech_prob":0.01,"avg_logprob":-0.1,"compression_ratio":1}]}), (0,"abri o Spotify"))
check("wake: nome perdido, gatilho não ouviu", run(J(W(("abri",2.3,2.6),("o",2.6,2.7),("Spotify",2.7,3.2))),"--wake","2.0",trig={"text":" Não","segments":[{"text":" Não","no_speech_prob":0.01,"avg_logprob":-0.1,"compression_ratio":1}]}), (2,""))
check("wake: conversa no gatilho é descartada", run(J(W(("Será?",0.3,0.8),("toca",2.3,2.6),("rock",2.6,3))),"--wake","2.0",trig={"text":" Será? Draco","segments":[{"text":" Será? Draco","no_speech_prob":0.01,"avg_logprob":-0.1,"compression_ratio":1}]}), (0,"toca rock"))
for t,exp in (("Draco",0),("Drácula",2),("Fraco",2),("Daco",0),("Obrigado.",2)):
    open("b.json","w").write(json.dumps({"text":t,"segments":[{"text":t,"no_speech_prob":0.01,"avg_logprob":-0.1,"compression_ratio":1}]}))
    check(f"gatilho '{t}'", subprocess.run(["python3",T,"gatilho","b.json"]).returncode, exp)
print(f"\n{ok} ok, {bad} falhas"); sys.exit(1 if bad else 0)
