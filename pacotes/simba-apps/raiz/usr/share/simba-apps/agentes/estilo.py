"""Folha de estilo do chat dos Agentes de IA."""

CSS = """
window.background, .chat-window, .chat-bg, .chat-scroll {
  background-color: @window_bg_color;
}

headerbar {
  background-color: alpha(@window_bg_color, 0.94);
  border-bottom: 1px solid alpha(@window_fg_color, 0.07);
  box-shadow: none;
}

/* Seletor de agente no cabeçalho */
.agent-pill {
  background-color: alpha(@window_fg_color, 0.055);
  border: 1px solid alpha(@window_fg_color, 0.10);
  border-radius: 12px;
  padding: 2px 7px;
  margin: 4px 0 4px 2px;
}
.agent-pill image { opacity: 0.80; }
.agent-pill dropdown > button {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 2px 4px;
  min-height: 28px;
}

.icon-button {
  min-width: 34px;
  min-height: 34px;
  padding: 0;
  border-radius: 10px;
}
.icon-button:hover { background-color: alpha(@window_fg_color, 0.08); }

/* Conversa */
.msg-user-row { margin: 6px 0 4px 0; }
.user-bubble {
  background-color: alpha(@accent_bg_color, 0.22);
  border: 1px solid alpha(@accent_bg_color, 0.36);
  border-radius: 18px 18px 6px 18px;
  padding: 12px 18px;
  box-shadow: 0 1px 4px alpha(#000, 0.08);
}
.user-bubble label {
  color: @window_fg_color;
  font-size: 15px;
}

.assistant-card {
  background-color: alpha(@window_fg_color, 0.04);
  border: 1px solid alpha(@window_fg_color, 0.09);
  border-radius: 16px;
  padding: 16px 20px;
  margin: 4px 0 8px 0;
  box-shadow: 0 1px 4px alpha(#000, 0.06);
}
.assistant-avatar {
  min-width: 28px;
  min-height: 28px;
  background-color: alpha(@accent_bg_color, 0.16);
  border: 1px solid alpha(@accent_bg_color, 0.22);
  border-radius: 999px;
}
.assistant-name { font-weight: 700; font-size: 13.5px; }
.model-badge {
  background-color: alpha(@accent_bg_color, 0.16);
  color: @accent_bg_color;
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 600;
}
.msg-time { font-size: 11px; opacity: 0.55; }

/* Atividade da IA: discreta por padrão, detalhes sob demanda */
.activity-row { margin: 0; min-height: 22px; }
.activity-toggle {
  font-size: 11.5px;
  color: alpha(@window_fg_color, 0.52);
  padding: 1px 7px;
  border-radius: 7px;
  min-height: 22px;
}
.activity-toggle:hover {
  background-color: alpha(@window_fg_color, 0.06);
  color: alpha(@window_fg_color, 0.82);
}
.activity-log {
  background-color: alpha(@window_fg_color, 0.03);
  border-radius: 10px;
  padding: 7px 10px;
  margin: 3px 0 2px 0;
}
.activity-log text {
  background-color: transparent;
  color: alpha(@window_fg_color, 0.60);
  font-size: 11.5px;
}

.msg-body {
  background-color: transparent;
  font-size: 15px;
  color: @window_fg_color;
}
.msg-body text { background-color: transparent; }
.msg-actions {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid alpha(@window_fg_color, 0.06);
}
.action-button {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 8px;
}

/* Bloco de Código com Sintaxe e Botão Copiar */
.code-block-box {
  background-color: alpha(#000, 0.28);
  border: 1px solid alpha(@window_fg_color, 0.12);
  border-radius: 10px;
  margin: 8px 0;
}
.code-block-header {
  background-color: alpha(@window_fg_color, 0.06);
  border-bottom: 1px solid alpha(@window_fg_color, 0.08);
  border-radius: 9px 9px 0 0;
  padding: 3px 10px;
}
.code-block-lang {
  font-family: monospace;
  font-size: 11px;
  font-weight: 600;
  color: alpha(@window_fg_color, 0.65);
}
.code-copy-btn {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  color: alpha(@window_fg_color, 0.80);
}
.code-copy-btn:hover {
  background-color: alpha(@window_fg_color, 0.08);
  color: @window_fg_color;
}
.code-block-view {
  background-color: transparent;
  font-family: monospace;
  font-size: 13px;
}

.duration-badge {
  background-color: alpha(@window_fg_color, 0.08);
  color: alpha(@window_fg_color, 0.70);
  border-radius: 999px;
  padding: 1px 7px;
  font-size: 10.5px;
  font-weight: 600;
}

.handover-pill {
  background-color: alpha(@warning_color, 0.12);
  border: 1px solid alpha(@warning_color, 0.28);
  color: @warning_color;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
}
.system-pill {
  color: alpha(@window_fg_color, 0.62);
  font-size: 12px;
  padding: 4px 10px;
}

/* Composer */
.composer-shell {
  background-color: alpha(@window_fg_color, 0.045);
  border: 1px solid alpha(@window_fg_color, 0.11);
  border-radius: 18px;
  padding: 8px 10px 6px 10px;
  box-shadow: 0 2px 10px alpha(#000, 0.10);
}
.composer-shell.focado {
  border-color: alpha(@accent_bg_color, 0.90);
  box-shadow: 0 0 0 1px alpha(@accent_bg_color, 0.55);
}
.composer-text {
  background-color: transparent;
  font-size: 14.5px;
}
.composer-text text { background-color: transparent; }
.composer-placeholder {
  font-size: 14.5px;
  color: alpha(@window_fg_color, 0.45);
}
.composer-hint {
  font-size: 11px;
  color: alpha(@window_fg_color, 0.45);
}
.chip {
  background-color: transparent;
  border-radius: 8px;
  padding: 2px 7px;
  font-size: 12px;
  min-height: 26px;
}
.chip:hover { background-color: alpha(@window_fg_color, 0.07); }

/* Seletor de modelo no rodapé do composer */
.model-chip {
  background-color: transparent;
  border-radius: 8px;
  min-height: 26px;
}
.model-chip > button {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 1px 6px;
  min-height: 26px;
  font-size: 12px;
  color: alpha(@window_fg_color, 0.88);
}
.model-chip > button:hover { background-color: alpha(@window_fg_color, 0.07); }
.model-chip image { opacity: 0.75; }

/* Central de agentes */
.central-hero {
  padding: 18px 16px 14px 16px;
}
.central-icone {
  min-width: 56px;
  min-height: 56px;
  background-color: alpha(@accent_bg_color, 0.14);
  border: 1px solid alpha(@accent_bg_color, 0.24);
  border-radius: 16px;
}
.central-titulo { font-size: 19px; font-weight: 800; }
.central-sub { font-size: 12.5px; opacity: 0.62; }

.send-button {
  min-width: 34px;
  min-height: 34px;
  padding: 0;
  border-radius: 999px;
  background-color: @accent_bg_color;
  color: @accent_fg_color;
}
.send-button:hover { background-color: @accent_bg_color; }
.send-button:disabled { opacity: 0.40; }
.stop-button {
  min-width: 34px;
  min-height: 34px;
  padding: 0;
  border-radius: 999px;
}

/* Estado vazio */
.empty-state { padding: 24px; }
.empty-icon-img { margin-bottom: 2px; }
.empty-title { font-size: 24px; font-weight: 800; }
.empty-desc {
  font-size: 14px;
  color: alpha(@window_fg_color, 0.62);
}
.suggestion {
  background-color: transparent;
  border: 1px solid alpha(@window_fg_color, 0.12);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12.5px;
}
.suggestion:hover {
  background-color: alpha(@window_fg_color, 0.06);
  border-color: alpha(@accent_bg_color, 0.45);
}

/* Mensagem na fila (enviada enquanto o agente respondia) */
.fila-label {
  font-size: 11px;
  color: alpha(@window_fg_color, 0.55);
}

/* O que a IA está fazendo agora, ao lado do spinner */
.activity-now {
  font-size: 11.5px;
  color: alpha(@window_fg_color, 0.55);
}

/* Uso do limite no rodapé */
.uso-alto { color: @warning_color; }

/* Modo somente leitura ligado */
.chip.seguro-ativo {
  background-color: alpha(@success_color, 0.14);
  color: @success_color;
}

/* Microfone gravando */
.stop-button.gravando {
  background-color: alpha(@error_color, 0.18);
  color: @error_color;
}

/* Tabelas markdown (grade de verdade, não desenho em fonte mono) */
.md-tabela-moldura {
  border: 1px solid alpha(@window_fg_color, 0.12);
  border-radius: 10px;
}
.md-tabela label { padding: 7px 12px; }
.md-th {
  font-weight: 700;
  background-color: alpha(@window_fg_color, 0.06);
  border-bottom: 1px solid alpha(@window_fg_color, 0.12);
}
.md-td { border-bottom: 1px solid alpha(@window_fg_color, 0.05); }
.md-par { background-color: alpha(@window_fg_color, 0.025); }

/* Blocos de código ocupam a largura da mensagem */
.code-block-box { margin: 2px 0; }
.code-block-box scrolledwindow { border-radius: 0 0 10px 10px; }
.code-copy-btn box { spacing: 4px; }
"""
