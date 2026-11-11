# Instalar o Simba OS

Guia passo a passo, do download ao primeiro uso. Leva uns 30 minutos.

> [!WARNING]
> A instalação **apaga o disco inteiro** que você escolher. Não há instalação lado a lado com o
> Windows no mesmo disco. Faça backup antes.

## 1. O que você precisa

| | Mínimo | Recomendado |
|---|---|---|
| Computador | 64 bits (x86_64) com **UEFI** | — |
| Memória | 4 GB | 8 GB ou mais |
| Disco | 25 GB | 64 GB ou mais, SSD |
| Pendrive | 8 GB (será apagado) | — |
| Internet | Não precisa para instalar | Precisa para atualizar e instalar apps |

- **Secure Boot desligado.** O Simba OS ainda não é assinado para Secure Boot.
- Placas NVIDIA: o instalador detecta o modelo e escolhe o driver. Placas muito antigas
  (série GeForce 600/700 Kepler ou anteriores) não têm driver atual e usam o vídeo genérico.

## 2. Baixar

Baixe a ISO e o arquivo de verificação em
**[sourceforge.net/projects/simba-os/files/0.1.0](https://sourceforge.net/projects/simba-os/files/0.1.0/)**:

- `simba-os-0.1.0-x86_64.iso` (4,0 GB)
- `simba-os-0.1.0-x86_64.iso.sha256`

### Conferir o download

Com os dois arquivos na mesma pasta:

**Linux**

```bash
sha256sum -c simba-os-0.1.0-x86_64.iso.sha256
```

Deve aparecer `simba-os-0.1.0-x86_64.iso: OK` (ou `SUCESSO`).

**Windows** (PowerShell, na pasta dos arquivos)

```powershell
(Get-FileHash .\simba-os-0.1.0-x86_64.iso).Hash.ToLower()
Get-Content .\simba-os-0.1.0-x86_64.iso.sha256
```

Os dois códigos têm que ser iguais. Se não forem, baixe de novo.

## 3. Gravar no pendrive

Todo o conteúdo do pendrive será apagado.

| Onde | Programa | Como |
|---|---|---|
| Windows | [Rufus](https://rufus.ie) | Escolha a ISO. Se perguntar, use **modo DD** (não ISO) |
| Windows, macOS, Linux | [balenaEtcher](https://etcher.balena.io) | Escolha a ISO, o pendrive e **Flash** |
| Linux | Impression ou Fedora Media Writer | Escolha a ISO e o pendrive |
| Simba OS | **Gerar ISO** › Gravar | Escolha a ISO e o pendrive |

Programas que guardam várias ISOs no mesmo pendrive (como o Ventoy) não foram testados.

## 4. Dar boot pelo pendrive

1. Com o pendrive conectado, ligue o computador e aperte a tecla do **menu de boot** logo no
   início. Varia por fabricante: **F12** (Dell, Lenovo), **F9** (HP), **F8** (Asus),
   **F11** (MSI, ASRock), **Esc** ou **F12** (Acer).
2. Escolha o pendrive, a opção que começa com **UEFI**.
3. Se o pendrive não aparecer, ou aparecer um aviso de segurança, entre na configuração do
   computador (**F2** ou **Del** ao ligar), **desligue o Secure Boot** e confira se o modo de
   boot está em **UEFI** (não "Legacy" nem "CSM").

O pendrive mostra o gato do Simba e abre o instalador sozinho.

## 5. Instalar

O instalador é feito de perguntas simples. Use as setas e **Enter**.

1. **Idioma**: português (Brasil) ou inglês.
2. **Teclado**: ABNT2, americano internacional ou americano. Dá para trocar depois.
3. **Sua conta**: seu nome, o nome de usuário (sugerido a partir do nome) e uma senha.
   > [!IMPORTANT]
   > O disco é **criptografado**: essa senha também desbloqueia o disco ao ligar. **Não a
   > esqueça**, porque sem ela não há como recuperar os arquivos.
4. **Nome do computador**: como ele aparece na rede.
5. **Onde instalar**: escolha o disco. Tudo nele será apagado.
6. **Desbloquear o disco automaticamente?** Só aparece se o computador tiver chip TPM. Com
   **Sim**, o computador não pede a senha do disco ao ligar.
7. **Entrar sem senha ao ligar?** O padrão é **Não**. Com **Sim**, qualquer pessoa que ligar
   o computador entra na sua conta.
8. **Resumo**: confira e escolha **Instalar**.

Ao terminar, escolha **Reiniciar agora** e tire o pendrive quando a tela apagar.

## 6. Primeiro uso

- Na primeira entrada aparece a tela de **boas-vindas**.
- **Atualize logo**: Configurações › Sistema › **Atualizar tudo**. A ISO é de uma data;
  as atualizações trazem tudo o que mudou desde então.
- Atalhos principais:

| Tecla | O que faz |
|---|---|
| **Super** (sozinha) | Menu Iniciar |
| **Super + Espaço** | Menu do Simba (instalar apps, configurar, sistema) |
| **Super + Enter** | Terminal |
| **Super + K** | Todos os atalhos |
| **Super + Esc** | Bloquear, reiniciar, desligar |

- **Instalar programas**: Super + Espaço › **Instalar**, ou a **Loja**. Spotify, Hydra,
  Lutris e outros vêm daí, sob demanda.

## 7. Problemas comuns

**"Inicie o pendrive em modo UEFI"**
O computador deu boot no modo antigo (Legacy/CSM). Escolha no menu de boot a opção do
pendrive que começa com **UEFI**, ou desligue o CSM na configuração do computador.

**O pendrive não aparece no menu de boot**
Desligue o **Secure Boot**. Se continuar, grave de novo (no Rufus, em modo DD) ou tente
outra porta USB.

**"Nenhum disco com espaço suficiente"**
O disco precisa de pelo menos 25 GB. O próprio pendrive nunca aparece na lista.

**Pede uma senha ao ligar**
É a senha do disco criptografado, a mesma da sua conta. Para não pedir mais, só com TPM:
reinstale e responda **Sim** no passo 6 do instalador.

**Tela preta depois de instalar (NVIDIA)**
Abra um terminal com **Ctrl + Alt + F2**, entre com seu usuário e rode `simba-saude`.
Mande o resultado num relato de problema (abaixo).

## 8. Canal de teste (opcional)

Quer receber as atualizações alguns dias antes e ajudar a achar problemas?

```bash
simba-canal teste      # ativa o canal de teste
simba-canal estavel    # volta ao normal
simba-canal            # mostra o canal atual
```

Depois de trocar, rode **Atualizar tudo**. Use só em máquina em que um problema não atrapalhe
seu dia.

## 9. Relatar um problema

Abra um relato em
**[github.com/renanjsilv/simba-os/issues](https://github.com/renanjsilv/simba-os/issues)**
dizendo:

- o que você fez e o que aconteceu (uma foto da tela ajuda);
- o modelo do computador;
- se conseguir abrir um terminal, a saída de:

```bash
fastfetch
simba-saude
simba-canal
```
