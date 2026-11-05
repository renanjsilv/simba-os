#!/usr/bin/env python3
"""Anthropic Messages API -> OpenAI Chat Completions, so Claude Code (Draco's brain) can
run on services that only speak the OpenAI format (NVIDIA NIM, Groq...).

  anthropic_proxy.py [--porta 47821]

Claude Code is pointed at http://127.0.0.1:<port>/<provider> (ANTHROPIC_BASE_URL) with
the provider's key as ANTHROPIC_AUTH_TOKEN; requests to /<provider>/v1/messages are
translated (system, text, images, tool_use/tool_result, tools, streaming SSE with tool
calls) and sent to UPSTREAM[provider] with that key. Listens on localhost only; exits
after IDLE seconds without requests (the draco script starts it again when needed).
"""
import http.server
import json
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

UPSTREAM = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "groq": "https://api.groq.com/openai/v1",
}
PORT = int(sys.argv[sys.argv.index("--porta") + 1]) if "--porta" in sys.argv else 47821
IDLE = 1800
LOG = __import__("os").path.expanduser("~/.local/share/draco/proxy.log")
MAX_TOKENS = 16384  # several OpenAI-style services refuse Claude Code's larger defaults
last_request = time.monotonic()


# ---------------------------------------------------------------- request: Anthropic -> OpenAI

def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if b.get("type") == "text")


def clean_schema(schema):
    """Drop JSON-schema keys some OpenAI-style services reject."""
    if isinstance(schema, dict):
        return {k: clean_schema(v) for k, v in schema.items() if k not in ("$schema",)}
    if isinstance(schema, list):
        return [clean_schema(v) for v in schema]
    return schema


