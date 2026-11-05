import QtQuick
import qs.Comum

Text {
  color: Tema.texto
  font.family: Tema.fonte
  font.pixelSize: Tema.tCorpo
  textFormat: Text.PlainText
  Behavior on color { ColorAnimation { duration: Tema.lento; easing.type: Tema.curva } }
}
