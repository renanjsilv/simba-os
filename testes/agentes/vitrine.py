#!/usr/bin/env python3
"""Abre a janela do chat com uma resposta de exemplo (markdown rico) para conferir o visual.

    testes/agentes/vitrine.sh   → fotografa a janela sem abrir nada no seu desktop

VITRINE_FOTOS="1.5:/tmp/meio.png,5:/tmp/fim.png" (segundos:arquivo) e VITRINE_PAUSA
(segundos entre as linhas do agente falso) para ver a resposta no meio da geração.
VITRINE_TAM="1920x1000" (tamanho da janela), VITRINE_ANEXO=/img.png (anexa uma
imagem ao pedido), VITRINE_SO_COMPOR=1 (não envia: mostra o anexo no composer).
VITRINE_TEMA=claro|escuro, VITRINE_FIXTURE=claude-ferramenta.ndjson (outra gravação),
VITRINE_SEGURO=1 (modo somente leitura), VITRINE_EXPANDIR=1 (abre o bloco "Pensando" e
os cartões), VITRINE_IMAGEM=/img.png (simula o agente lendo uma imagem),
VITRINE_REABRIR=1 (depois da resposta, recarrega a conversa salva),
VITRINE_SEM_ANIMACAO=1 (preferência do sistema de reduzir animações).
"""
import json
import os
from pathlib import Path
import sys
import tempfile

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1] / "pacotes/simba-apps/raiz/usr/share/simba-apps/agentes"
home = Path(tempfile.mkdtemp(prefix="agentes-vitrine-"))
os.environ["HOME"] = str(home)
os.environ["AGENTES_DEV"] = "1"
if os.environ.get("VITRINE_CONVERSAS"):  # VITRINE_CONVERSAS=1: algumas conversas salvas na barra
    import json as _json, time as _time
    _pasta = home / ".local/state/simba/agents/conversas"
    _pasta.mkdir(parents=True, exist_ok=True)
    for _i, (_tit, _ag, _dias) in enumerate([("Corrigir o login do GitHub", "claude", 0.1), ("Plano da ISO 0.1.5", "codex", 0.3),
            ("Por que o Wi-Fi cai?", "claude", 1.2), ("Tema escuro no Bazaar", "opencode", 3), ("Script de backup", "gemini", 12), ("Ideias para o Draco", "claude", 40)]):
        (_pasta / f"v{_i}.json").write_text(_json.dumps({"id": f"v{_i}", "titulo": _tit, "atualizada": _time.time() - _dias * 86400,
            "mensagens": [{"tipo": "user", "texto": _tit}, {"tipo": "assistant", "agente": _ag, "texto": "ok"}]}))
(home / ".config/agentes").mkdir(parents=True)
(home / ".config/agentes/config.json").write_text(json.dumps(
    {"ordem": ["claude"], "inativos": [], "trocaAutomatica": True, "esperar": 8, "modelos": {},
     "seguro": bool(os.environ.get("VITRINE_SEGURO"))}))
(home / "Work").mkdir()
sys.path.insert(0, str(RAIZ))
import motor as M  # noqa: E402
import app as A  # noqa: E402
from gi.repository import GLib  # noqa: E402

FALSO = home / "falso.py"
FALSO.write_text("import sys,time\nfor l in open(sys.argv[1]).read().splitlines():\n print(l,flush=True); time.sleep(float(sys.argv[2]))\n")
pausa = os.environ.get("VITRINE_PAUSA", "0.05")
# VITRINE_FOTOS="2.0:/tmp/a.png,6:/tmp/b.png" → fotos da janela nesses segundos
FOTOS = [(float(x.split(":", 1)[0]), x.split(":", 1)[1])
         for x in os.environ.get("VITRINE_FOTOS", "5:/tmp/vitrine.png").split(",") if ":" in x]