def to_openai(req):
    msgs = []
    system = text_of(req.get("system"))
    if system:
        msgs.append({"role": "system", "content": system})
    for m in req.get("messages", []):
        content = m.get("content")
        if isinstance(content, str):
            msgs.append({"role": m["role"], "content": content})
            continue
        if m["role"] == "assistant":
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            calls = [{"id": b["id"], "type": "function",
                      "function": {"name": b["name"], "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}}
                     for b in content if b.get("type") == "tool_use"]
            out = {"role": "assistant", "content": text or None}
            if calls:
                out["tool_calls"] = calls
            msgs.append(out)
            continue
        # user: tool results first (they answer the previous assistant turn), then the rest
        parts = []
        for b in content:
            t = b.get("type")
            if t == "tool_result":
                c = b.get("content")
                body = text_of(c) if not isinstance(c, str) else c
                if b.get("is_error"):
                    body = "ERRO: " + body
                msgs.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": body or "(vazio)"})
            elif t == "text":
                parts.append({"type": "text", "text": b.get("text", "")})
            elif t == "image" and b.get("source", {}).get("type") == "base64":
                src = b["source"]
                parts.append({"type": "image_url",
                              "image_url": {"url": f"data:{src['media_type']};base64,{src['data']}"}})
        if parts:
            only_text = all(p["type"] == "text" for p in parts)
            msgs.append({"role": "user", "content": "\n".join(p["text"] for p in parts) if only_text else parts})
    out = {"model": req.get("model"), "messages": msgs,
           "max_tokens": min(int(req.get("max_tokens") or 4096), MAX_TOKENS)}
    for k in ("temperature", "top_p"):
        if k in req:
            out[k] = req[k]
    if req.get("stop_sequences"):
        out["stop"] = req["stop_sequences"]
    tools = [t for t in req.get("tools", []) if t.get("name") and "input_schema" in t]
    if tools:
        out["tools"] = [{"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": clean_schema(t["input_schema"])}} for t in tools]
        tc = req.get("tool_choice") or {}
        out["tool_choice"] = {"auto": "auto", "any": "required", "none": "none"}.get(tc.get("type"), "auto")
        if tc.get("type") == "tool":
            out["tool_choice"] = {"type": "function", "function": {"name": tc["name"]}}
    if req.get("stream"):
        out["stream"] = True
        out["stream_options"] = {"include_usage": True}
    return out


# ---------------------------------------------------------------- response: OpenAI -> Anthropic

STOP = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use", "function_call": "tool_use"}


def parse_args(s):
    try:
        v = json.loads(s or "{}")
        return v if isinstance(v, dict) else {"value": v}
    except ValueError:
        return {"raw": s}


def from_openai(resp, model):
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = []
    if msg.get("content"):
        content.append({"type": "text", "text": msg["content"]})
    for c in msg.get("tool_calls") or []:
        content.append({"type": "tool_use", "id": c.get("id") or "toolu_" + uuid.uuid4().hex[:20],
                        "name": c["function"]["name"], "input": parse_args(c["function"].get("arguments"))})
    usage = resp.get("usage") or {}
    return {"id": "msg_" + uuid.uuid4().hex[:24], "type": "message", "role": "assistant", "model": model,
            "content": content or [{"type": "text", "text": ""}],
            "stop_reason": STOP.get(choice.get("finish_reason"), "end_turn"), "stop_sequence": None,
            "usage": {"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)}}


class Streamer:
    """Turns OpenAI chat.completion.chunk events into Anthropic SSE events."""

    def __init__(self, write, model):
        self.write, self.model = write, model
        self.index = -1
        self.open = None        # "text" or the OpenAI tool-call index of the open block
        self.tools = {}          # OpenAI tool index -> our block index
        self.stop = "end_turn"
        self.usage = {"input_tokens": 0, "output_tokens": 0}

    def event(self, kind, data):
        data["type"] = kind
        self.write(f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode())

    def start(self):
        self.event("message_start", {"message": {
            "id": "msg_" + uuid.uuid4().hex[:24], "type": "message", "role": "assistant", "model": self.model,
            "content": [], "stop_reason": None, "stop_sequence": None, "usage": dict(self.usage)}})

    def close_block(self):
        if self.open is not None:
            self.event("content_block_stop", {"index": self.index})
            self.open = None

    def chunk(self, ch):
        if ch.get("usage"):
            self.usage = {"input_tokens": ch["usage"].get("prompt_tokens", 0),
                          "output_tokens": ch["usage"].get("completion_tokens", 0)}
        for choice in ch.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                if self.open != "text":
                    self.close_block()
                    self.index += 1
                    self.open = "text"
                    self.event("content_block_start", {"index": self.index, "content_block": {"type": "text", "text": ""}})
                self.event("content_block_delta", {"index": self.index,
                                                   "delta": {"type": "text_delta", "text": delta["content"]}})
            for tc in delta.get("tool_calls") or []:
                k = tc.get("index", 0)
                if k not in self.tools:
                    self.close_block()
                    self.index += 1
                    self.tools[k] = self.index
                    self.open = ("tool", k)
                    fn = tc.get("function") or {}
                    self.event("content_block_start", {"index": self.index, "content_block": {
                        "type": "tool_use", "id": tc.get("id") or "toolu_" + uuid.uuid4().hex[:20],
                        "name": fn.get("name", ""), "input": {}}})
                args = (tc.get("function") or {}).get("arguments")
                if args:
                    self.event("content_block_delta", {"index": self.tools[k],
                                                       "delta": {"type": "input_json_delta", "partial_json": args}})
            if choice.get("finish_reason"):
                self.stop = STOP.get(choice["finish_reason"], "end_turn")

    def finish(self):
        self.close_block()
        self.event("message_delta", {"delta": {"stop_reason": self.stop, "stop_sequence": None},
                                     "usage": {"output_tokens": self.usage["output_tokens"]}})
        self.event("message_stop", {})


# ---------------------------------------------------------------- server

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error(self, code, message, kind="api_error"):
        try:
            with open(LOG, "a") as f:
                f.write(f"{time.strftime('%F %T')} {code} {message[:300]}\n")
        except OSError:
            pass
        self.send_json(code, {"type": "error", "error": {"type": kind, "message": message}})

    def do_GET(self):
        self.send_json(200, {"ok": True})

    do_HEAD = do_GET

    def do_POST(self):
        global last_request
        last_request = time.monotonic()
        parts = self.path.split("?")[0].strip("/").split("/", 1)
        provider, rest = parts[0], (parts[1] if len(parts) > 1 else "")
        body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
        if provider not in UPSTREAM:
            return self.error(404, f"provedor desconhecido: {provider}", "not_found_error")
        if rest.endswith("count_tokens"):
            return self.send_json(200, {"input_tokens": len(json.dumps(body)) // 4})
        if not rest.endswith("messages"):
            return self.error(404, "rota desconhecida", "not_found_error")
        key = (self.headers.get("authorization") or "").removeprefix("Bearer ").strip() or self.headers.get("x-api-key", "")
        req = to_openai(body)
        up = urllib.request.Request(UPSTREAM[provider] + "/chat/completions", data=json.dumps(req).encode(),
                                    headers={"Authorization": f"Bearer {key}", "content-type": "application/json",
                                             "User-Agent": "draco-proxy/1.0"})
        try:
            r = urllib.request.urlopen(up, timeout=300)
        except urllib.error.HTTPError as e:
            msg = e.read(800).decode(errors="ignore")
            kind = {401: "authentication_error", 403: "permission_error", 404: "not_found_error",
                    429: "rate_limit_error"}.get(e.code, "api_error")
            return self.error(e.code, f"{provider}: {msg}", kind)
        except (urllib.error.URLError, OSError) as e:
            return self.error(502, f"{provider}: sem conexão ({e})")
        model = body.get("model", "")
        if not req.get("stream"):
            return self.send_json(200, from_openai(json.load(r), model))
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()
        self.close_connection = True
        s = Streamer(lambda b: (self.wfile.write(b), self.wfile.flush()), model)
        s.start()
        try:
            for raw in r:
                line = raw.decode(errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    s.chunk(json.loads(data))
                except ValueError:
                    continue
            s.finish()
        except (BrokenPipeError, ConnectionResetError):
            pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    srv = Server(("127.0.0.1", PORT), Handler)

    def idle_exit():
        while time.monotonic() - last_request < IDLE:
            time.sleep(30)
        srv.shutdown()
    threading.Thread(target=idle_exit, daemon=True).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
