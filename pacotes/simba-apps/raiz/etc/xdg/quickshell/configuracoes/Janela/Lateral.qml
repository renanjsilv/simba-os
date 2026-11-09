import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Comum

// Sidebar: profile, global search and the category list. The selection bar is
// "elastic": its leading edge moves first and the trailing edge catches up.
Item {
  id: l
  property var paginas: []
  property bool compacta: false
  property alias busca: campoBusca
  property string usuario: Quickshell.env("USER") || ""
  property string nomeCompleto: ""
  property string versao: ""
  signal escolhida(string id)
  signal buscaFoco(bool foco)
  signal buscaBaixo()
  signal buscaEnter()

  Process {
    command: ["bash", "-c", "getent passwd \"$USER\" | cut -d: -f5 | cut -d, -f1; simba-version 2>/dev/null | head -1"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        var p = text.split("\n")
        l.nomeCompleto = (p[0] || "").trim()
        l.versao = (p[1] || "").trim()
      }
    }
  }
  readonly property string nomeExibido: nomeCompleto || (usuario.charAt(0).toUpperCase() + usuario.slice(1))

  Rectangle {
    anchors.fill: parent
    color: Tema.alfa(Tema.lateral, 0.55)
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Tema.linha }
  }

  ColumnLayout {
    anchors.fill: parent
    anchors.topMargin: 18
    anchors.bottomMargin: 12
    anchors.leftMargin: l.compacta ? 10 : 14
    anchors.rightMargin: l.compacta ? 10 : 14
    spacing: 12

    // ── profile ───────────────────────────────────────────────────────────
    RowLayout {
      Layout.fillWidth: true
      spacing: 12
      Avatar {
        id: avatar
        Layout.preferredWidth: l.compacta ? 40 : 48
        Layout.preferredHeight: Layout.preferredWidth
        Layout.alignment: l.compacta ? Qt.AlignHCenter : Qt.AlignLeft
        nome: l.nomeExibido
      }
      ColumnLayout {
        visible: !l.compacta
        Layout.fillWidth: true
        spacing: 1
        Texto {
          text: l.nomeExibido
          font.pixelSize: Tema.tSubtitulo + 1
          font.weight: Font.DemiBold
          elide: Text.ElideRight
          Layout.fillWidth: true
        }
        Texto {
          text: I18n.t("Simba OS ") + l.versao.replace(/-\d+$/, "") + " · " + Tema.nome.split("-").map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1) }).join(" ")
          color: Tema.texto3
          font.pixelSize: Tema.tLegenda
          elide: Text.ElideRight
          Layout.fillWidth: true
        }
      }
    }

    // ── search ────────────────────────────────────────────────────────────
    Campo {
      id: campoBusca
      visible: !l.compacta
      Layout.fillWidth: true
      glifo: Icones.magnify
      dica: I18n.t("Localizar configuração")
      rightPadding: text.length ? 30 : 58
      onActiveFocusChanged: l.buscaFoco(activeFocus)
      Keys.onDownPressed: l.buscaBaixo()
      Keys.onReturnPressed: l.buscaEnter()
      Texto {
        visible: !campoBusca.activeFocus && campoBusca.text === ""
        anchors.right: parent.right
        anchors.rightMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        text: I18n.t("Ctrl F")
        color: Tema.texto3
        font.pixelSize: Tema.tLegenda - 1
      }
    }
    Botao {
      visible: l.compacta
      Layout.alignment: Qt.AlignHCenter
      glifo: Icones.magnify
      tipo: "fantasma"
      onClicado: l.escolhida("__busca")
    }

    // ── categories ────────────────────────────────────────────────────────
    ListView {
      id: lista
      Layout.fillWidth: true
      Layout.fillHeight: true
      clip: true
      model: l.paginas
      spacing: 1
      boundsBehavior: Flickable.StopAtBounds
      currentIndex: {
        // a lateral lista grupos: vale o grupo que contém a página aberta
        for (var i = 0; i < l.paginas.length; i++) {
          var e = l.paginas[i]
          if (e.id === Navegacao.pagina) return i
          var ps = e.paginas || []
          for (var k = 0; k < ps.length; k++) if (ps[k].id === Navegacao.pagina) return i
        }
        return 0
      }
      highlightFollowsCurrentItem: false
      onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)

      // Elastic selection
      property real alvoTopo: currentItem ? currentItem.y : 0
      property real alvoBase: currentItem ? currentItem.y + currentItem.height : 0
      property real topo: alvoTopo
      property real base: alvoBase
      property bool descendo: false
      onAlvoTopoChanged: descendo = alvoTopo > topo
      Behavior on topo { NumberAnimation { duration: lista.descendo ? Tema.lento : Tema.medio; easing.type: Easing.OutQuart } }
      Behavior on base { NumberAnimation { duration: lista.descendo ? Tema.medio : Tema.lento; easing.type: Easing.OutQuart } }

      Rectangle {
        z: -1
        x: 0
        y: lista.topo - lista.contentY
        width: lista.width
        height: Math.max(0, lista.base - lista.topo)
        radius: Tema.raio
        color: Tema.superficieMax
        Rectangle {
          x: 0
          anchors.verticalCenter: parent.verticalCenter
          width: 3
          height: Math.min(16, parent.height - 16)
          radius: 1.5
          color: Tema.realce
        }
      }

      delegate: Item {
        id: item
        required property var modelData
        required property int index
        readonly property bool atual: index === lista.currentIndex
        width: lista.width
        height: modelData.separador ? 9 : 34
        Rectangle {
          visible: !!item.modelData.separador
          anchors.verticalCenter: parent.verticalCenter
          x: 10
          width: parent.width - 20
          height: 1
          color: Tema.linha
        }
        Rectangle {
          visible: !item.modelData.separador
          anchors.fill: parent
          radius: Tema.raio
          color: ma.containsMouse && !item.atual ? Tema.hover : "transparent"
          Behavior on color { ColorAnimation { duration: Tema.rapido } }
        }
        RowLayout {
          visible: !item.modelData.separador
          anchors.fill: parent
          anchors.leftMargin: l.compacta ? 0 : 14
          anchors.rightMargin: 8
          spacing: 12
          Glifo {
            g: item.modelData.glifo || ""
            tamanho: 17
            color: item.atual ? Tema.texto : Tema.texto2
            Layout.alignment: l.compacta ? Qt.AlignHCenter : Qt.AlignVCenter
            Layout.fillWidth: l.compacta
            scale: ma.pressed ? 0.85 : 1
            Behavior on scale { NumberAnimation { duration: Tema.rapido } }
          }
          Texto {
            visible: !l.compacta
            text: item.modelData.titulo || ""
            color: item.atual ? Tema.texto : Tema.texto2
            font.weight: item.atual ? Font.DemiBold : Font.Normal
            elide: Text.ElideRight
            Layout.fillWidth: true
          }
        }
        MouseArea {
          id: ma
          anchors.fill: parent
          enabled: !item.modelData.separador
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: l.escolhida(item.modelData.id)
        }
      }
    }
  }
}
