import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic as C
import qs.Comum

// Base for every settings page: big title, centered column, and a staggered
// reveal (each block rises and fades in a few frames after the previous one).
Flickable {
  id: f
  property string titulo: ""
  property string subtitulo: ""
  property string glifo: ""
  default property alias conteudo: col.data
  property alias cabecalhoExtra: extraCab.data
  property real revelacao: 0

  contentWidth: width
  contentHeight: coluna.implicitHeight + 56
  clip: true
  boundsBehavior: Flickable.StopAtBounds
  flickableDirection: Flickable.VerticalFlick
  maximumFlickVelocity: 4000
  C.ScrollBar.vertical: C.ScrollBar {
    id: barra
    policy: f.contentHeight > f.height ? C.ScrollBar.AsNeeded : C.ScrollBar.AlwaysOff
    contentItem: Rectangle {
      implicitWidth: barra.hovered || barra.pressed ? 8 : 4
      radius: Tema.raio > 0 ? width / 2 : 0
      color: Tema.texto3
      opacity: barra.active ? 0.7 : 0.25
      Behavior on opacity { NumberAnimation { duration: Tema.medio } }
      Behavior on implicitWidth { NumberAnimation { duration: Tema.rapido } }
    }
  }

  NumberAnimation on revelacao {
    id: revelar
    from: 0; to: 1
    duration: Tema.animacoes ? 900 : 0
    easing.type: Easing.Linear
    running: true
  }

  function itens() {
    var lista = [cab]
    for (var i = 0; i < col.children.length; i++) {
      var c = col.children[i]
      if (c.visible !== false) lista.push(c)
    }
    return lista
  }
  function prepararRevelacao() {
    var lista = itens()
    var n = Math.min(lista.length, 14)
    for (var i = 0; i < lista.length; i++) {
      (function(item, idx) {
        var deslize = Qt.createQmlObject(I18n.t('import QtQuick; Translate {}'), item)
        deslize.y = Qt.binding(function() {
          var p = Math.max(0, Math.min(1, (f.revelacao * (n + 5) - Math.min(idx, n)) / 5))
          var e = 1 - Math.pow(1 - p, 3)
          return (1 - e) * 18
        })
        var t = []
        for (var k = 0; k < item.transform.length; k++) t.push(item.transform[k])
        t.push(deslize)
        item.transform = t
        item.opacity = Qt.binding(function() {
          var p = Math.max(0, Math.min(1, (f.revelacao * (n + 5) - Math.min(idx, n)) / 5))
          return 1 - Math.pow(1 - p, 2)
        })
      })(lista[i], i)
    }
  }
  Component.onCompleted: { Navegacao.paginaAtual = f; Qt.callLater(prepararRevelacao) }

  Column {
    id: coluna
    width: Math.min(f.width - 64, 940)
    x: Math.round((f.width - width) / 2)
    y: 6
    spacing: 0

    RowLayout {
      id: cab
      width: parent.width
      spacing: 14
      ColumnLayout {
        Layout.fillWidth: true
        spacing: 4
        Texto {
          text: f.titulo
          font.pixelSize: Tema.tTitulao
          font.weight: Font.Bold
          font.letterSpacing: -0.5
          Layout.fillWidth: true
          elide: Text.ElideRight
        }
        Texto {
          visible: f.subtitulo !== ""
          text: f.subtitulo
          color: Tema.texto3
          wrapMode: Text.WordWrap
          Layout.fillWidth: true
        }
      }
      Row { id: extraCab; spacing: 8; Layout.alignment: Qt.AlignBottom }
    }

    Item { width: 1; height: 14 }

    ColumnLayout {
      id: col
      width: parent.width
      spacing: 8
    }
  }
}
