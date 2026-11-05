# Simba OS

Distribuição baseada no Arch Linux, com Hyprland e uma área de trabalho no estilo do Windows 11:
barra de tarefas, Menu Iniciar, Configurações, Explorador de Arquivos, Gerenciador de Tarefas,
assistente de voz (Draco), backup no Google Drive, pontos de restauração e instalador próprio.
Português (Brasil) e inglês.

## Pacotes

| Pacote | O que tem | Fonte |
|---|---|---|
| `simba` | base: shell (barra, menus, notificações), scripts `simba-*`, temas, `/etc/skel`, tradução | `pacotes/simba/raiz` (derivado do [Omarchy](https://github.com/basecamp/omarchy), MIT) |
| `simba-apps` | Configurações, Menu Iniciar, Explorador, Gerenciador de Tarefas, Transcrever, Boas-vindas, Gerar ISO, Conta, módulos da barra, tela de bloqueio, idiomas, "Atualizar tudo" | `pacotes/simba-apps/raiz` |
| `simba-draco` | assistente de voz Draco (só o código; ambiente Python e vozes são preparados por usuário) | `pacotes/simba-draco/raiz` |
| `simba-keyring` | chave que assina os pacotes + seção `[simba-os]` no `pacman.conf` | `pacotes/simba-keyring` |

Cada `raiz/` espelha o sistema de arquivos instalado (`raiz/usr/bin/x` → `/usr/bin/x`).

## Fluxo de trabalho

```bash
# 1. edite em pacotes/<pacote>/raiz/…  (suba o pkgver/pkgrel do PKGBUILD a cada versão)
ferramentas/construir simba-apps          # gera dist/simba-apps-*.pkg.tar.zst
sudo pacman -U dist/simba-apps-*.pkg.tar.zst   # testa no seu computador
simba-apps-usuario                        # (uma vez por usuário) usa os apps do sistema

# 2. publica para todas as instalações
ferramentas/publicar                      # assina, gera o banco e envia ao GitHub Releases
```

As instalações recebem pelo **Atualizar tudo** (ou `sudo pacman -Syu`), porque o `simba-keyring`
adiciona ao `/etc/pacman.conf`:

```ini
[simba-os]
SigLevel = Required DatabaseRequired
Server = https://github.com/<usuário>/simba-os/releases/download/repo
```

Primeira vez: `ferramentas/criar-chave` (chave GPG que assina os pacotes; a privada fica só no
seu computador) e `gh auth login`.

## Idiomas

Textos dos apps próprios: catálogos em `pacotes/simba-apps/raiz/usr/share/simba-apps/idiomas/`
(o texto em português é a chave). Ver o `LEIA-ME.md` dessa pasta e as ferramentas `extrair.py`,
`marcar.py`, `marcar_py.py`, `conferir.py`.

## Licença

MIT — ver `LICENSE`. A parte derivada do Omarchy mantém o aviso original (`NOTICE`,
`LICENSES/omarchy-MIT.txt`).
