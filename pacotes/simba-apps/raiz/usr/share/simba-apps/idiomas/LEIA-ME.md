# Idiomas dos componentes próprios do Simba OS

O texto em **português** escrito no código é a chave. Cada idioma tem um catálogo
`<idioma>.json` com `{"texto em português": "tradução"}`. Português não precisa de catálogo.

Qual catálogo vale: `SIMBA_IDIOMA` (para testes) ou o `LANG`/`LC_MESSAGES` da sessão.
`en_US.UTF-8` procura `en_US.json` e depois `en.json`. Sem catálogo/sem a frase → português.

Como marcar texto de interface no código:
- QML (app Configurações):        `I18n.t("Texto")`            (singleton em qs.Comum)
- QML (barra, outros shells):     `import "idiomas"` (link para /usr/share/simba-apps/idiomas/qml) + `I18n.t("Texto")`
- Python:                         `from simba_i18n import t`   (sys.path += esta pasta)
- Bash:                           `simba-t "Texto"`
- .desktop:                       `Name=` em inglês + `Name[pt_BR]=` em português (padrão freedesktop)

Espaços nas pontas não fazem parte da chave: `I18n.t(" de ")` usa a entrada "de".

Chaves internas (dicionário indexado pelo rótulo, status comparado depois): guarde em português e
traduza só ao exibir — Python `_n("Rótulo")` marca para o catálogo sem traduzir; exiba com `_t(rotulo)`.
Números: `.replace(".", I18n.decimal)` (QML) / `.replace(".", DECIMAL)` (Python). Datas: `Qt.locale()`.

Ferramentas (`ferramentas/`):
- `extrair.py`             lista todas as frases marcadas e, para cada catálogo, as que faltam
                           (`extrair.py --faltando en`); `--json` gera o esqueleto de um idioma novo.
- `marcar.py ARQUIVOS...`     marca os textos em português de arquivos QML/JS com I18n.t(...)
- `marcar_py.py ARQUIVOS...`  idem para Python (_t; f-strings viram _t("… %1 …", x)); --ver = só listar
- `conferir.py ARQUIVOS...`   texto marcado que também aparece SEM marca no arquivo (comparação/chave):
                              em outro idioma a comparação falharia — revisar cada achado
- `sobras.py ARQUIVOS...`     literais que parecem português e não foram marcados
Sempre revise o que os marcadores fizeram: comandos, nomes de pasta/arquivo, ids e formatos não se traduzem.

Idioma novo (ex.: espanhol): `ferramentas/extrair.py --novo es > es.json`, traduzir os valores,
e pronto — vale na próxima vez que o app abrir numa sessão com LANG=es_*.
