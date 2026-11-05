import QtQuick
import qs.Comum

// Ícone de app/arquivo (caminho já resolvido) ou, sem ícone, um glifo.
Item {
  id: r
  property string fonte: ""
  property string glifo: ""
  property int tamanho: 32
  implicitWidth: tamanho; implicitHeight: tamanho
  Image {
    id: img
    anchors.fill: parent
    source: r.fonte
    sourceSize: Qt.size(r.tamanho * 2, r.tamanho * 2)
    fillMode: Image.PreserveAspectFit
    asynchronous: true
    smooth: true
    mipmap: true
    visible: status === Image.Ready && !r.glifo
  }
  Glifo {
    anchors.centerIn: parent
    visible: !!r.glifo || img.status !== Image.Ready
    g: r.glifo || Icones.application
    tamanho: Math.round(r.tamanho * 0.75)
    color: Tema.texto2
  }
}
