#!/usr/bin/env python3
"""marcar.py — envolve com I18n.t(...) os textos de interface em português de arquivos QML/JS.

    marcar.py [--ver] [--funcao I18n.t] ARQUIVOS...

--ver   só lista o que seria marcado (arquivo:linha  "texto"), sem gravar.
Grava com cópia <arquivo>.bak-i18n. Não toca em: comandos (Sistema.sh/solto/rodar/json,
execDetached, command:, cmd:), comparações, chaves de objeto, ids/valores, caminhos,
URLs, cores, glifos e o que já estiver marcado. Sempre revise o resultado.
"""
import re
import sys

UI_PROPS = r"(text|titulo|subtitulo|descricao|detalhe|texto|rotulo|dica|placeholderText|tooltipText|label|title|" \
           r"confirmText|mensagem|aviso|legenda|nome|rotuloLongo|ajuda|vazio|textoVazio|explicacao|pergunta|" \
           r"tituloConfirmar|textoBotao|botao|resumo|nota|sub)"
NAO_UI_PROPS = r"(id|valor|chave|glifo|g|cmd|tipo|icone|source|path|color|cor|fonte|family|moduleName|objectName|" \
               r"kind|acao|modo|estilo|app|appId|classe|url|link|key|value|target|pagina|pg|categoria|arquivo|" \
               r"comando|exec|desktop|mime|prop|campo|ordem|chaveBusca|sinal|evento|dispositivo|layout|variante|tema)"
COMANDO = re.compile(r"(Sistema\.(sh|solto|soltoSh|rodar|json|hypr)|\.soltoSh|execDetached|Qt\.openUrlExternally|"
                     r"Hypr\.(definir|valor|eval|aplicar|setar|ler|keyword)\w*|\bhypr\(|console\.\w+|"
                     r"Preferencias\.\w+|\.(indexOf|startsWith|endsWith|includes|test|match|split|replace|join|"
                     r"lastIndexOf|search|exec|get|set|has|remove|arg)|JSON\.parse|new RegExp|require|"
                     r"Quickshell\.env|Qt\.(formatDateTime|formatDate|formatTime|locale|resolvedUrl|font|rgba|color|"
                     r"darker|lighter|tint)|\.toString)\s*\(")
COMANDO_PROP = re.compile(r"\b(command|cmd|comando|exec)\s*:")


