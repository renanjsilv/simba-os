#!/usr/bin/env python3
"""Abre a janela do chat com uma resposta de exemplo (markdown rico) para conferir o visual.

    testes/agentes/vitrine.sh   → fotografa a janela sem abrir nada no seu desktop

VITRINE_FOTOS="1.5:/tmp/meio.png,5:/tmp/fim.png" (segundos:arquivo) e VITRINE_PAUSA
(segundos entre as linhas do agente falso) para ver a resposta no meio da geração.
VITRINE_TAM="1920x1000" (tamanho da janela), VITRINE_ANEXO=/img.png (anexa uma
imagem ao pedido), VITRINE_SO_COMPOR=1 (não envia: mostra o anexo no composer).
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
(home / ".config/agentes").mkdir(parents=True)
(home / ".config/agentes/config.json").write_text(json.dumps(
    {"ordem": ["claude"], "inativos": [], "trocaAutomatica": True, "esperar": 8, "modelos": {}, "seguro": False}))
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
M.montar_comando = lambda a, p, c, **k: [sys.executable, str(FALSO), str(AQUI / "fixtures/markdown-rico.sintetico.ndjson"), pausa]
M.candidatos = lambda c, pular=(), verificar=True, seguro=False: ["claude"]
M.esgotado_ate = lambda a: None


class Vitrine(A.App):
    def do_activate(self):
        w = A.MainWindow(self)
        w.unmaximize()
        larg, alt = (int(x) for x in os.environ.get("VITRINE_TAM", "1100x900").split("x"))
        w.set_default_size(larg, alt)
        w.present()

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
            return False
        if acao:
            GLib.timeout_add(2500, agir)

        def foto(caminho, tentativa=0):
            from gi.repository import Gtk
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
            elif tentativa < 20:  # no meio de um quadro o snapshot pode vir vazio
                GLib.timeout_add(30, foto, caminho, tentativa + 1)
            return False
        for i, (quando, caminho) in enumerate(FOTOS):
            GLib.timeout_add(int(quando * 1000), foto, caminho)
        GLib.timeout_add(int(float(os.environ.get("VITRINE_DURACAO", str(max(q for q, _ in FOTOS) + 1))) * 1000), lambda: self.quit())

    def do_command_line(self, cl):
        self.activate()
        return 0


Vitrine().run([sys.argv[0]])
