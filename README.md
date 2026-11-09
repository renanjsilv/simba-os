<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/imagens/banner-escuro.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/imagens/banner-claro.png">
  <img alt="Simba OS — o gatinho Simba e o nome do sistema" src="docs/imagens/banner-escuro.png" width="820">
</picture>

<br><br>

**Uma distribuição baseada no Arch Linux, com Hyprland e uma área de trabalho familiar:**<br>
barra de tarefas, Menu Iniciar, Configurações e apps próprios, tudo em português.

<br>

[![Arch Linux](https://img.shields.io/badge/base-Arch%20Linux-1793D1?style=for-the-badge&logo=archlinux&logoColor=white)](https://archlinux.org)
[![Hyprland](https://img.shields.io/badge/Hyprland-Wayland-58E1FF?style=for-the-badge&logo=wayland&logoColor=white)](https://hyprland.org)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-a6d189?style=for-the-badge)](LICENSE)
[![Idiomas](https://img.shields.io/badge/idiomas-pt--BR%20%C2%B7%20en-f5a97f?style=for-the-badge)](#-idiomas)

[Destaques](#-destaques) ·
[Apps](#-apps-do-simba) ·
[Instalação](#-instalação) ·
[Papéis de parede](#%EF%B8%8F-papéis-de-parede) ·
[Desenvolvimento](#%EF%B8%8F-desenvolvimento) ·
[Licença](#-licença)

</div>

---

## ✨ Destaques

<table>
<tr>
<td width="50%" valign="top">

### 🪟 Área de trabalho familiar
Barra de tarefas, **Menu Iniciar**, bandeja do sistema, notificações e botões de janela,
tudo construído com Quickshell sobre o **Hyprland**. Fica bonito no Wayland e não
estranha quem chega do Windows.

</td>
<td width="50%" valign="top">

### ⚙️ Configurações de verdade
Um app de **Configurações** com tela, som, rede, Bluetooth, temas, papel de parede,
desfoque da barra e tema de boot. Ninguém precisa editar arquivo de texto para mudar
o básico.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🐉 Draco, assistente de voz
Palavra de ativação, transcrição com Whisper, vozes Piper/Edge e integração com
agentes de IA. Responde em português.

</td>
<td width="50%" valign="top">

### 🤖 Agentes de IA no desktop
Chat próprio para Claude Code, Codex, Gemini e outros, com sessões, fila, voz e um
**navegador embutido** que o agente consegue controlar.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 💿 Gere sua própria ISO
O **Gerar ISO** cria uma imagem instalável a partir da sua máquina, como clone pessoal
ou como versão distribuível, sem os seus dados. O instalador detecta NVIDIA e
microcódigo sozinho.

</td>
<td width="50%" valign="top">

### 🔄 Atualizações assinadas
Os pacotes do Simba saem de um repositório pacman próprio, assinado com GPG. O
**Atualizar tudo** atualiza o Arch, o AUR e o Simba de uma vez.

</td>
</tr>
</table>

## 📦 Apps do Simba

| | App | O que faz |
|:-:|---|---|
| ⚙️ | **Configurações** | Central do sistema: aparência, temas (com loja da comunidade), tela, som, rede, contas |
| 🗂️ | **Explorador de Arquivos** | Gerenciador de arquivos próprio |
| 📊 | **Gerenciador de Tarefas** | Processos, desempenho e apps em execução |
| 🤖 | **Agentes de IA** | Chat com agentes de código, voz e navegador embutido |
| 🎙️ | **Transcrever** | Áudio para texto, localmente, com Whisper |
| 🧮 | **Calculadora** | Calculadora no visual do sistema |
| 💿 | **Gerar ISO** | Cria uma ISO instalável (clone pessoal ou distribuível) |
| 👋 | **Boas-vindas** | Primeiros passos depois da instalação |
| 🔒 | **Tela de bloqueio** e **temas de boot** | Plymouth e bloqueio com a identidade do Simba |

## 💾 Instalação

> [!NOTE]
> O Simba OS ainda é um projeto pessoal em evolução. A ISO pública e o repositório de
> pacotes assinados estão sendo preparados.

**Pela ISO:** gere a imagem no app **Gerar ISO** (modo *Distribuível*), grave num pendrive
e dê boot. O instalador pergunta disco, usuário e login automático.

**Num Arch Linux que já existe:** adicione o repositório ao `/etc/pacman.conf`
(o pacote `simba-keyring` faz isso sozinho):

```ini
[simba-os]
SigLevel = Required DatabaseRequired
Server = https://github.com/__USUARIO__/simba-os/releases/download/repo
```

```bash
sudo pacman -Sy simba-keyring
sudo pacman -S simba simba-apps simba-draco
simba-apps-usuario        # uma vez por usuário
```

## 🖼️ Papéis de parede

O Simba vem com papéis de parede próprios, e o gatinho aparece em vários deles.

<table>
<tr>
<td><img src="docs/imagens/papel-simba-lua.jpg" alt="Simba e a lua"></td>
<td><img src="docs/imagens/papel-simba-por-do-sol.jpg" alt="Simba no pôr do sol"></td>
<td><img src="docs/imagens/papel-simba-retrato-escuro.jpg" alt="Retrato do Simba"></td>
</tr>
<tr>
<td><img src="docs/imagens/papel-simba-patinhas.jpg" alt="Patinhas"></td>
<td><img src="docs/imagens/papel-montanhas.jpg" alt="Montanhas"></td>
<td><img src="docs/imagens/papel-aurora-escura.jpg" alt="Aurora"></td>
</tr>
</table>

## 🧩 Pacotes

| Pacote | O que tem |
|---|---|
| `simba` | Base: shell (barra, menus, notificações), scripts `simba-*`, temas, `/etc/skel`, tradução. Derivado do [Omarchy](https://github.com/basecamp/omarchy) (MIT) |
| `simba-apps` | Configurações, Menu Iniciar, Explorador, Gerenciador de Tarefas, Agentes, Transcrever, Boas-vindas, Gerar ISO, módulos da barra, tela de bloqueio, idiomas |
| `simba-draco` | Assistente de voz Draco (o ambiente Python e as vozes são preparados para cada usuário) |
| `simba-keyring` | Chave que assina os pacotes e a seção `[simba-os]` do `pacman.conf` |

Cada `pacotes/<pacote>/raiz/` espelha o sistema instalado (`raiz/usr/bin/x` → `/usr/bin/x`).

## 🛠️ Desenvolvimento

```bash
# 1. edite em pacotes/<pacote>/raiz/…  (suba pkgver/pkgrel no PKGBUILD a cada versão)
ferramentas/construir simba-apps                 # gera dist/simba-apps-*.pkg.tar.zst
sudo pacman -U dist/simba-apps-*.pkg.tar.zst     # testa no seu computador

# 2. publica para todas as instalações
ferramentas/publicar                             # assina, gera o banco e envia ao GitHub Releases
```

Na primeira vez, rode `ferramentas/criar-chave` (gera a chave GPG que assina os pacotes; a
chave privada fica só no seu computador) e `gh auth login`.

Os testes dos Agentes de IA ficam em `testes/agentes`:

```bash
python3 -m unittest discover -s testes/agentes
```

## 🌎 Idiomas

Português (Brasil) e inglês. Os textos dos apps próprios ficam em catálogos em
`pacotes/simba-apps/raiz/usr/share/simba-apps/idiomas/`, com o texto em português como
chave. Para adicionar um idioma, crie um novo `.json`; o `LEIA-ME.md` da pasta e as
ferramentas `extrair.py`, `marcar.py` e `conferir.py` explicam como.

## 📜 Licença

[MIT](LICENSE). A parte derivada do [Omarchy](https://github.com/basecamp/omarchy) mantém
o aviso original em [`NOTICE`](NOTICE) e [`LICENSES/omarchy-MIT.txt`](LICENSES/omarchy-MIT.txt).

<div align="center">
<br>
<sub>Feito com ☕ e 🐈 no Brasil.</sub>
</div>
