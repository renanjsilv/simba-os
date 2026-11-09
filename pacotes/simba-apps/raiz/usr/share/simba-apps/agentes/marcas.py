"""Logos das empresas de IA (agente e provedor do modelo) para o chat.

Os SVGs ficam em logos/ (ícones da LobeHub, licença MIT). Os coloridos se chamam
simba-ia-<marca>.svg; os monocromáticos, simba-ia-<marca>-symbolic.svg, e o GTK
os pinta com a cor do texto do tema (ficam legíveis no claro e no escuro).
"""
from pathlib import Path
import re

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

LOGOS = Path(__file__).resolve().parent / "logos"
GENERICO = "simba-agente"

# Agente (CLI) → marca do logo
AGENTE_MARCA = {
    "claude": "claude",
    "codex": "codex",
    "agy": "antigravity",
    "opencode": "opencode",
    "copilot": "copilot",
    "cursor-agent": "cursor",
    "grok": "grok",
}

# Primeiro trecho de "provedor/modelo" (OpenCode, Crush, Pi…) → marca
PROVEDOR_MARCA = {
    "openrouter": "openrouter", "anthropic": "claude", "openai": "openai",
    "google": "gemini", "google-vertex": "gemini", "gemini": "gemini", "vertex": "gemini",
    "xai": "grok", "x-ai": "grok", "grok": "grok", "deepseek": "deepseek",
    "qwen": "qwen", "alibaba": "qwen", "dashscope": "qwen", "mistral": "mistral",
    "moonshot": "moonshot", "moonshotai": "moonshot", "kimi": "moonshot",
    "zai": "zai", "z-ai": "zai", "zhipu": "zai", "zhipuai": "zai", "minimax": "minimax",
    "ollama": "ollama", "groq": "groq", "perplexity": "perplexity",
    "fireworks": "fireworks", "fireworks-ai": "fireworks", "together": "together",
    "togetherai": "together", "github-copilot": "copilot", "copilot": "copilot",
    "opencode": "opencode",
}

# Nome do modelo sem provedor → marca de quem fez o modelo
MODELO_MARCA = (
    (r"claude|opus|sonnet|haiku|fable", "claude"),
    (r"gpt|codex|\bo[134]\b|o[134]-|openai", "openai"),
    (r"gemini|gemma", "gemini"),
    (r"grok", "grok"),
    (r"deepseek", "deepseek"),
    (r"qwen|qwq", "qwen"),
    (r"mistral|codestral|devstral|magistral|ministral", "mistral"),
    (r"kimi|moonshot", "moonshot"),
    (r"glm|zhipu", "zai"),
    (r"minimax", "minimax"),
    (r"sonar|perplexity", "perplexity"),
)

NOMES = {
    "claude": "Anthropic", "codex": "OpenAI", "openai": "OpenAI", "antigravity": "Google",
    "gemini": "Google", "opencode": "OpenCode", "copilot": "GitHub Copilot", "cursor": "Cursor",
    "grok": "xAI", "openrouter": "OpenRouter", "deepseek": "DeepSeek", "qwen": "Qwen",
    "mistral": "Mistral", "moonshot": "Moonshot AI", "zai": "Z.ai", "minimax": "MiniMax",
    "ollama": "Ollama", "groq": "Groq", "perplexity": "Perplexity", "fireworks": "Fireworks",
    "together": "Together AI",
}

_registrado = False


def registrar():
    """Inclui logos/ na busca de ícones do tema (uma vez, depois que há display)."""
    global _registrado
    if _registrado:
        return
    display = Gdk.Display.get_default()
    if display is None:
        return
    Gtk.IconTheme.get_for_display(display).add_search_path(str(LOGOS))
    _registrado = True


def nome_icone(marca):
    """Nome do ícone da marca, ou None se não há logo para ela."""
    if not marca:
        return None
    if (LOGOS / f"simba-ia-{marca}.svg").exists():
        return f"simba-ia-{marca}"
    if (LOGOS / f"simba-ia-{marca}-symbolic.svg").exists():
        return f"simba-ia-{marca}-symbolic"
    return None


def marca_modelo(modelo):
    """Marca de quem fornece o modelo: o provedor em 'provedor/modelo', senão quem o fez."""
    m = str(modelo or "").strip().lower()
    if not m:
        return None
    if "/" in m:
        provedor = m.split("/", 1)[0]
        if provedor in PROVEDOR_MARCA:
            return PROVEDOR_MARCA[provedor]
    for padrao, marca in MODELO_MARCA:
        if re.search(padrao, m):
            return marca
    return None


def marca_agente(agente, modelo=None):
    """Marca do agente; para agentes sem logo próprio (Crush, Pi), a do modelo."""
    return AGENTE_MARCA.get(agente) or marca_modelo(modelo)


def icone_agente(agente, modelo=None):
    return nome_icone(marca_agente(agente, modelo)) or GENERICO


def imagem(nome_ou_none, tamanho=16):
    registrar()
    img = Gtk.Image.new_from_icon_name(nome_ou_none or GENERICO)
    img.set_pixel_size(tamanho)
    return img
