#!/usr/bin/env python3
"""wake.py reading the mic (raw and AU streams) and the "só assistente de voz" permissions.

  ~/.local/share/draco/venv/bin/python -I tests/test_mic_permissoes.py
"""
import io
import os
import subprocess
import sys

import numpy as np

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CODE)
sys.path.insert(0, os.path.join(CODE, "lib"))
sys.argv = [sys.argv[0], "--teste"]
import wake  # noqa: E402
import config  # noqa: E402

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("ok   " if cond else "FALHA"), name)


class FakeProc:
    def __init__(self, data):
        self.stdout = io.BytesIO(data)

    def terminate(self):
        pass

    def wait(self):
        pass


def mic_from(data):
    m = wake.Mic.__new__(wake.Mic)
    m.proc = FakeProc(data)
    m.swap = False
    m.zi = np.zeros((len(wake.Mic.HIGHPASS), 2))
    m.skip_au_header()
    return m


tone = (np.sin(np.arange(16000) * 2 * np.pi * 440 / 16000) * 8000).astype(np.int16)
raw = mic_from(tone.tobytes()).read(1280)
au_head = b".snd" + (24).to_bytes(4, "big") + (0xFFFFFFFF).to_bytes(4, "big") + (3).to_bytes(4, "big") \
    + (16000).to_bytes(4, "big") + (1).to_bytes(4, "big")
au = mic_from(au_head + tone.astype(">i2").tobytes()).read(1280)
check("mic: PCM cru é lido como está", np.abs(np.frombuffer(raw, np.int16)).max() > 4000)
check("mic: fluxo AU (pw-record sem --raw) vira o mesmo PCM", np.array_equal(raw, au))

# Permissions
total = config.opencode_permission({"PERMISSAO": "total"})
voz = config.opencode_permission({"PERMISSAO": "voz"})
check("opencode: modo total libera tudo", total == "allow")
check("opencode: só voz nega o resto", voz["*"] == "deny" and voz["bash"]["*"] == "deny")
check("opencode: só voz deixa mídia e lembretes", voz["bash"].get("dr-midia *") == "allow"
      and voz["bash"].get("dr-lembrete *") == "allow")
check("opencode: só voz não libera arquivos, teclas nem WhatsApp",
      not any(k.split()[0].endswith(("dr-arquivos", "dr-key", "dr-whatsapp")) for k in voz["bash"] if k != "*"))
check("opencode: só voz deixa só o volume/brilho do dr-sistema",
      "dr-sistema volume *" in voz["bash"] and not any("wifi" in k for k in voz["bash"]))
args = config.claude_voice_only_args()
check("claude: só voz sem Read/Edit", args[args.index("--tools") + 1] == "Bash,WebSearch,WebFetch"
      and "Edit" in args[args.index("--disallowedTools") + 1])
check("claude: só voz sem --dangerously-skip-permissions", "--dangerously-skip-permissions" not in args)

# The draco script picks the flags and the prompt note from the settings
env = subprocess.run(["python3", os.path.join(CODE, "lib", "config.py"), "env"], capture_output=True, text=True).stdout
check("config env: DRACO_PERMISSAO presente", "DRACO_PERMISSAO=" in env)
check("config env: DRACO_STT_LOCAL presente", "DRACO_STT_LOCAL=" in env)
print(f"\n{ok} ok, {bad} falhas")
sys.exit(1 if bad else 0)
