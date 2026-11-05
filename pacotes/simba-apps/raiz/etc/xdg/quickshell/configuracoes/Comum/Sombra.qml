import QtQuick
import QtQuick.Effects
import qs.Comum

// Soft drop shadow drawn underneath `alvo` (children with negative z render
// below their parent). The shape copy it blurs is covered by the opaque card.
Item {
  id: s
  property Item alvo: parent
  property real intensidade: 1
  property real deslocamento: 10
  anchors.fill: alvo
  z: -1
  Rectangle {
    id: forma
    anchors.fill: parent
    radius: s.alvo && s.alvo.radius !== undefined ? s.alvo.radius : 0
    color: Tema.escuro ? "#000000" : "#202020"
    visible: false
  }
  MultiEffect {
    source: forma
    anchors.fill: forma
    autoPaddingEnabled: true
    shadowEnabled: true
    shadowColor: Tema.sombra
    shadowBlur: 1.0
    shadowOpacity: s.intensidade
    shadowVerticalOffset: s.deslocamento
    shadowHorizontalOffset: 0
    blurMax: 48
  }
}
