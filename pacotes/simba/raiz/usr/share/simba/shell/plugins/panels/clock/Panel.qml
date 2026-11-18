import QtQuick 6.11
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Model.js" as Model
import "../../notifications/components/PixelArte.js" as Px

// Painel do Relógio: Central de Notificações e Calendário flutuantes estilo Windows 11.
// Dois cartões flutuantes desacoplados (notificações em cima, data/calendário/foco embaixo),
// compactos (360 px), alinhados ao widget do relógio na barra de tarefas.
Panel {
  id: root
  moduleName: "simba.clock"
  ipcTarget: "simba.clock"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  // ---- Data de hoje e navegação do mês
  property date today: new Date()
  readonly property string todayKey: Model.keyForDate(today)

  property int viewYear: today.getFullYear()
  property int viewMonth: today.getMonth()
  readonly property date viewDate: new Date(viewYear, viewMonth, 1, 12)
  readonly property bool viewingCurrentMonth: viewYear === today.getFullYear() && viewMonth === today.getMonth()

  readonly property int weekStart: Model.normalizedWeekStart(setting("weekStartDay", null), 0)
  readonly property var labelLocale: Qt.locale("pt_BR")
  readonly property var weeks: Model.monthGrid(viewYear, viewMonth, weekStart, todayKey)

  readonly property color contentForeground: bar ? bar.foreground : Commons.Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family

  // Estado recolhido do calendário (estilo Windows 11)
  property bool calendarioRecolhido: false

  // Sessão de Foco (Windows 11)
  property int focoMinutos: 25
  property bool focoAtivo: false

  function passoFoco(delta) {
    var v = focoMinutos + delta
    if (v < 5) v = 5
    if (v > 120) v = 120
    focoMinutos = v
  }

  function alternarFoco() {
    focoAtivo = !focoAtivo
    if (focoAtivo) {
      Quickshell.execDetached(["simba-shell", "notifications", "toggleDnd"])
      Quickshell.execDetached(["notify-send", "-a", "Sessão de Foco", "-i", "preferences-system-time",
                               "Sessão de Foco iniciada", "Duração: " + focoMinutos + " minutos. Não perturbe ativado."])
    } else {
      Quickshell.execDetached(["simba-shell", "notifications", "toggleDnd"])
      Quickshell.execDetached(["notify-send", "-a", "Sessão de Foco", "-i", "preferences-system-time",
                               "Sessão de Foco encerrada", "Modo normal restaurado."])
    }
  }

  function open() {
    refresh()
    root.controller.show()
    Qt.callLater(function() {
      if (root.opened) setCenterHoverRevealSuppressed(true)
    })
  }

  function close() {
    setCenterHoverRevealSuppressed(false)
    root.controller.hide()
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }

  function setCenterHoverRevealSuppressed(value) {
    if (root.bar && typeof root.bar.setCenterHoverRevealSuppressed === "function")
      root.bar.setCenterHoverRevealSuppressed(value)
    else if (root.bar && "centerHoverRevealSuppressed" in root.bar)
      root.bar.centerHoverRevealSuppressed = value
  }

  function refresh() {
    root.today = new Date()
    root.goToToday()
  }

  function goToToday() {
    root.viewYear = today.getFullYear()
    root.viewMonth = today.getMonth()
  }

  function moveMonth(delta) {
    var next = Model.stepMonth(viewYear, viewMonth, delta)
    root.viewYear = next.year
    root.viewMonth = next.month
  }

  function moveYear(delta) {
    moveMonth(delta * 12)
  }

  SystemClock {
    id: clock
    precision: SystemClock.Minutes
    onDateChanged: {
      if (Model.keyForDate(clock.date) === String(root.todayKey)) return
      var followToday = root.viewingCurrentMonth
      root.today = clock.date
      if (followToday) root.goToToday()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    framed: false
    focusTarget: keyCatcher
    contentWidth: Style.space(360)
    contentHeight: panel.availableCardHeight > 0 ? panel.availableCardHeight : Style.space(680)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) {
        if (dx !== 0) root.moveMonth(dx)
        if (dy !== 0) root.moveYear(dy)
      }
      onActivateRequested: root.goToToday()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "[") root.moveMonth(-1)
        else if (t === "]") root.moveMonth(1)
        else if (t === "{") root.moveYear(-1)
        else if (t === "}") root.moveYear(1)
        else if (t === "t" || t === "T") root.goToToday()
      }

      Item {
        id: painelConteudo
        anchors.fill: parent

        // ========================================================
        // CARTÃO 2: DATA, CALENDÁRIO & FOCO (FLUTUANTE INFERIOR)
        // ========================================================
        Item {
          id: calCard
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          height: calLayout.implicitHeight

            // Fundo e borda do cartão do calendário (segue o tema da central)
            Rectangle {
              anchors.fill: parent
              visible: !central.pixel
              radius: central.raio
              color: central.cFundo
              border.width: 1
              border.color: central.cBorda
            }

            Canvas {
              id: calMoldura
              anchors.fill: parent
              visible: central.pixel
              antialiasing: false
              property string chave: central.tema + width + "x" + height + central.fg + central.bg
              onChaveChanged: requestPaint()
              onPaint: {
                var c = getContext("2d"); c.reset()
                if (!central.pixel) return
                var P = central.px, W = Math.floor(width / P), H = Math.floor(height / P)
                var f = String(central.cFundo), t = String(central.cBorda)
                Px.caixa(c, P, 0, 0, W, H, f, t, 2)
                Px.caixa(c, P, 2, 2, W - 4, H - 4, f, String(central.cBordaItem), 1)
              }
            }

            ColumnLayout {
              id: calLayout
              width: parent.width
              spacing: 0

              // ── 1. Linha da Data (com botão de recolher/expandir à direita) ──
              RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: central.pixel ? 12 : 14
                Layout.rightMargin: central.pixel ? 12 : 14
                Layout.topMargin: central.pixel ? 8 : 10
                Layout.bottomMargin: central.pixel ? 8 : 10
                spacing: 8

                Text {
                  Layout.fillWidth: true
                  textFormat: Text.PlainText
                  elide: Text.ElideRight
                  text: {
                    var t = Qt.locale("pt_BR").toString(root.today, "dddd, d 'de' MMMM")
                    return t.charAt(0).toUpperCase() + t.slice(1)
                  }
                  color: central.cTexto
                  font.family: central.fonteTitulo
                  font.pixelSize: central.pixel ? 15 : 13.5
                  font.bold: true
                  renderType: central.pixel ? Text.NativeRendering : Text.QtRendering
                }

                Rectangle {
                  implicitWidth: 24; implicitHeight: 24
                  radius: central.pixel ? 0 : 5
                  color: btnRecolherMouse.containsMouse ? central.cHover : "transparent"
                  border.width: central.pixel ? 1 : 0
                  border.color: central.cBorda
                  Text {
                    anchors.centerIn: parent
                    text: root.calendarioRecolhido ? "▼" : "▲"
                    font.family: central.pixel ? "Simba Pixel" : "Adwaita Sans"
                    font.pixelSize: 11
                    color: central.cTexto
                  }
                  MouseArea {
                    id: btnRecolherMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.calendarioRecolhido = !root.calendarioRecolhido
                  }
                }
              }

              // Linha separadora
              Rectangle {
                Layout.fillWidth: true
                height: 1
                color: central.pixel ? "transparent" : central.cBorda
                opacity: central.pixel ? 0 : 0.6
              }

              // ── 2. Seção do Calendário (Mês e Grade de Dias) ──
              ColumnLayout {
                id: secaoGrade
                visible: !root.calendarioRecolhido
                Layout.fillWidth: true
                Layout.leftMargin: central.pixel ? 10 : 12
                Layout.rightMargin: central.pixel ? 10 : 12
                Layout.topMargin: 8
                Layout.bottomMargin: 8
                spacing: 6

                // Linha de navegação do Mês
                RowLayout {
                  Layout.fillWidth: true
                  spacing: 4

                  Text {
                    Layout.fillWidth: true
                    text: Qt.locale("pt_BR").toString(root.viewDate, "MMMM 'de' yyyy")
                    color: central.cTexto
                    font.family: central.fonteTitulo
                    font.pixelSize: central.pixel ? 14 : 13
                    font.bold: true
                    font.capitalization: central.pixel ? Font.AllUppercase : Font.MixedCase
                    renderType: central.pixel ? Text.NativeRendering : Text.QtRendering
                  }

                  // Steppers de mês < e >
                  Row {
                    spacing: 2
                    Rectangle {
                      width: 22; height: 22
                      radius: central.pixel ? 0 : 4
                      color: prevMesMouse.containsMouse ? central.cHover : "transparent"
                      border.width: central.pixel ? 1 : 0
                      border.color: central.cBorda
                      Text { anchors.centerIn: parent; text: "<"; font.family: central.fonteTitulo; font.pixelSize: 12; color: central.cTexto }
                      MouseArea { id: prevMesMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.moveMonth(-1) }
                    }
                    Rectangle {
                      width: 22; height: 22
                      radius: central.pixel ? 0 : 4
                      color: nextMesMouse.containsMouse ? central.cHover : "transparent"
                      border.width: central.pixel ? 1 : 0
                      border.color: central.cBorda
                      Text { anchors.centerIn: parent; text: ">"; font.family: central.fonteTitulo; font.pixelSize: 12; color: central.cTexto }
                      MouseArea { id: nextMesMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.moveMonth(1) }
                    }
                  }
                }

                // Cabeçalhos dos dias da semana (D S T Q Q S S)
                RowLayout {
                  Layout.fillWidth: true
                  spacing: 0
                  Repeater {
                    model: ["D", "S", "T", "Q", "Q", "S", "S"]
                    Text {
                      required property string modelData
                      Layout.fillWidth: true
                      horizontalAlignment: Text.AlignHCenter
                      text: modelData
                      font.family: central.pixel ? "Simba Pixel" : "Adwaita Sans"
                      font.pixelSize: central.pixel ? 12 : 11
                      font.bold: true
                      color: central.cApagado
                    }
                  }
                }

                // Grade dos dias (6 semanas de 7 dias)
                ColumnLayout {
                  Layout.fillWidth: true
                  spacing: 2

                  Repeater {
                    model: root.weeks
                    delegate: RowLayout {
                      id: semanaRow
                      required property var modelData
                      Layout.fillWidth: true
                      spacing: 0

                      Repeater {
                        model: semanaRow.modelData.days
                        delegate: Item {
                          id: celulaDia
                          required property var modelData
                          Layout.fillWidth: true
                          implicitHeight: 26

                          readonly property bool hoje: modelData.today
                          readonly property bool mesAtual: modelData.inMonth
                          readonly property bool sobre: mouseDia.containsMouse

                          Rectangle {
                            anchors.centerIn: parent
                            width: 24; height: 24
                            radius: central.pixel ? 0 : (hoje ? 12 : 4)
                            color: hoje ? central.destaque : (sobre && mesAtual ? central.cHover : "transparent")
                            border.width: (hoje && central.pixel) ? 1 : 0
                            border.color: central.cTexto

                            Text {
                              anchors.centerIn: parent
                              text: celulaDia.modelData.day
                              font.family: central.pixel ? "Simba Pixel" : "Adwaita Sans"
                              font.pixelSize: central.pixel ? 13 : 11
                              font.bold: celulaDia.hoje
                              color: celulaDia.hoje ? "#ffffff" : (celulaDia.mesAtual ? central.cTexto : central.cApagado)
                              opacity: celulaDia.mesAtual ? 1.0 : 0.4
                            }
                          }

                          MouseArea {
                            id: mouseDia
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: celulaDia.mesAtual ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: {
                              if (celulaDia.hoje) root.goToToday()
                              else if (!celulaDia.mesAtual) {
                                if (celulaDia.modelData.day > 15) root.moveMonth(-1)
                                else root.moveMonth(1)
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }

              // Linha separadora antes da barra de foco
              Rectangle {
                Layout.fillWidth: true
                height: 1
                color: central.pixel ? "transparent" : central.cBorda
                opacity: central.pixel ? 0 : 0.6
              }

              // ── 3. Barra de Sessão de Foco (Windows 11) ──
              RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: central.pixel ? 12 : 14
                Layout.rightMargin: central.pixel ? 12 : 14
                Layout.topMargin: central.pixel ? 6 : 8
                Layout.bottomMargin: central.pixel ? 6 : 8
                spacing: 8

                // Stepper [-] 25 min [+]
                Rectangle {
                  implicitHeight: 28
                  Layout.preferredWidth: 106
                  radius: central.pixel ? 0 : 5
                  color: central.cItem
                  border.width: 1
                  border.color: central.cBordaItem

                  RowLayout {
                    anchors.fill: parent
                    anchors.margins: 2
                    spacing: 0

                    Rectangle {
                      Layout.preferredWidth: 24; Layout.fillHeight: true
                      radius: central.pixel ? 0 : 4
                      color: minusMouse.containsMouse ? central.cHover : "transparent"
                      Text { anchors.centerIn: parent; text: "−"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 12; color: central.cTexto }
                      MouseArea {
                        id: minusMouse
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.passoFoco(-5)
                      }
                    }

                    Text {
                      Layout.fillWidth: true
                      horizontalAlignment: Text.AlignHCenter
                      text: root.focoMinutos + " min"
                      font.family: central.fonteTitulo
                      font.pixelSize: central.pixel ? 13 : 11.5
                      font.bold: true
                      color: central.cTexto
                    }

                    Rectangle {
                      Layout.preferredWidth: 24; Layout.fillHeight: true
                      radius: central.pixel ? 0 : 4
                      color: plusMouse.containsMouse ? central.cHover : "transparent"
                      Text { anchors.centerIn: parent; text: "+"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 12; color: central.cTexto }
                      MouseArea {
                        id: plusMouse
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.passoFoco(5)
                      }
                    }
                  }
                }

                Item { Layout.fillWidth: true }

                // Botão de Foco [▶ Foco]
                Rectangle {
                  implicitHeight: 28
                  implicitWidth: focoConteudo.implicitWidth + 22
                  radius: central.pixel ? 0 : 6
                  color: root.focoAtivo ? central.destaque : (focoMouse.containsMouse ? central.cHover : central.cItem)
                  border.width: 1
                  border.color: root.focoAtivo ? central.destaque : central.cBordaItem

                  Row {
                    id: focoConteudo
                    anchors.centerIn: parent
                    spacing: 6

                    Text {
                      text: central.pixel ? (root.focoAtivo ? "⏹" : "😺") : (root.focoAtivo ? "󰓛" : "󰐊")
                      font.family: central.pixel ? "Simba Pixel" : "JetBrainsMono Nerd Font"
                      font.pixelSize: 12
                      color: root.focoAtivo ? "#ffffff" : (central.pixel ? central.cTexto : central.destaque)
                    }

                    Text {
                      text: root.focoAtivo ? "Parar" : "Foco"
                      font.family: central.fonteTitulo
                      font.pixelSize: central.pixel ? 13 : 11.5
                      font.bold: true
                      color: root.focoAtivo ? "#ffffff" : central.cTexto
                    }
                  }

                  MouseArea {
                    id: focoMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.alternarFoco()
                  }
                }
              }
            }
          }

          // ========================================================
          // CARTÃO 1: CENTRAL DE NOTIFICAÇÕES (FLUTUANTE SUPERIOR)
          // ========================================================
          CentralNotificacoes {
            id: central
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: calCard.top
            anchors.bottomMargin: Style.space(10) // Vão de 10px entre os 2 cartões flutuantes
            ativo: root.opened
            fg: root.contentForeground
            onAcionado: root.close()
          }
        }
      }
    }
  }
