import QtQuick 6.11
import QtQuick.Window

// Retrato do Simba OS em pixel art (/usr/share/simba-apps/marca-pixel, gerado por ./gerar).
// Em múltiplos exatos de 36 px os pixels ficam nítidos (sem suavizar); fora disso suaviza.
// `cor` ficou por compatibilidade com o símbolo antigo (vetor de uma cor só).
// Sem implicitWidth/Height: no Image eles são somente leitura (Qt 6.11), e atribuí-los
// impedia o plugin de bloqueio inteiro de carregar (Super+L não bloqueava).
Image {
  id: s
  property color cor: "white"
  width: 72; height: 72
  readonly property real px: Math.max(width, height) * (Screen.devicePixelRatio || 1)
  source: "file:///usr/share/simba-apps/marca-pixel/" + (px > 288 ? "retrato-1152.png" : px > 72 ? "retrato-288.png" : "retrato-144.png")
  sourceSize: Qt.size(0, 0)
  fillMode: Image.PreserveAspectFit
  smooth: Math.round(px) % 36 !== 0
  mipmap: smooth
}
