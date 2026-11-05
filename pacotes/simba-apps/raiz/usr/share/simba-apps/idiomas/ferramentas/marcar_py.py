#!/usr/bin/env python3
"""marcar_py.py — marca os textos de interface em português de arquivos Python com _t(...).

    marcar_py.py [--ver] ARQUIVOS...

- "texto"            → _t("texto")
- f"Abrir {n} itens" → _t("Abrir %1 itens", n)
Pula docstrings, comparações, chaves de dict, índices, argumentos de subprocess/os/re/json/
caminhos, kwargs técnicos (css_classes, icon_name…) e o que já está marcado. Acrescenta o
import de simba_i18n depois dos imports do arquivo. Cópia em <arquivo>.bak-i18n.
"""
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marcar import eh_texto  # noqa: E402

UI_KW = {"label", "title", "text", "tooltip_text", "placeholder_text", "subtitle", "body", "heading",
         "secondary_text", "description", "texto", "titulo", "descricao", "rotulo", "mensagem", "detalhe",
         "dica", "accept_label", "cancel_label", "message", "summary"}
NAO_UI_KW = {"css_classes", "css_class", "icon_name", "name", "action_name", "mime_type", "application_id",
             "cwd", "env", "encoding", "errors", "mode", "sep", "end", "file", "key", "default", "dest",
             "metavar", "choices", "type", "detailed_action", "id", "valor", "chave", "tipo", "cmd", "glifo",
             "family", "font", "halign", "valign", "orientation", "propriedade", "prop", "categoria", "pasta"}
CHAMADA_TECNICA = re.compile(
    r"^(subprocess\.\w+|run|Popen|check_output|check_call|call|sh|rodar|os\.\w+(\.\w+)*|shutil\.\w+|"
    r"open|Path|re\.\w+|json\.\w+|getattr|setattr|hasattr|isinstance|logging\.\w+|log\.\w+|"
    r"Gio\.\w+(\.\w+)*|GLib\.\w+|Gdk\.\w+|Gtk\.CssProvider|.*\.(startswith|endswith|split|rsplit|replace|"
    r"join|strip|lstrip|rstrip|get|setdefault|pop|index|find|count|encode|decode|format|add_css_class|"
    r"remove_css_class|set_css_classes|set_icon_name|set_from_icon_name|lookup_action|add_action|"
    r"set_accels_for_action|get_value|set_value|connect|emit|set_name|set_property|get_property|"
    r"set_detailed_action_name|set_action_name|activate_action|new_from_icon_name|load_from_string|"
    r"load_from_data|__getitem__|endswith|match|sub|search|fullmatch|compile|exists|is_file|is_dir|"
    r"glob|rglob|with_suffix|joinpath|read_text|write_text|mkdir|unlink|rename|write|environ\.get|"
    r"require_version|getenv|which|parse_args|add_argument|add_parser|add_subparsers|set_defaults))$")


# comandos de shell, cabeçalhos HTTP, blocos de configuração
TECNICO_TXT = re.compile(r"^(sudo|flatpak|pacman|yay|rclone|git|systemctl|Bearer|Basic) |\|\||&&|\$\(|\n\[|^\s*\w+ = |\n\w+ = ")


def nome_chamada(f):
    try:
        return ast.unparse(f)
    except Exception:
        return ""


def pais(arv):
    p = {}
    for n in ast.walk(arv):
        for c in ast.iter_child_nodes(n):
            p[c] = n
    return p


def tecnico(no, pai):
    """O literal está em contexto técnico (não é texto de interface)?"""
    filho, n = no, pai.get(no)
    while n is not None:
        if isinstance(n, ast.Expr) and isinstance(filho, (ast.Constant, ast.JoinedStr)):
            return True                                           # docstring / statement solto
        if isinstance(n, ast.Compare):
            return True
        if isinstance(n, ast.Dict) and filho in n.keys:
            return True
        if isinstance(n, ast.Subscript) and filho is n.slice:
            return True
        if isinstance(n, ast.keyword):
            if n.arg in NAO_UI_KW: return True
            if n.arg in UI_KW: return False
        if isinstance(n, ast.Call):
            if n.func is filho: return True
            nome = nome_chamada(n.func)
            if nome in ("_t", "t"): return True                   # já marcado
            if CHAMADA_TECNICA.match(nome): return True
            return False                                          # argumento de chamada comum: decide pelo texto
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.Return, ast.FunctionDef, ast.Lambda,
                          ast.IfExp, ast.BoolOp)) and not isinstance(n, (ast.IfExp, ast.BoolOp)):
            return False
        if isinstance(n, (ast.List, ast.Tuple, ast.Set)) and isinstance(pai.get(n), ast.Call) \
                and CHAMADA_TECNICA.match(nome_chamada(pai[n].func)):
            return True                                           # lista de comando
        filho, n = n, pai.get(n)
    return False


def offsets(src):
    ini = [0]
    for l in src.splitlines(keepends=True):
        ini.append(ini[-1] + len(l))
    return ini