M.montar_comando = lambda a, p, c, **k: [sys.executable, str(FALSO), str(AQUI / "fixtures" / os.environ.get("VITRINE_FIXTURE", "markdown-rico.sintetico.ndjson")), pausa]
M.candidatos = lambda c, pular=(), verificar=True, seguro=False: ["claude"]
M.esgotado_ate = lambda a: None


class Vitrine(A.App):
    def do_activate(self):
        from gi.repository import Adw, Gtk
        tema = os.environ.get("VITRINE_TEMA")
        if tema:
            Adw.StyleManager.get_default().set_color_scheme(
                Adw.ColorScheme.FORCE_DARK if tema == "escuro" else Adw.ColorScheme.FORCE_LIGHT)
        if os.environ.get("VITRINE_SEM_ANIMACAO"):
            Gtk.Settings.get_default().set_property("gtk-enable-animations", False)
        w = A.MainWindow(self)
        w.unmaximize()
        larg, alt = (int(x) for x in os.environ.get("VITRINE_TAM", "1100x900").split("x"))
        w.set_default_size(larg, alt)
        w.present()
        if os.environ.get("VITRINE_DETALHES"):  # VITRINE_DETALHES=1: painel de detalhes encaixado (tela estreita)
            def detalhes():
                w.split_detalhes.set_collapsed(False)
                w.split_detalhes.set_show_sidebar(True)
                return False
            GLib.timeout_add(300, detalhes)
            GLib.timeout_add(3000, detalhes)

        def enviar():
            w.text_input_buf.set_text("Revise o app.py e me diga o que corrigir")
            # VITRINE_ANEXO=/caminho.png → manda o pedido com essa imagem anexada
            if os.environ.get("VITRINE_ANEXO"):
                w._adicionar_anexo(os.environ["VITRINE_ANEXO"])
            if os.environ.get("VITRINE_SO_COMPOR"):
                return False  # só mostra o composer com o anexo, sem enviar
            w._on_enviar()
            return False
        GLib.timeout_add(400, enviar)

        # VITRINE_ACAO="busca:termo" ou "painel" → executa depois da resposta
        acao = os.environ.get("VITRINE_ACAO", "")
        def agir():
            if acao.startswith("busca:"):
                w._abrir_busca()
                w.busca_entrada.set_text(acao[6:])
                w._buscar()
            elif acao == "painel":
                w._abrir_painel_uso()
            elif acao.startswith("agente"):  # "agente" = tela do principal; "agente:<id>" = de um subagente
                w.split_detalhes.set_show_sidebar(True)
                if w.ultimo_bloco is not None:
                    w._detalhes_bloco(w.ultimo_bloco, abrir=False)
                    alvo = acao.split(":", 1)[1] if ":" in acao else "principal"
                    if alvo == "1":   # o primeiro subagente que aparecer
                        alvo = next((c for c in w.detalhes._cartoes if c != "principal"), "principal")
                    w.detalhes.abrir_agente(alvo)
            elif acao == "pergunta":
                w._adicionar_pergunta("Posso apagar os 3 arquivos temporários em ~/Work/build?",
                                      ["Sim, pode apagar", "Não, mantenha", "Mostre a lista antes"], lambda r: None)
            elif acao == "lateral":
                w._mostrar_codigo_lateral("python", "def ler(fd):\n    dados = os.read(fd, 4096)\n    if not dados:\n        return None\n    return dados.decode('utf-8')\n", "leitor.py")
            elif acao == "lateral-busca":  # busca da barra de conversas aberta
                w.barra._alternar_busca(True)
                if os.environ.get("VITRINE_TERMO"):
                    w.barra.busca.set_text(os.environ["VITRINE_TERMO"])
            elif acao in ("uso", "seletor", "modelo"):
                import time as _tm
                w.janelas_uso["claude"] = {"5h": 0.62, "7d": 0.31}
                w.janelas_volta["claude"] = {"5h": _tm.time() + 2 * 3600 + 600, "7d": _tm.time() + 3 * 86400}
                w._atualizar_uso_ui()
                {"uso": w.lbl_uso, "seletor": w.dropdown, "modelo": w.modelo_dropdown}[acao].popup()
            return False
        if acao:
            GLib.timeout_add(2500, agir)

        def ler_imagem():
            # VITRINE_IMAGEM=/caminho.png → simula o agente lendo a imagem (prévia clicável)
            caminho = os.environ.get("VITRINE_IMAGEM")
            if not caminho or getattr(w, "_imagem_vitrine", False) or getattr(w, "ativo_bloco", None) is None:
                return
            w._imagem_vitrine = True
            w.ativo_bloco.passo({"id": "img-vitrine", "tipo": "leitura", "nome": "read",
                                 "entrada": {"arquivo": caminho}, "texto": f"Lendo: {Path(caminho).name}",
                                 "estado": "ok"})

        def expandir_tudo():
            import atividade
            from gi.repository import Gtk
            ler_imagem()
            pilha = [w]
            while pilha:
                x = pilha.pop()
                if isinstance(x, atividade.BlocoPensando):
                    x.expandir(True)
                elif isinstance(x, atividade.LinhaPasso):
                    x.abrir_saida()
                f = x.get_first_child()
                while f is not None:
                    pilha.append(f)
                    f = f.get_next_sibling()
            return False

        def foto(caminho, tentativa=0):
            from gi.repository import Gtk
            if os.environ.get("VITRINE_EXPANDIR") and tentativa == 0:
                expandir_tudo()
                GLib.timeout_add(120, expandir_tudo)
                GLib.timeout_add(1400, expandir_tudo)
                GLib.timeout_add(3000, foto, caminho, 1)
                return False
            if os.environ.get("VITRINE_TOPO") and tentativa == 0:  # VITRINE_TOPO=1: rola até o início
                w.seguir_fim = False
                w.scroller.get_vadjustment().set_value(0)
                GLib.timeout_add(150, foto, caminho, 1)
                return False
            larg, alt = w.get_width(), w.get_height()
            pintura = Gtk.WidgetPaintable.new(w)
            snap = Gtk.Snapshot()
            pintura.snapshot(snap, larg, alt)
            no = snap.to_node()
            if no is not None:
                w.get_native().get_renderer().render_texture(no, None).save_to_png(caminho)
                print("foto:", caminho, flush=True)
                if acao in ("uso", "seletor", "modelo"):
                    pop = {"uso": w.lbl_uso, "seletor": w.dropdown, "modelo": w.modelo_dropdown}[acao].get_popover()
                    pp = Gtk.WidgetPaintable.new(pop)
                    s2 = Gtk.Snapshot()
                    pp.snapshot(s2, pop.get_width(), pop.get_height())
                    n2 = s2.to_node()
                    if n2 is not None:
                        pop.get_native().get_renderer().render_texture(n2, None).save_to_png(caminho[:-4] + "-pop.png")
            elif tentativa < 20:  # no meio de um quadro o snapshot pode vir vazio
                GLib.timeout_add(30, foto, caminho, tentativa + 1)
            return False
        for i, (quando, caminho) in enumerate(FOTOS):
            GLib.timeout_add(int(quando * 1000), foto, caminho)
        # VITRINE_IMAGEM sem VITRINE_EXPANDIR: simula o agente lendo a imagem
        # durante a resposta (o bloco deve abrir sozinho com a miniatura)
        if os.environ.get("VITRINE_IMAGEM") and not os.environ.get("VITRINE_EXPANDIR"):
            GLib.timeout_add(
                int(float(os.environ.get("VITRINE_IMAGEM_QUANDO", "2")) * 1000),
                lambda: (ler_imagem(), False)[1])
        GLib.timeout_add(int(float(os.environ.get("VITRINE_DURACAO", str(max(q for q, _ in FOTOS) + 1))) * 1000), lambda: self.quit())

    def do_command_line(self, cl):
        self.activate()
        return 0


Vitrine().run([sys.argv[0]])
