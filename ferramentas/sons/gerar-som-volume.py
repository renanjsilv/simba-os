# Gera usr/share/sounds/simba/volume.oga do simba-apps: python3 gerar-som-volume.py 560 v.wav; ffmpeg -i v.wav -c:a libvorbis -q:a 5 volume.oga
import math, wave, struct, sys
sr=48000; dur=0.62; n=int(sr*dur)
f0=float(sys.argv[1]) if len(sys.argv)>1 else 700.0
out=[0.0]*n
for i in range(n):
    t=i/sr
    att=0.5-0.5*math.cos(math.pi*min(1,t/0.010))          # ataque suave de 10 ms
    # leve "subida" de afinação no começo (soa arredondado, tipo gota)
    f=f0*(1-0.03*math.exp(-t/0.02))
    ph=2*math.pi*f*t
    s=(1.00*math.sin(ph)*math.exp(-t/0.17)
      +0.30*math.sin(2*ph+0.3)*math.exp(-t/0.08)
      +0.08*math.sin(3*ph+0.7)*math.exp(-t/0.04)
      +0.18*math.sin(1.5*ph)*math.exp(-t/0.10))
    out[i]=att*s
# reverberação curta: ecos difusos
rev=out[:]
for d,g in ((0.029,0.22),(0.041,0.18),(0.057,0.14),(0.083,0.10),(0.113,0.07),(0.151,0.05)):
    k=int(d*sr)
    for i in range(k,n): rev[i]+=g*out[i-k]
# cauda até o fim + fade
for i in range(n):
    t=i/sr
    if t>dur-0.08: rev[i]*=0.5+0.5*math.cos(math.pi*(t-(dur-0.08))/0.08)
pk=max(abs(x) for x in rev); g=10**(-7/20)/pk
with wave.open(sys.argv[2] if len(sys.argv)>2 else 'volume.wav','w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(b''.join(struct.pack('<h',int(max(-1,min(1,x*g))*32767)) for x in rev))
