import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Compatibilidade Windows (.exe)")
  subtitulo: I18n.t("Execução e integração transparente de jogos e programas Windows usando Wine Staging e Proton (UMU).")

  Secao { titulo: I18n.t("Atalhos e Menu de Aplicativos") }
  Cartao {
    Linha {
      glifo: Icones.sync
      titulo: I18n.t("Sincronizar atalhos instalados")
      descricao: I18n.t("Varre os prefixos e atalhos do Windows e cria lançadores nativos com ícones no seu menu de aplicativos.")
      Botao {
        texto: I18n.t("Sincronizar Agora")
        onClicado: {
          Sistema.sh("simba-exe --integrar", function(out, code) {
            Navegacao.confirmar(I18n.t("Atalhos do Windows sincronizados!"), Icones.checkboxMarkedCircle)
          })
        }
      }
    }
  }

  Secao { titulo: I18n.t("Ambientes e Prefixos do Simba") }
  Cartao {
    Linha {
      glifo: Icones.gamepadVariant
      titulo: I18n.t("Prefixo de Jogos (Proton / UMU)")
      descricao: I18n.t("Otimizado para jogos DirectX 9/11/12 e Vulkan, com DXVK, VKD3D, FSR e GameMode nativo.")
      Botao {
        texto: I18n.t("Abrir Pasta")
        onClicado: Sistema.solto(["xdg-open", Sistema.home + "/.local/share/simba-exe/prefixes/jogos"])
      }
    }
    Linha {
      glifo: Icones.application
      titulo: I18n.t("Prefixo de Aplicativos (Wine)")
      descricao: I18n.t("Ambiente leve e rápido para programas utilitários, instaladores clássicos e ferramentas de escritório.")
      Botao {
        texto: I18n.t("Abrir Pasta")
        onClicado: Sistema.solto(["xdg-open", Sistema.home + "/.local/share/simba-exe/prefixes/apps"])
      }
    }
  }

  Secao { titulo: I18n.t("Ferramentas e Configurações") }
  Cartao {
    Linha {
      glifo: Icones.cogOutline
      titulo: I18n.t("Painel de Controle do Wine (winecfg)")
      descricao: I18n.t("Configurar versão do Windows simulada, resolução, drivers de áudio e substituições de DLL.")
      Botao {
        texto: I18n.t("Abrir winecfg")
        onClicado: Sistema.solto(["simba-exe", "--modo", "app", "winecfg"])
      }
    }
    Linha {
      glifo: Icones.speedometer
      titulo: I18n.t("Telemetria de Jogos (MangoHud)")
      descricao: I18n.t("Monitor de FPS, temperaturas e consumo de GPU/CPU. Pressione Shift Direito + F12 em qualquer jogo.")
      Botao {
        texto: I18n.t("Editar Perfil")
        onClicado: Sistema.soltoSh("simba-default-editor /etc/MangoHud/MangoHud.conf")
      }
    }
  }
}
