#!/usr/bin/env python3
"""Draco's free brain: OpenCode with its free models (no account, no key).

Runs `opencode run --format json` and rewrites its events in the shape the draco
script already reads from Claude Code (stream-json): an "assistant" line for each
tool it uses (shown on the orb) and one final "result" line with the answer.

  opencode_brain.py [--continue] [--] <pedido>

The model comes from $DRACO_MODELO ("" = the best free one available). When a free
model is out (limit reached, retired), it is set aside for a while and the next free
one is tried, before anything was said. The instructions are the same prompt.md,
passed as OpenCode "instructions"; the conversation memory is the OpenCode session
saved in $RUN/opencode.session (--continue reuses it).
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "draco")
SESSAO = os.path.join(RUN, "opencode.session")
LIMITE = ("limit", "quota", "rate", "unavailable", "no-route", "429", "exhausted", "overloaded")


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def tool_line(name, desc):
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": {"description": desc}}]}})


def describe(part):
    st = part.get("state") or {}
    inp = st.get("input") or {}
    return st.get("title") if st.get("title") and st.get("title") != part.get("tool") else \
        inp.get("description") or inp.get("command") or inp.get("url") or inp.get("filePath") or part.get("tool", "")


def run_once(oc, model, prompt, instr, session):
    """(answer, error, session id, said anything?)"""
    cmd = [oc, "run", "--standalone", "--format", "json", "--archived", "--auto", "-m", model]
    if session:
        cmd += ["-s", session]
    env = {**os.environ, "OPENCODE_CONFIG_CONTENT": json.dumps({
        "instructions": [instr], "permission": "allow", "autoupdate": False, "share": "disabled"})}
    p = subprocess.Popen(cmd + ["--", prompt], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, text=True, env=env)
    texts, err, sid, acted = [], "", session, False
    for line in p.stdout:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        sid = ev.get("sessionID") or sid
        t, part = ev.get("type"), ev.get("part") or {}
        if t == "tool_use":
            acted = True
            tool_line(part.get("tool", ""), describe(part))
        elif t == "step_start":
            texts = []  # only the last step's text is the answer
        elif t == "text" and part.get("text"):
            texts.append(part["text"])
        elif t == "error":
            e = ev.get("error") or {}
            err = f"{e.get('type', '')}: {e.get('message', '')}".strip(": ")
    p.wait()
    if p.returncode and not err and not texts:
        err = f"opencode saiu com {p.returncode}"
    return "\n".join(texts).strip(), err, sid, acted or bool(texts)


def main():
    args = sys.argv[1:]
    cont = "--continue" in args
    args = [a for a in args if a not in ("--continue", "--")]
    prompt = " ".join(args)
    oc = config.opencode_bin()
    if not oc:
        emit({"type": "result", "is_error": True, "result": "O OpenCode não está instalado."})
        return
    os.makedirs(RUN, exist_ok=True)
    instr = os.environ.get("DRACO_PROMPT_FILE", "")
    session = ""
    if cont:
        try:
            with open(SESSAO) as f:
                session = f.read().strip()
        except OSError:
            pass
    chosen = os.environ.get("DRACO_MODELO", "")
    tried, last_err = set(), ""
    for _ in range(4):
        model = chosen if chosen and chosen not in tried else config.free_model(skip=tried)
        if not model:
            break
        tried.add(model)
        answer, err, sid, said = run_once(oc, model, prompt, instr, session)
        if sid:
            with open(SESSAO, "w") as f:
                f.write(sid)
        if answer or said or not err:
            emit({"type": "result", "is_error": bool(err and not answer), "result": answer or err})
            return
        last_err = err
        if not any(k in err.lower() for k in LIMITE):
            break
        config.free_mark_out(model)
        session = ""  # a session can be tied to the model that failed
    emit({"type": "result", "is_error": True,
          "result": last_err or "Nenhum modelo grátis está disponível agora."})


if __name__ == "__main__":
    main()