def literais(src):
    """(início, fim, aspas, conteúdo) de cada string, pulando comentários e regex."""
    i, n = 0, len(src)
    ant = ""  # último caractere significativo (para distinguir regex de divisão)
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            i = src.find("\n", i)
            i = n if i < 0 else i
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/" and ant in "(,=:[!&|?{};+-*%<>~^\n" :
            # literal regex: /.../flags
            j, classe = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2; continue
                if src[j] == "[": classe = True
                elif src[j] == "]": classe = False
                elif src[j] == "/" and not classe: break
                j += 1
            if j < n and src[j] == "/":
                i = j + 1
                while i < n and src[i].isalpha(): i += 1
                ant = "x"
                continue
        if c in "\"'`":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\": j += 1
                elif src[j] == "\n" and c != "`": break
                j += 1
            yield i, j + 1, c, src[i + 1:j]
            i = j + 1
            ant = "x"
            continue
        if not c.isspace() or c == "\n":
            ant = c
        i += 1


def eh_texto(s):
    if not re.search(r"[A-Za-zÀ-ÿ]{2}", s): return False
    if "\\u" in s or "\\x" in s: return False
    nucleo = s.strip()
    if re.match(r"^(https?|file|qrc|image)://", nucleo): return False
    if re.match(r"^[#/~$.-]", nucleo) and not re.match(r"^\.\.\.|^…", nucleo): return False
    if re.search(r"\.(qml|js|json|png|svg|jpg|desktop|sh|py|conf|toml|lua|css)\b", nucleo): return False
    if re.fullmatch(r"[A-Za-z0-9_.:/+=\-@%*]+", nucleo) and not re.search(r"[A-Z]", nucleo[:1]): return False   # identificador
    if re.fullmatch(r"[A-Z0-9_]+", nucleo): return False                       # CONSTANTE / sigla
    if re.fullmatch(r"(d{1,4}|M{1,4}|y{2,4}|H{1,2}|h{1,2}|m{1,2}|s{1,2}|ap|AP|[ :/.,-])+", nucleo): return False  # formato de data
    if re.fullmatch(r"[A-Z][a-zA-Z]+(\.[A-Za-z]+)+", nucleo): return False    # Qualified.Name
    return bool(re.search(r"[ À-ÿ]", nucleo) or nucleo[:1].isupper())


SEM_STR = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|//[^\n]*')


def aberto(txt):
    """txt começa num '(': ele continua aberto até o fim de txt?"""
    prof = 0
    for ch in SEM_STR.sub("", txt):
        if ch in "([{": prof += 1
        elif ch in ")]}":
            prof -= 1
            if prof == 0: return False
    return prof > 0


def balanco(txt):
    txt = SEM_STR.sub("", txt)
    return sum(txt.count(a) for a in "([{") - sum(txt.count(b) for b in ")]}")


def decidir(src, ini, fim, conteudo, funcao):
    linha_ini = src.rfind("\n", 0, ini) + 1
    linha = src[linha_ini:src.find("\n", ini) if src.find("\n", ini) >= 0 else len(src)]
    if re.match(r"\s*(import|pragma|\.pragma|\.import|//@)", linha): return False
    antes = src[max(0, ini - 600):ini]
    depois = src[fim:fim + 40]
    if antes.endswith(funcao + "(") or re.search(r"I18n\.[tf]\(\s*$", antes): return False
    if re.search(r"(===|!==|==|!=|\bcase)\s*$", antes) or re.match(r"\s*(===|!==|==|!=)", depois): return False
    if re.match(r"\s*:", depois) and re.search(r"[{,]\s*$", antes): return False          # chave de objeto
    if re.match(r"\s*\]", depois) and re.search(r"\[\s*$", antes): pass
    # dentro de chamada de comando ainda aberta
    for m in COMANDO.finditer(antes):
        dentro = antes[m.end() - 1:]
        # callback (function/=>) dentro do comando: lá volta a ser código de interface
        if aberto(dentro) and not re.search(r"\bfunction\b|=>", SEM_STR.sub("", dentro)):
            return False
    resto_linha = antes[antes.rfind("\n") + 1:]
    m = None
    for m in COMANDO_PROP.finditer(resto_linha):
        pass
    if m and ";" not in resto_linha[m.end():]: return False
    # listas de ids: categorias freedesktop (chaves: [...]) e ids de .desktop
    if re.search(r"\b(chaves|categorias|categories|fixadosPadrao|padrao|apps|ids)\s*:\s*\[[^\]]*$", resto_linha): return False
    if re.search(r'"(org|com|io|dev)\.[\w.-]+"', linha) and not re.search(r"\b(titulo|rotulo|texto|text|descricao)\s*:", linha): return False
    # propriedade imediatamente antes (prop: "texto")
    p = re.search(r"\b([A-Za-z_.]+)\s*:\s*$", antes)
    if p:
        nome = p.group(1).split(".")[-1]
        if re.fullmatch(NAO_UI_PROPS, nome): return False
        if re.fullmatch(UI_PROPS, nome) and re.search(r"[A-Za-zÀ-ÿ]{2}", conteudo) and "\\u" not in conteudo \
                and not re.match(r"^\s*[#/~$]", conteudo):
            return True
    return eh_texto(conteudo)


def processar(caminho, ver, funcao):
    src = open(caminho, encoding="utf-8").read()
    trocas = []
    for ini, fim, aspas, conteudo in literais(src):
        if aspas == "`" or not conteudo.strip(): continue
        if '"' in conteudo or "hl." in conteudo or "address:" in conteudo: continue      # código Lua/Hyprland
        if re.match(r"^[a-z][a-z-]+: ", conteudo): continue                              # tags de log
        if re.search(r"Nerd Font|^JetBrains", conteudo): continue                          # fontes
        if decidir(src, ini, fim, conteudo, funcao):
            trocas.append((ini, fim, conteudo))
    if ver:
        for ini, fim, conteudo in trocas:
            print(f"{caminho}:{src.count(chr(10), 0, ini) + 1}\t{src[ini:fim]}")
        return len(trocas)
    if not trocas: return 0
    novo, pos = [], 0
    for ini, fim, _ in trocas:
        novo.append(src[pos:ini]); novo.append(f"{funcao}({src[ini:fim]})"); pos = fim
    novo.append(src[pos:])
    open(caminho + ".bak-i18n", "w", encoding="utf-8").write(src)
    open(caminho, "w", encoding="utf-8").write("".join(novo))
    return len(trocas)


if __name__ == "__main__":
    args = sys.argv[1:]
    ver = "--ver" in args
    funcao = "I18n.t"
    if "--funcao" in args:
        k = args.index("--funcao"); funcao = args[k + 1]; del args[k:k + 2]
    args = [a for a in args if a != "--ver"]
    total = sum(processar(a, ver, funcao) for a in args)
    print(f"# {total} textos {'encontrados' if ver else 'marcados'}", file=sys.stderr)
