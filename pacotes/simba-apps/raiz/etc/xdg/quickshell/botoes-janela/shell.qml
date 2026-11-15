// BotoesJanela sozinho num Quickshell próprio (qs -c botoes-janela). O normal é ele rodar DENTRO do
// processo das Configurações (configuracoes/shell.qml, "componentes hospedados"), o que
// economiza um Quickshell inteiro (~85 MB). Se as Configurações já o hospedam, este sai.
import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
  id: raiz
  property bool sozinho: false
  Process {
    running: true
    command: ["sh", "-c", 'p=$(cat "${XDG_RUNTIME_DIR:-/tmp}/simba-hospede/botoes-janela" 2>/dev/null) && [ "$p" != ' + Quickshell.processId + ' ] && grep -qxE "qs|quickshell" "/proc/$p/comm" 2>/dev/null']
    onExited: function(codigo) {
      if (codigo === 0) { console.log("botoes-janela: já roda dentro das Configurações; saindo"); Qt.quit() }
      else raiz.sozinho = true
    }
  }
  LazyLoader { active: raiz.sozinho; BotoesJanela {} }
}