def processar(caminho, ver):
    src = open(caminho, encoding="utf-8").read()
    try:
        arv = ast.parse(src)
    except SyntaxError as e:
        print(f"# {caminho}: {e}", file=sys.stderr); return 0
    pai = pais(arv)
    lin = offsets(src)
    # posições em bytes→caracteres: ast usa offsets UTF-8 por linha
    def pos(l, c):
        linha = src[lin[l - 1]:lin[l]] if l < len(lin) else ""
        return lin[l - 1] + len(linha.encode("utf-8")[:c].decode("utf-8", "replace"))
    dentro_fstring = set()
    for n in ast.walk(arv):
        if isinstance(n, ast.JoinedStr):
            for c in ast.walk(n):
                if c is not n: dentro_fstring.add(c)
    trocas = []
    for n in ast.walk(arv):
        if n in dentro_fstring:
            continue
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if "\n" in n.value and re.search(r"[{};]|--\w|^\s*[#\w-]+\s*[:=]", n.value, re.M):
                continue                                              # CSS/código/config em bloco
            if re.match(r"^\*|.*\*/", n.value) or TECNICO_TXT.search(n.value):
                continue                                              # padrão glob
            dono = pai.get(n)
            if isinstance(dono, ast.Assign) and any(isinstance(a, ast.Name) and re.search(
                    r"(^|_)(PASTA|NOME|REMOTO|DIR|PATH|CAMINHO|ARQ\w*|ID|APP\w*|URL|SERVICO|UNIDADE)$", a.id)
                    for a in dono.targets):
                continue                                              # constante técnica (nome de pasta etc.)
            if not n.value.strip() or tecnico(n, pai) or not eh_texto(n.value):
                continue
            a, b = pos(n.lineno, n.col_offset), pos(n.end_lineno, n.end_col_offset)
            trocas.append((a, b, f"_t({src[a:b]})", n.value))
        elif isinstance(n, ast.JoinedStr):
            if tecnico(n, pai):
                continue
            modelo, args = "", []
            ok = True
            for v in n.values:
                if isinstance(v, ast.Constant):
                    modelo += str(v.value).replace("%", "%%") if False else str(v.value)
                elif isinstance(v, ast.FormattedValue):
                    exp = ast.get_source_segment(src, v.value)
                    if exp is None: ok = False; break
                    if v.conversion == 114: exp = f"repr({exp})"
                    elif v.conversion == 115: exp = f"str({exp})"
                    if v.format_spec is not None:
                        spec = "".join(str(x.value) for x in v.format_spec.values if isinstance(x, ast.Constant))
                        exp = f"format({exp}, {json.dumps(spec)})"
                    args.append(exp)
                    modelo += f"%{len(args)}"
            if TECNICO_TXT.search(modelo):
                continue
            texto_puro = re.sub(r"%\d+", " ", modelo)
            if not ok or not eh_texto(texto_puro) or len(re.findall(r"[A-Za-zÀ-ÿ]", texto_puro)) < 3:
                continue
            a, b = pos(n.lineno, n.col_offset), pos(n.end_lineno, n.end_col_offset)
            trocas.append((a, b, f"_t({json.dumps(modelo, ensure_ascii=False)}" + "".join(", " + x for x in args) + ")", modelo))
    trocas.sort()
    # descarta sobreposições (fica a de fora)
    finais, fim = [], -1
    for t in trocas:
        if t[0] >= fim:
            finais.append(t); fim = t[1]
    if ver:
        for a, b, novo, txt in finais:
            print(f"{caminho}:{src.count(chr(10), 0, a) + 1}\t{novo[:140]}")
        return len(finais)
    if not finais:
        return 0
    out, p = [], 0
    for a, b, novo, _ in finais:
        out.append(src[p:a]); out.append(novo); p = b
    out.append(src[p:])
    novo_src = "".join(out)
    if "from simba_i18n import" not in novo_src:
        ultimo = 0
        for no in arv.body:
            if isinstance(no, (ast.Import, ast.ImportFrom)) or (isinstance(no, ast.Expr) and no is arv.body[0]):
                ultimo = no.end_lineno
            elif ultimo:
                break
        linhas = novo_src.split("\n")
        linhas.insert(ultimo, 'import sys as _sys, os as _os  # noqa: E401\n'
                              '_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))\n'
                              'from simba_i18n import t as _t  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)')
        novo_src = "\n".join(linhas)
    compile(novo_src, caminho, "exec")
    open(caminho + ".bak-i18n", "w", encoding="utf-8").write(src)
    open(caminho, "w", encoding="utf-8").write(novo_src)
    return len(finais)


if __name__ == "__main__":
    ver = "--ver" in sys.argv
    arqs = [a for a in sys.argv[1:] if a != "--ver"]
    total = sum(processar(a, ver) for a in arqs)
    print(f"# {total} textos {'encontrados' if ver else 'marcados'}", file=sys.stderr)
