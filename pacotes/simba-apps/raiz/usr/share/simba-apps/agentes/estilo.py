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
  min-width: 30px;
  min-height: 30px;
  padding: 0;
  background-color: alpha(@window_fg_color, 0.07);
  border: 1px solid alpha(@window_fg_color, 0.10);
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
.model-badge image { color: @window_fg_color; }
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

/* Anexos: faixa acima do texto e miniaturas nas mensagens */
.anexos-faixa { margin: 2px 2px 4px 2px; }
.anexos-faixa > flowboxchild, .user-bubble flowboxchild { padding: 0; }
.anexo-botao {
  padding: 0;
  border-radius: 10px;
  border: 1px solid alpha(@window_fg_color, 0.14);
  background-color: alpha(@window_fg_color, 0.05);
}
.anexo-botao:hover { border-color: alpha(@accent_bg_color, 0.70); }
.anexo-foto { border-radius: 9px; }
.anexo-arquivo { padding: 6px 10px; font-size: 12px; }
.anexo-remover {
  min-width: 20px;
  min-height: 20px;
  padding: 0;
  margin: 3px;
  background-color: alpha(#000, 0.65);
  color: #fff;
}
.anexo-remover:hover { background-color: @error_color; }
.anexo-remover image { -gtk-icon-size: 12px; }

/* Arrastando arquivos sobre a janela */
.chat-bg:drop(active) { box-shadow: inset 0 0 0 2px alpha(@accent_bg_color, 0.70); }

/* Busca na conversa */
.barra-busca {
  padding: 6px 12px;
  background-color: alpha(@window_bg_color, 0.94);
  border-bottom: 1px solid alpha(@window_fg_color, 0.07);
}

/* Painel de uso e custo */
.uso-cartao {
  background-color: alpha(@window_fg_color, 0.045);
  border: 1px solid alpha(@window_fg_color, 0.09);
  border-radius: 14px;
  padding: 14px 16px;
}
.uso-rotulo { font-size: 12px; color: alpha(@window_fg_color, 0.62); }
.uso-valor { font-size: 26px; font-weight: 700; }
.uso-detalhe { font-size: 12px; color: alpha(@window_fg_color, 0.55); }
.uso-numero { font-feature-settings: "tnum"; }
progressbar.uso-barra > trough { min-height: 6px; border-radius: 3px; background-color: alpha(@accent_bg_color, 0.16); }
progressbar.uso-barra > trough > progress { min-height: 6px; border-radius: 3px; background-color: @accent_bg_color; }
levelbar.uso-medidor > trough { min-height: 8px; border-radius: 4px; padding: 0; }
levelbar.uso-medidor > trough > block { min-height: 8px; border-radius: 4px; border: none; }
levelbar.uso-medidor > trough > block.empty { background-color: alpha(@accent_bg_color, 0.16); }
levelbar.uso-medidor > trough > block.uso-ok { background-color: @accent_bg_color; }
levelbar.uso-medidor > trough > block.uso-alto { background-color: @warning_color; }
levelbar.uso-medidor > trough > block.uso-critico { background-color: @error_color; }

/* navegador embutido */
.navegador { border-left: 1px solid alpha(currentColor, 0.12); }
.navegador-barra entry { min-height: 30px; border-radius: 15px; padding: 0 12px; }
.navegador-aviso {
  background: alpha(@accent_bg_color, 0.92); color: @accent_fg_color;
  border-radius: 999px; padding: 6px 14px; font-weight: 600; font-size: 0.9em;
}
"""

# ── Visual 2026-11: inspirado no Claude/ChatGPT (sem cartão nas respostas, bloco
# "Pensando" com linha do tempo, código separado da conversa, animações leves).
CSS += """
/* ---------- animações ---------- */
@keyframes surgir { from { opacity: 0; margin-top: 8px; } to { opacity: 1; margin-top: 0; } }
@keyframes surgir-suave { from { opacity: 0; } to { opacity: 1; } }
@keyframes pulsar { 0% { opacity: .25; } 50% { opacity: 1; } 100% { opacity: .25; } }
@keyframes respirar { 0% { opacity: .55; } 50% { opacity: 1; } 100% { opacity: .55; } }
@keyframes girar-brilho { from { -gtk-icon-transform: rotate(0deg); } to { -gtk-icon-transform: rotate(360deg); } }
.msg-entrada { animation: surgir 320ms cubic-bezier(.2,.8,.2,1); }
.surgir { animation: surgir-suave 220ms ease-out; }

/* ---------- coluna de leitura ---------- */
.coluna-chat { margin: 0; }

/* Resposta da IA: sem cartão, texto direto na página (como Claude/ChatGPT) */
.assistant-card {
  background: none;
  border: none;
  box-shadow: none;
  padding: 2px 2px 0 2px;
  margin: 6px 0 10px 0;
}
.assistant-avatar {
  min-width: 26px; min-height: 26px;
  background-color: alpha(@window_fg_color, 0.06);
  border: 1px solid alpha(@window_fg_color, 0.08);
}
.assistant-card.ativo .assistant-avatar { animation: respirar 1.6s ease-in-out infinite; }
.assistant-name { font-weight: 650; font-size: 13.5px; }
.model-badge {
  background-color: alpha(@window_fg_color, 0.06);
  color: alpha(@window_fg_color, 0.70);
  font-weight: 500;
}
.msg-time { opacity: 0.45; }
.msg-body { font-size: 15px; }
.msg-actions {
  border-top: none;
  margin-top: 2px;
  padding-top: 0;
  opacity: 0.55;
  transition: opacity 180ms ease;
}
.assistant-card:hover .msg-actions, .msg-actions:focus-within { opacity: 1; }
.action-button {
  min-height: 28px; min-width: 28px;
  padding: 0 7px;
  border-radius: 8px;
  color: alpha(@window_fg_color, 0.75);
}
.action-button:hover { background-color: alpha(@window_fg_color, 0.08); color: @window_fg_color; }
.action-button.copiado { color: @success_color; }
.duration-badge {
  background: none;
  color: alpha(@window_fg_color, 0.50);
  font-weight: 500;
  font-size: 11.5px;
  padding: 0 4px;
}

/* Mensagem do usuário: bolha suave à direita, ações aparecem ao passar o mouse */
.user-bubble {
  background-color: alpha(@window_fg_color, 0.065);
  border: none;
  border-radius: 20px 20px 6px 20px;
  padding: 11px 17px;
  box-shadow: none;
}
.msg-user-acoes { opacity: 0; transition: opacity 180ms ease; }
.msg-user-row:hover .msg-user-acoes, .msg-user-acoes:focus-within { opacity: 1; }

/* ---------- bloco "Pensando" ---------- */
.pensando { margin: 2px 0 6px 0; }
.pensando-cabecalho {
  background: none;
  padding: 4px 10px 4px 4px;
  border-radius: 10px;
  min-height: 28px;
  color: alpha(@window_fg_color, 0.62);
  transition: background-color 150ms ease, color 150ms ease;
}
.pensando-cabecalho:hover { background-color: alpha(@window_fg_color, 0.055); color: @window_fg_color; }
.pensando-cabecalho:checked { background: none; color: @window_fg_color; }
.pensando-atual { font-size: 14px; font-weight: 500; }
.pensando-tempo { font-size: 12.5px; color: alpha(@window_fg_color, 0.48); margin-left: 2px; }
.pensando-tempo.aviso { color: @warning_color; }
.pensando-icone { color: alpha(@window_fg_color, 0.55); }
.pensando-seta { opacity: 0.6; transition: opacity 150ms ease; }
.pensando-corpo {
  margin: 4px 0 6px 11px;
  padding: 2px 0 2px 16px;
  border-left: 2px solid alpha(@window_fg_color, 0.10);
}
.pensando-raciocinio-caixa { background: none; }
.pensando-raciocinio, .pensando-raciocinio text {
  background: none;
  color: alpha(@window_fg_color, 0.66);
  font-size: 14px;
}

/* passos da linha do tempo */
.passo-linha, .passo-cartao { animation: surgir-suave 220ms ease-out; }
.passo-linha { padding: 3px 0; }
.passo-cab { min-height: 26px; }
.passo-icone {
  min-width: 24px; min-height: 24px;
  border-radius: 999px;
  background-color: alpha(@window_fg_color, 0.06);
  color: alpha(@window_fg_color, 0.65);
}
.passo-titulo { font-size: 13.5px; color: alpha(@window_fg_color, 0.85); }
.passo-info { font-size: 12.5px; color: alpha(@window_fg_color, 0.50); }
.passo-dur { font-size: 11.5px; color: alpha(@window_fg_color, 0.42); font-feature-settings: "tnum"; }
.passo-linha.erro .passo-icone { background-color: alpha(@error_color, 0.14); color: @error_color; }
.passo-linha.negado .passo-titulo { text-decoration-line: line-through; opacity: .6; }
.passo-filhos { margin: 2px 0 2px 11px; padding-left: 14px; border-left: 1px dashed alpha(@window_fg_color, 0.14); }
.passo-mais {
  font-size: 12px; padding: 1px 8px; min-height: 22px;
  border-radius: 7px;
  color: alpha(@window_fg_color, 0.60);
}
.passo-mais:hover { color: @accent_color; background-color: alpha(@accent_bg_color, 0.08); }

/* cartão de ação no computador (comando / edição): parece um terminal */
.passo-cartao {
  margin: 4px 0;
  border-radius: 12px;
  border: 1px solid alpha(@window_fg_color, 0.10);
  background-color: alpha(@window_fg_color, 0.025);
  padding: 6px 8px 6px 6px;
}
.passo-cartao .passo-icone { background-color: alpha(@accent_bg_color, 0.14); color: @accent_color; }
.passo-cartao.erro { border-color: alpha(@error_color, 0.35); }
.passo-cartao.erro .passo-icone { background-color: alpha(@error_color, 0.14); color: @error_color; }
.passo-codigo {
  font-family: monospace;
  font-size: 12.5px;
  margin: 6px 0 2px 0;
  padding: 9px 12px;
  border-radius: 9px;
  background-color: alpha(@window_fg_color, 0.055);
}
.passo-estado {
  font-size: 11px; font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
}
.passo-estado.rodando { color: @accent_color; background-color: alpha(@accent_bg_color, 0.12); }
.passo-estado.auto { color: alpha(@window_fg_color, 0.62); background-color: alpha(@window_fg_color, 0.06); }
.passo-estado.ok { color: @success_color; background-color: alpha(@success_color, 0.12); }
.passo-estado.erro { color: @error_color; background-color: alpha(@error_color, 0.12); }
.passo-estado.negado, .passo-estado.parado { color: @warning_color; background-color: alpha(@warning_color, 0.12); }
.passo-botao { min-width: 26px; min-height: 26px; padding: 0; border-radius: 8px; }
.passo-botao.copiado { color: @success_color; }
.passo-saida-btn { font-size: 12px; padding: 1px 6px; min-height: 22px; border-radius: 7px; color: alpha(@window_fg_color, 0.60); }
.passo-saida {
  margin-top: 4px;
  border-radius: 9px;
  background-color: alpha(#000, 0.80);
  padding: 8px 12px;
}
.passo-saida-texto { font-family: monospace; font-size: 12px; color: #e6e6e6; }

/* trecho do raciocínio entre os passos */
.passo-pensamento { padding: 2px 0 6px 0; animation: surgir-suave 260ms ease-out; }
.pensamento-texto { font-size: 14px; color: alpha(@window_fg_color, 0.66); }
.pensamento-texto:selected { color: @window_fg_color; }

/* revisão de UI/UX: hierarquia, contraste e um só estilo de terminal */
.pensando-cabecalho label, .suggestion label, .pergunta-opcao label, .code-copy-btn label { font-weight: 500; }
.pensando-tempo { font-weight: 400; }
.pensando-cabecalho { padding-left: 6px; }
.msg-actions { opacity: 1; }
.msg-actions .action-button { opacity: .55; transition: opacity 180ms ease; }
.assistant-card:hover .action-button, .msg-actions .action-button:focus { opacity: 1; }
.duration-badge { color: alpha(@window_fg_color, 0.60); }
.passo-codigo { background-color: #1f2229; color: #e6e6e6; border-radius: 9px; }
.passo-saida { background-color: #1a1d23; border: 1px solid alpha(#fff, .06); }
.code-block-box { border: 1px solid alpha(@window_fg_color, 0.10); box-shadow: none; }
.code-copy-btn.icone { min-width: 28px; padding: 0 6px; }
.code-copy-btn.perigo:hover { color: #ffbe6f; }
.painel-codigo-view, .painel-codigo-view text { background-color: #1f2229; color: #e6e6e6; }
.pergunta-opcao { background: @view_bg_color; border: 1px solid alpha(@accent_bg_color, .35); padding: 6px 16px; }
.pergunta-opcao:hover { background-color: alpha(@accent_bg_color, .10); }
.pergunta-card entry { background: @view_bg_color; border: 1px solid alpha(@window_fg_color, .12); border-radius: 12px; }
.pergunta-card { margin-left: 2px; margin-right: 2px; }
.composer-hint { color: alpha(@window_fg_color, .55); }
.uso-pop-link { color: @accent_color; font-size: 13px; font-weight: 600; margin-top: 4px; }
levelbar.uso-medidor > trough { background-color: alpha(@window_fg_color, .08); }
levelbar.uso-medidor > trough > block.empty { background-color: transparent; }
.pensamento-texto { animation: surgir-suave 260ms ease-out; }

/* indicador de digitação, no fim da resposta */
.digitando { margin: 4px 0 2px 2px; min-height: 22px; }
.digitando-ponto {
  min-width: 6px; min-height: 6px;
  border-radius: 999px;
  background-color: @accent_bg_color;
  animation: pulsar 1.2s ease-in-out infinite;
}
.digitando-ponto.p2 { animation-delay: 160ms; }
.digitando-ponto.p3 { animation-delay: 320ms; }
.digitando-texto { font-size: 13px; color: alpha(@window_fg_color, 0.55); }

/* ---------- código: separado da conversa ---------- */
.code-block-box {
  background-color: #1f2229;
  border: 1px solid alpha(#000, 0.25);
  border-radius: 12px;
  margin: 6px 0;
  box-shadow: 0 1px 3px alpha(#000, 0.10);
}
.code-block-header {
  background-color: #2a2e37;
  border-bottom: 1px solid alpha(#fff, 0.06);
  border-radius: 11px 11px 0 0;
  padding: 2px 6px 2px 14px;
  min-height: 32px;
}
.code-block-lang { color: alpha(#fff, 0.62); font-size: 11.5px; font-weight: 600; }
.code-copy-btn { color: alpha(#fff, 0.70); font-size: 11.5px; min-height: 26px; }
.code-copy-btn:hover { background-color: alpha(#fff, 0.10); color: #fff; }
.code-copy-btn.copiado { color: #8ff0a4; }
.code-block-view, .code-block-view text { background-color: transparent; color: #e6e6e6; font-size: 13px; }
.code-block-mais {
  color: alpha(#fff, 0.70);
  border-top: 1px solid alpha(#fff, 0.06);
  border-radius: 0 0 11px 11px;
  font-size: 12px;
  min-height: 30px;
}
.code-block-mais:hover { background-color: alpha(#fff, 0.06); color: #fff; }

/* ---------- composer ---------- */
.composer-shell {
  background-color: @view_bg_color;
  border: 1px solid alpha(@window_fg_color, 0.12);
  border-radius: 24px;
  padding: 10px 12px 8px 12px;
  box-shadow: 0 4px 18px alpha(#000, 0.07), 0 1px 3px alpha(#000, 0.05);
  transition: border-color 160ms ease, box-shadow 200ms ease;
}
.composer-shell.focado {
  border-color: alpha(@accent_bg_color, 0.55);
  box-shadow: 0 0 0 3px alpha(@accent_bg_color, 0.14), 0 6px 22px alpha(#000, 0.08);
}
.send-button { transition: background-color 150ms ease, opacity 150ms ease; }
.send-button:not(:disabled):hover { background-color: shade(@accent_bg_color, 1.08); }

/* ---------- seletores (agente/modelo) ---------- */
menubutton.agent-pill > button, menubutton.model-chip > button {
  background: none; border: none; box-shadow: none;
  min-height: 30px; padding: 2px 10px; border-radius: 10px;
  font-weight: 600;
}
menubutton.agent-pill > button { font-size: 14px; }
menubutton.model-chip > button { font-size: 12.5px; color: alpha(@window_fg_color, 0.80); padding: 1px 8px; min-height: 28px; }
menubutton.agent-pill > button:hover, menubutton.model-chip > button:hover,
menubutton.agent-pill > button:checked, menubutton.model-chip > button:checked { background-color: alpha(@window_fg_color, 0.07); }
.agent-pill { background: none; border: none; padding: 0; margin: 0; }
.seletor-seta { opacity: 0.55; }
popover.seletor-pop > contents { padding: 6px; border-radius: 14px; }
.seletor-titulo { font-size: 11.5px; font-weight: 700; color: alpha(@window_fg_color, 0.50); margin: 4px 8px 2px 8px; }
.seletor-busca { margin: 2px 2px 4px 2px; }
.seletor-lista { background: none; }
.seletor-linha { border-radius: 10px; padding: 7px 10px; transition: background-color 120ms ease; }
.seletor-linha:hover { background-color: alpha(@window_fg_color, 0.06); }
.seletor-linha.atual { background-color: alpha(@accent_bg_color, 0.10); }
.seletor-linha.separar { margin-top: 2px; }
.seletor-nome { font-weight: 600; font-size: 13.5px; }
.seletor-sub { font-size: 12px; color: alpha(@window_fg_color, 0.55); }
.seletor-marca { color: @accent_color; }
.seletor-aviso {
  font-size: 11px; font-weight: 600; color: @warning_color;
  background-color: alpha(@warning_color, 0.12);
  border-radius: 999px; padding: 1px 8px;
}

/* ---------- uso do limite (estilo Claude: anel + barras com contagem) ---------- */
.uso-chip { border-radius: 10px; padding: 1px 8px; min-height: 28px; font-size: 12px; font-weight: 600; color: alpha(@window_fg_color, 0.70); }
.uso-chip:hover { background-color: alpha(@window_fg_color, 0.07); }
.uso-chip.uso-alto { color: @warning_color; }
.uso-chip.uso-critico { color: @error_color; }
popover.uso-pop > contents { padding: 14px 16px; border-radius: 16px; }
.uso-pop-titulo { font-weight: 700; font-size: 14px; }
.uso-pop-linha-titulo { font-weight: 600; font-size: 13px; }
.uso-pop-sub { font-size: 12px; color: alpha(@window_fg_color, 0.58); }
.uso-pop-pct { font-size: 12.5px; font-weight: 700; font-feature-settings: "tnum"; }
.uso-pop-nota { font-size: 11.5px; color: alpha(@window_fg_color, 0.50); }

/* ---------- pergunta do agente (botões de resposta) ---------- */
.pergunta-card {
  border: 1px solid alpha(@accent_bg_color, 0.35);
  background-color: alpha(@accent_bg_color, 0.06);
  border-radius: 16px;
  padding: 14px 16px;
  margin: 4px 0 8px 0;
  animation: surgir 320ms cubic-bezier(.2,.8,.2,1);
}
.pergunta-titulo { font-weight: 650; font-size: 14.5px; }
.pergunta-rotulo { font-size: 11.5px; font-weight: 700; color: @accent_color; }
.pergunta-opcao { border-radius: 999px; padding: 4px 14px; }
.pergunta-card.respondida { border-color: alpha(@window_fg_color, 0.10); background-color: alpha(@window_fg_color, 0.03); }

/* ---------- painel lateral de código (canvas) ---------- */
.painel-codigo { border-left: 1px solid alpha(@window_fg_color, 0.10); background-color: @view_bg_color; }
.painel-codigo-barra { padding: 6px 8px 6px 14px; border-bottom: 1px solid alpha(@window_fg_color, 0.08); }
.painel-codigo-titulo { font-weight: 700; font-size: 13.5px; }
.painel-codigo-sub { font-size: 11.5px; color: alpha(@window_fg_color, 0.55); }
.painel-codigo-view, .painel-codigo-view text { font-family: monospace; font-size: 13px; }
.painel-abas { padding: 4px 8px; border-bottom: 1px solid alpha(@window_fg_color, 0.06); }
.painel-aba { font-size: 12px; border-radius: 8px; padding: 2px 10px; min-height: 26px; }
.painel-aba:checked { background-color: alpha(@accent_bg_color, 0.14); color: @accent_color; }

/* estado vazio com entrada suave */
.empty-state { animation: surgir 420ms cubic-bezier(.2,.8,.2,1); }
.empty-title { font-size: 28px; font-weight: 750; letter-spacing: -0.3px; }
.suggestion { transition: background-color 150ms ease, border-color 150ms ease; border-radius: 14px; padding: 9px 16px; }

/* modo livre: comandos rodaram no computador */
.acoes-pc {
  font-size: 11.5px; font-weight: 600;
  color: alpha(@window_fg_color, 0.62);
  background-color: alpha(@window_fg_color, 0.05);
  border-radius: 999px; padding: 1px 9px;
}
.acoes-pc.root { color: @warning_color; background-color: alpha(@warning_color, 0.12); }
"""
