"""Operações de arquivo em segundo plano: copiar, mover, lixeira, excluir, compactar,
extrair — com progresso, cancelar, pergunta de conflito e desfazer (Ctrl+Z)."""
import os
import shutil
import stat
import subprocess
import threading
from pathlib import Path

from gi.repository import Gio, GLib, GObject

from utilidades import nome_livre, tamanho
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

BLOCO = 1024 * 1024


class Cancelado(Exception):
    pass


class Operacoes(GObject.Object):
    __gsignals__ = {
        # texto, fração (-1 = indeterminado)
        "progresso": (GObject.SignalFlags.RUN_FIRST, None, (str, float)),
        # mensagem final (vazia = nada a dizer), sucesso
        "terminou": (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
    }

    def __init__(self):
        super().__init__()
        self.ocupado = False
        self.cancelar = threading.Event()
        self.desfazer_pilha = []
        self.perguntar = None   # fn(nome_destino) -> "substituir" | "ambos" | "pular" (laço do GTK)

    # ── execução ───────────────────────────────────────────────────────────
    def _rodar(self, titulo, fn, *args):
        if self.ocupado:
            self.emit("terminou", _t("Aguarde a operação em andamento terminar"), False)
            return
        self.ocupado = True
        self.cancelar.clear()
        self.emit("progresso", titulo, -1)

        def corpo():
            msg, ok = "", True
            try:
                msg = fn(*args) or ""
            except Cancelado:
                msg, ok = _t("Operação cancelada"), False
            except Exception as e:  # noqa: BLE001
                msg, ok = _t("Erro: %1", e), False
            GLib.idle_add(self._fim, msg, ok)
        threading.Thread(target=corpo, daemon=True).start()

    def _fim(self, msg, ok):
        self.ocupado = False
        self.emit("terminou", msg, ok)
        return False

    def _prog(self, texto, frac):
        GLib.idle_add(lambda: (self.emit("progresso", texto, frac), False)[1])

    def _pergunta(self, nome):
        if not self.perguntar:
            return "ambos"
        ev, r = threading.Event(), {}

        def no_gtk():
            def resposta(x):
                r["x"] = x
                ev.set()
            self.perguntar(nome, resposta)
            return False
        GLib.idle_add(no_gtk)
        ev.wait()
        return r.get("x", "pular")

    # ── copiar / mover ─────────────────────────────────────────────────────
    def copiar(self, origens, destino):
        self._rodar(_t("Copiando…"), self._transferir, list(origens), destino, False)

    def mover(self, origens, destino):
        self._rodar(_t("Movendo…"), self._transferir, list(origens), destino, True)

    def _total(self, caminhos):
        t = 0
        for p in caminhos:
            try:
                if os.path.isdir(p) and not os.path.islink(p):
                    for raiz, _, arqs in os.walk(p):
                        for a in arqs:
                            try:
                                t += os.lstat(os.path.join(raiz, a)).st_size
                            except OSError:
                                pass
                else:
                    t += os.lstat(p).st_size
            except OSError:
                pass
        return max(t, 1)

    def _transferir(self, origens, destino, mover):
        destino = str(destino)
        politica = None          # resposta de conflito vale para todos
        feitos = []              # (novo, antigo) para desfazer
        total = self._total(origens)
        estado = {"feito": 0}
        verbo = _t("Movendo") if mover else _t("Copiando")

        def avancar(n, nome):
            if self.cancelar.is_set():
                raise Cancelado()
            estado["feito"] += n
            self._prog(f"{verbo} “{nome}” · {tamanho(estado['feito'])} de {tamanho(total)}",
                       min(1.0, estado["feito"] / total))

        for orig in origens:
            orig = str(orig).rstrip("/") or "/"
            nome = os.path.basename(orig)
            alvo = Path(destino) / nome
            if os.path.abspath(orig) == os.path.abspath(str(alvo)):
                if mover:
                    continue
                alvo = nome_livre(destino, nome)          # colar na mesma pasta: "nome (2)"
            elif str(alvo).startswith(orig + "/"):
                raise OSError(_t("não dá para colocar “%1” dentro dela mesma", nome))
            elif alvo.exists() or alvo.is_symlink():
                r = politica or self._pergunta(nome)
                if r.endswith("-todos"):
                    politica = r = r[:-6]
                if r == "pular":
                    continue
                if r == "ambos":
                    alvo = nome_livre(destino, nome)
                else:  # substituir
                    if alvo.is_dir() and not alvo.is_symlink():
                        shutil.rmtree(alvo)
                    else:
                        alvo.unlink()
            if mover:
                try:
                    os.rename(orig, alvo)                 # mesmo disco: instantâneo
                    avancar(self._total([str(alvo)]), nome)
                    feitos.append((str(alvo), orig))
                    continue
                except OSError:
                    pass
            self._copiar_item(orig, str(alvo), avancar)
            if mover:
                if os.path.isdir(orig) and not os.path.islink(orig):
                    shutil.rmtree(orig)
                else:
                    os.unlink(orig)
            feitos.append((str(alvo), orig))
        if feitos:
            self.desfazer_pilha.append(("mover" if mover else "copiar", feitos))
        n = len(feitos)
        return f"{n} {'item' if n == 1 else 'itens'} {'movido' if mover else 'copiado'}{'' if n == 1 else 's'}" if n else ""

    def _copiar_item(self, orig, alvo, avancar):
        if os.path.islink(orig):
            os.symlink(os.readlink(orig), alvo)
            return
        if os.path.isdir(orig):
            os.makedirs(alvo, exist_ok=True)
            for e in os.scandir(orig):
                self._copiar_item(e.path, os.path.join(alvo, e.name), avancar)
            shutil.copystat(orig, alvo, follow_symlinks=False)
            return
        nome = os.path.basename(orig)
        with open(orig, "rb") as fi, open(alvo, "wb") as fo:
            while True:
                b = fi.read(BLOCO)
                if not b:
                    break
                fo.write(b)
                avancar(len(b), nome)
        try:
            shutil.copystat(orig, alvo)
        except OSError:
            pass

    # ── lixeira / excluir ──────────────────────────────────────────────────
    def lixeira(self, caminhos):
        self._rodar(_t("Movendo para a Lixeira…"), self._lixeira, list(caminhos))

    def _lixeira(self, caminhos):
        feitos = []
        for i, p in enumerate(caminhos):
            if self.cancelar.is_set():
                raise Cancelado()
            self._prog(_t("Movendo para a Lixeira: %1", os.path.basename(p)), i / max(1, len(caminhos)))
            Gio.File.new_for_path(p).trash(None)
            feitos.append(p)
        self.desfazer_pilha.append(("lixeira", feitos))
        n = len(feitos)
        return _t("%1 %2 para a Lixeira", n, 'item movido' if n == 1 else 'itens movidos')

    def excluir(self, arquivos):
        """Excluir de vez: caminhos locais ou URIs (trash:///...)."""
        self._rodar(_t("Excluindo…"), self._excluir, list(arquivos))

    def _excluir(self, arquivos):
        for i, a in enumerate(arquivos):
            if self.cancelar.is_set():
                raise Cancelado()
            self._prog(_t("Excluindo %1", os.path.basename(str(a).rstrip('/'))), i / max(1, len(arquivos)))
            if "://" in str(a):
                self._apagar_gio(Gio.File.new_for_uri(a))
            elif os.path.isdir(a) and not os.path.islink(a):
                shutil.rmtree(a)
            else:
                os.unlink(a)
        n = len(arquivos)
        return f"{n} {'item excluído' if n == 1 else 'itens excluídos'} permanentemente"

    def _apagar_gio(self, f):
        try:
            if f.query_file_type(Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None) == Gio.FileType.DIRECTORY:
                for i in f.enumerate_children("standard::name", Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None):
                    self._apagar_gio(f.get_child(i.get_name()))
        except GLib.Error:
            pass
        f.delete(None)

    def esvaziar_lixeira(self):
        def corpo():
            lix = Gio.File.new_for_uri("trash:///")
            n = 0
            for i in lix.enumerate_children("standard::name", Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None):
                self._apagar_gio(lix.get_child(i.get_name()))
                n += 1
            return _t("Lixeira esvaziada (%1 %2)", n, 'item' if n == 1 else 'itens')
        self._rodar(_t("Esvaziando a Lixeira…"), corpo)

    def restaurar(self, uris):
        """Itens da Lixeira (trash:///...) de volta ao lugar de origem."""
        def corpo():
            n = 0
            for u in uris:
                f = Gio.File.new_for_uri(u)
                info = f.query_info("trash::orig-path", Gio.FileQueryInfoFlags.NONE, None)
                orig = info.get_attribute_byte_string("trash::orig-path")
                if not orig:
                    continue
                os.makedirs(os.path.dirname(orig), exist_ok=True)
                alvo = nome_livre(os.path.dirname(orig), os.path.basename(orig))
                f.move(Gio.File.new_for_path(str(alvo)), Gio.FileCopyFlags.NONE, None, None, None)
                n += 1
            return f"{n} {'item restaurado' if n == 1 else 'itens restaurados'}"
        self._rodar(_t("Restaurando…"), corpo)

    # ── compactar / extrair ────────────────────────────────────────────────
    def compactar(self, caminhos, destino_zip):
        def corpo():
            base = os.path.dirname(caminhos[0])
            nomes = [os.path.relpath(p, base) for p in caminhos]
            p = subprocess.Popen(["zip", "-r", "-q", "-y", str(destino_zip), "--", *nomes], cwd=base)
            while p.poll() is None:
                if self.cancelar.wait(0.2):
                    p.terminate()
                    Path(destino_zip).unlink(missing_ok=True)
                    raise Cancelado()
            if p.returncode != 0:
                raise OSError(_t("o zip falhou"))
            self.desfazer_pilha.append(("criar", [str(destino_zip)]))
            return _t("Compactado em %1", os.path.basename(str(destino_zip)))
        self._rodar(_t("Compactando…"), corpo)

    def extrair(self, arquivo, pasta_destino):
        def corpo():
            os.makedirs(pasta_destino, exist_ok=True)
            p = subprocess.Popen(["bsdtar", "-xf", arquivo, "-C", str(pasta_destino)],
                                 stderr=subprocess.PIPE, text=True)
            while p.poll() is None:
                if self.cancelar.wait(0.2):
                    p.terminate()
                    raise Cancelado()
            if p.returncode != 0:
                raise OSError((p.stderr.read() or _t("não foi possível extrair")).strip()[:200])
            self.desfazer_pilha.append(("criar", [str(pasta_destino)]))
            return _t("Extraído em %1", os.path.basename(str(pasta_destino)))
        self._rodar(_t("Extraindo…"), corpo)

    # ── criar / renomear (rápidos, no laço do GTK) ─────────────────────────
    def nova_pasta(self, pasta, nome=_t("Nova pasta")):
        alvo = nome_livre(pasta, nome)
        os.makedirs(alvo)
        self.desfazer_pilha.append(("criar", [str(alvo)]))
        return str(alvo)

    def novo_arquivo(self, pasta, nome, conteudo=b""):
        alvo = nome_livre(pasta, nome)
        Path(alvo).write_bytes(conteudo)
        self.desfazer_pilha.append(("criar", [str(alvo)]))
        return str(alvo)

    def renomear(self, caminho, novo_nome):
        alvo = os.path.join(os.path.dirname(caminho), novo_nome)
        if os.path.exists(alvo) and os.path.abspath(alvo) != os.path.abspath(caminho):
            raise OSError(_t("já existe “%1” nesta pasta", novo_nome))
        os.rename(caminho, alvo)
        self.desfazer_pilha.append(("renomear", [(alvo, caminho)]))
        return alvo

    # ── desfazer ───────────────────────────────────────────────────────────
    def desfazer(self):
        if not self.desfazer_pilha:
            self.emit("terminou", _t("Nada para desfazer"), False)
            return
        tipo, dados = self.desfazer_pilha.pop()

        def corpo():
            if tipo in ("mover", "renomear"):
                for novo, antigo in reversed(dados):
                    if os.path.exists(novo) and not os.path.exists(antigo):
                        try:
                            os.rename(novo, antigo)
                        except OSError:
                            shutil.move(novo, antigo)
            elif tipo in ("copiar", "criar"):
                for p in dados:
                    p = p[0] if isinstance(p, tuple) else p
                    if os.path.exists(p) or os.path.islink(p):
                        Gio.File.new_for_path(p).trash(None)
            elif tipo == "lixeira":
                lix = Gio.File.new_for_uri("trash:///")
                quero = set(dados)
                for i in lix.enumerate_children("standard::name,trash::orig-path,trash::deletion-date",
                                                Gio.FileQueryInfoFlags.NONE, None):
                    orig = i.get_attribute_byte_string("trash::orig-path")
                    if orig in quero:
                        lix.get_child(i.get_name()).move(Gio.File.new_for_path(orig), Gio.FileCopyFlags.NONE, None, None, None)
                        quero.discard(orig)
            return _t("Desfeito")
        self._rodar(_t("Desfazendo…"), corpo)


def modo_texto(m):
    """0o755 → 'rwxr-xr-x'"""
    return stat.filemode(m)[1:]
