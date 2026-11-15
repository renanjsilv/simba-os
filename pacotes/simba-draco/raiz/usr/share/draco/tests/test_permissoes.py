#!/usr/bin/env python3
"""The "só assistente de voz" permissions (opencode and Claude Code).

  python3 -I tests/test_permissoes.py
"""
import os
import subprocess
import sys

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CODE)
sys.path.insert(0, os.path.join(CODE, "lib"))
import config  # noqa: E402

ok = bad = 0


def check(name, cond):
    global ok, bad
    ok += bool(cond)
    bad += not cond
    print(("ok   " if cond else "FALHA"), name)


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
