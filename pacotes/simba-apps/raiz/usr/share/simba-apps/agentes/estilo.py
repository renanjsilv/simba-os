"""Folha de estilo do chat dos Agentes de IA."""

CSS = """
@define-color simba_destaque @accent_color;
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
.passo-mais:hover { color: @simba_destaque; background-color: alpha(@accent_bg_color, 0.08); }

/* cartão de ação no computador (comando / edição): parece um terminal */
.passo-cartao {
  margin: 4px 0;
  border-radius: 12px;
  border: 1px solid alpha(@window_fg_color, 0.10);
  background-color: alpha(@window_fg_color, 0.025);
  padding: 6px 8px 6px 6px;
}
.passo-cartao .passo-icone { background-color: alpha(@accent_bg_color, 0.14); color: @simba_destaque; }
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
.passo-estado.rodando { color: @simba_destaque; background-color: alpha(@accent_bg_color, 0.12); }
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

/* imagem que o agente está lendo: miniatura clicável (abre o visualizador) */
.passo-imagem { animation: surgir-suave 240ms ease-out; }
.passo-imagem-botao {
  padding: 0;
  margin: 5px 0 4px 0;
  border-radius: 12px;
  border: 1px solid alpha(@window_fg_color, 0.14);
  background: none;
  box-shadow: 0 1px 5px alpha(#000, 0.10);
  transition: border-color 160ms ease, box-shadow 160ms ease;
}
.passo-imagem-botao:hover {
  border-color: alpha(@accent_bg_color, 0.60);
  box-shadow: 0 3px 12px alpha(#000, 0.20);
}
.passo-imagem-foto { border-radius: 11px; }
.passo-imagem-selo {
  margin: 7px;
  padding: 3px 10px 3px 8px;
  border-radius: 999px;
  background-color: alpha(#000, 0.64);
  color: #ffffff;
  font-size: 11.5px;
  font-weight: 600;
  opacity: 0.82;
  box-shadow: 0 1px 4px alpha(#000, 0.35);
  transition: opacity 160ms ease, background-color 160ms ease;
}
.passo-imagem-botao:hover .passo-imagem-selo,
.passo-imagem-botao:focus .passo-imagem-selo {
  opacity: 1;
  background-color: alpha(@accent_bg_color, 0.92);
}

/* visualizador da imagem (janela própria) */
window.visor-imagem { background-color: #0f1115; }
.visor-cabecalho {
  background-color: alpha(#0f1115, 0.96);
  border-bottom: 1px solid alpha(#ffffff, 0.08);
  box-shadow: none;
}
.visor-cabecalho button { color: alpha(#ffffff, 0.85); }
.visor-cabecalho button:hover { background-color: alpha(#ffffff, 0.10); }
.visor-titulo { color: #f6f6f6; font-weight: 600; }
.visor-corpo { background-color: #0f1115; padding: 10px 12px 6px 12px; }
.visor-rodape {
  color: alpha(#ffffff, 0.50);
  font-size: 11.5px;
  margin: 6px 2px 2px 2px;
  font-feature-settings: "tnum";
}
.visor-erro { color: alpha(#ffffff, 0.72); font-size: 14px; padding: 40px; }

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
.uso-pop-link { color: @simba_destaque; font-size: 13px; font-weight: 600; margin-top: 4px; }
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
.seletor-marca { color: @simba_destaque; }
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
.pergunta-rotulo { font-size: 11.5px; font-weight: 700; color: @simba_destaque; }
.pergunta-opcao { border-radius: 999px; padding: 4px 14px; }
/* pergunta no meio da resposta: fica no lugar em que foi feita */
.pergunta-card.na-resposta { margin: 10px 0 12px 0; }
.pergunta-card.respondida { border-color: alpha(@window_fg_color, 0.10); background-color: alpha(@window_fg_color, 0.03); }

/* ---------- painel lateral de código (canvas) ---------- */
.painel-codigo { border-left: 1px solid alpha(@window_fg_color, 0.10); background-color: @view_bg_color; }
.painel-codigo-barra { padding: 6px 8px 6px 14px; border-bottom: 1px solid alpha(@window_fg_color, 0.08); }
.painel-codigo-titulo { font-weight: 700; font-size: 13.5px; }
.painel-codigo-sub { font-size: 11.5px; color: alpha(@window_fg_color, 0.55); }
.painel-codigo-view, .painel-codigo-view text { font-family: monospace; font-size: 13px; }
.painel-abas { padding: 4px 8px; border-bottom: 1px solid alpha(@window_fg_color, 0.06); }
.painel-aba { font-size: 12px; border-radius: 8px; padding: 2px 10px; min-height: 26px; }
.painel-aba:checked { background-color: alpha(@accent_bg_color, 0.14); color: @simba_destaque; }

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

/* ================= painéis laterais (conversas / detalhes) ================= */
@keyframes entrar-lado { from { opacity: 0; margin-left: -10px; } to { opacity: 1; margin-left: 0; } }
@keyframes entrar-baixo { from { opacity: 0; margin-top: 6px; } to { opacity: 1; margin-top: 0; } }
@keyframes ponto-vivo {
  0%   { box-shadow: 0 0 0 0 alpha(@accent_bg_color, 0.55); }
  70%  { box-shadow: 0 0 0 5px alpha(@accent_bg_color, 0); }
  100% { box-shadow: 0 0 0 0 alpha(@accent_bg_color, 0); }
}
@keyframes borda-viva {
  0%   { border-color: alpha(@accent_bg_color, 0.22); }
  50%  { border-color: alpha(@accent_bg_color, 0.60); }
  100% { border-color: alpha(@accent_bg_color, 0.22); }
}

/* ---- conversas (esquerda) ---- */
.barra-conversas {
  background-color: @sidebar_bg_color;
  border-right: 1px solid alpha(@window_fg_color, 0.07);
  padding: 8px 0 0 0;
}
.barra-acoes { padding: 0 8px 6px 8px; }
.barra-acao {
  min-height: 36px;
  padding: 0 10px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 13.5px;
  color: alpha(@window_fg_color, 0.88);
  transition: background-color 160ms ease, color 160ms ease, border-color 160ms ease;
}
.barra-acao image { opacity: 0.80; transition: opacity 160ms ease; }
.barra-acao:hover { background-color: alpha(@window_fg_color, 0.07); color: @window_fg_color; }
.barra-acao:hover image { opacity: 1; }
.barra-acao:active { background-color: alpha(@window_fg_color, 0.11); }
.barra-acao:focus-visible { box-shadow: 0 0 0 2px alpha(@accent_bg_color, 0.45); }

/* ação principal: um tom do accent, sem competir com o conteúdo */
.barra-acao-nova {
  background-color: alpha(@accent_bg_color, 0.13);
  border: 1px solid alpha(@accent_bg_color, 0.22);
  box-shadow: none;
}
.barra-acao-nova:hover {
  background-color: alpha(@accent_bg_color, 0.19);
  border-color: alpha(@accent_bg_color, 0.32);
}
.barra-acao-nova:active { background-color: alpha(@accent_bg_color, 0.25); }
.barra-acao-nova image { color: @simba_destaque; opacity: 1; }

/* Procurar fica discreto ao lado da ação principal */
.barra-acao-icone {
  min-width: 36px;
  min-height: 36px;
  padding: 0;
  border-radius: 10px;
  color: alpha(@window_fg_color, 0.62);
}
.barra-acao-icone:hover { background-color: alpha(@window_fg_color, 0.07); color: @window_fg_color; }
.barra-acao-icone:focus-visible { box-shadow: 0 0 0 2px alpha(@accent_bg_color, 0.45); }

.barra-conversas-busca {
  margin: 2px 8px 4px 8px;
  min-height: 34px;
  border-radius: 10px;
  background-color: alpha(@window_fg_color, 0.055);
  border: 1px solid alpha(@window_fg_color, 0.07);
  box-shadow: none;
}
.barra-conversas-busca:focus-within {
  border-color: alpha(@accent_bg_color, 0.55);
  background-color: alpha(@window_fg_color, 0.04);
}
.barra-conversas-busca image { opacity: 0.50; }

/* nível 1: "Recentes" */
.barra-secao-caixa {
  padding: 8px 14px 6px 14px;
  border-bottom: 1px solid alpha(@window_fg_color, 0.06);
}
.barra-secao {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.55px;
  color: alpha(@window_fg_color, 0.48);
}
.barra-secao-contagem {
  font-size: 10.5px;
  font-weight: 600;
  font-feature-settings: "tnum";
  color: alpha(@window_fg_color, 0.36);
}

/* nível 2: grupos de data, alinhados com o texto dos títulos */
.barra-grupo-caixa { padding: 10px 6px 3px 6px; }
.barra-grupo-caixa.primeiro { padding-top: 6px; }
.barra-grupo {
  margin-left: 30px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: alpha(@window_fg_color, 0.36);
}

.barra-lista { background: none; padding: 0 4px 12px 4px; }
.barra-lista > row.barra-conversa {
  min-height: 44px;
  padding: 6px 3px 6px 6px;
  margin: 1px 0;
  border-radius: 10px;
  background: none;
  outline: none;
  animation: surgir-suave 200ms ease-out;
  transition: background-color 160ms ease, box-shadow 160ms ease;
}
.barra-lista > row.barra-conversa:hover { background-color: alpha(@window_fg_color, 0.055); }
.barra-lista > row.barra-conversa:selected {
  background-color: alpha(@accent_bg_color, 0.14);
  box-shadow: inset 2px 0 0 @accent_bg_color, inset 0 0 0 1px alpha(@accent_bg_color, 0.10);
}
.barra-lista > row.barra-conversa:selected:hover { background-color: alpha(@accent_bg_color, 0.18); }
.barra-lista > row.barra-conversa:focus-visible {
  box-shadow: inset 0 0 0 2px alpha(@accent_bg_color, 0.55);
}

/* identidade: logo do agente num chip pequeno e consistente */
.barra-conversa-avatar {
  min-width: 24px;
  min-height: 24px;
  border-radius: 7px;
  background-color: alpha(@window_fg_color, 0.055);
  border: 1px solid alpha(@window_fg_color, 0.07);
  transition: background-color 160ms ease, border-color 160ms ease;
}
/* ícone do chip: opacidade aplicada direto na imagem (set_opacity) */
row.barra-conversa:selected .barra-conversa-avatar {
  background-color: alpha(@accent_bg_color, 0.16);
  border-color: alpha(@accent_bg_color, 0.22);
}

.barra-conversa-titulo {
  font-size: 13px;
  font-weight: 550;
  color: alpha(@window_fg_color, 0.92);
}
.barra-conversa-sub {
  font-size: 11px;
  font-weight: 500;
  color: alpha(@window_fg_color, 0.50);
}
.barra-conversa-hora {
  font-size: 10.5px;
  font-weight: 500;
  font-feature-settings: "tnum";
  color: alpha(@window_fg_color, 0.46);
}
row.barra-conversa:selected .barra-conversa-titulo { color: @window_fg_color; font-weight: 600; }
row.barra-conversa:selected .barra-conversa-sub { color: alpha(@window_fg_color, 0.68); }
row.barra-conversa:selected .barra-conversa-hora { color: alpha(@simba_destaque, 0.90); }

/* menu em coluna fixa: o horário nunca anda quando o "…" aparece */
.barra-conversa-menu {
  min-width: 32px;
  min-height: 32px;
  padding: 0;
  border-radius: 8px;
  color: alpha(@window_fg_color, 0.55);
  opacity: 0;
  transition: opacity 150ms ease, background-color 150ms ease, color 150ms ease;
}
row.barra-conversa:hover .barra-conversa-menu,
row.barra-conversa:selected .barra-conversa-menu,
.barra-conversa-menu:checked,
.barra-conversa-menu:focus-within { opacity: 1; }
.barra-conversa-menu:hover {
  background-color: alpha(@window_fg_color, 0.08);
  color: @window_fg_color;
}
.barra-conversa-opcao {
  min-height: 32px;
  padding: 2px 10px;
  border-radius: 8px;
}
.barra-conversa-opcao:hover { background-color: alpha(@window_fg_color, 0.07); }

/* estado vazio: ícone discreto e uma frase, sem caixa tracejada */
.barra-vazio { padding: 24px 20px; }
.barra-vazio-icone { opacity: 0.38; }
.barra-vazio-texto {
  font-size: 12.5px;
  color: alpha(@window_fg_color, 0.54);
}

/* barra de rolagem discreta */
.barra-conversas scrollbar { background: none; border: none; }
.barra-conversas scrollbar trough { background: none; border: none; }
.barra-conversas scrollbar slider {
  min-width: 5px;
  min-height: 36px;
  border-radius: 999px;
  background-color: alpha(@window_fg_color, 0.16);
}
.barra-conversas scrollbar slider:hover { background-color: alpha(@window_fg_color, 0.28); }

/* ---- detalhes (direita) ---- */
.painel-detalhes {
  background-color: @sidebar_bg_color;
  border-left: 1px solid alpha(@window_fg_color, 0.07);
}
.detalhes-cab { padding: 10px 8px 4px 18px; min-height: 36px; }
.detalhes-titulo { font-size: 15px; font-weight: 700; letter-spacing: -0.1px; }
.detalhes-fechar {
  min-width: 30px; min-height: 30px; padding: 0;
  border-radius: 9px;
  opacity: 0.65;
  transition: opacity 150ms ease, background-color 150ms ease;
}
.detalhes-fechar:hover { opacity: 1; background-color: alpha(@window_fg_color, 0.08); }
.detalhes-conteudo { padding: 0 12px 14px 12px; }
.detalhes-secao { margin: 14px 4px 6px 4px; }
.detalhes-secao-titulo {
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.2px;
  color: alpha(@window_fg_color, 0.50);
}
label.detalhes-secao { margin: 14px 4px 6px 4px; }
.detalhes-cartao {
  background-color: alpha(@view_bg_color, 0.85);
  border: 1px solid alpha(@window_fg_color, 0.08);
  border-radius: 14px;
  padding: 4px;
  box-shadow: 0 1px 2px alpha(#000, 0.04);
  animation: entrar-baixo 320ms cubic-bezier(.2,.8,.2,1);
}
.detalhes-linha { min-height: 34px; padding: 0 10px; }
.detalhes-linha-botao {
  padding: 0; border-radius: 10px;
  transition: background-color 150ms ease;
}
.detalhes-linha-botao:hover { background-color: alpha(@window_fg_color, 0.06); }
.detalhes-linha-botao .detalhes-seta { opacity: 0; transition: opacity 150ms ease; }
.detalhes-linha-botao:hover .detalhes-seta { opacity: 0.55; }
.detalhes-icone { color: alpha(@window_fg_color, 0.60); }
.detalhes-valor { font-size: 13px; font-weight: 500; }
.detalhes-dica { font-size: 12px; color: alpha(@window_fg_color, 0.55); }
.detalhes-cartao .detalhes-dica { margin: 2px 10px 8px 10px; font-feature-settings: "tnum"; }
.detalhes-ctx-pct {
  font-size: 11.5px; font-weight: 700;
  font-feature-settings: "tnum";
  color: alpha(@window_fg_color, 0.62);
}
levelbar.detalhes-ctx-barra { margin: 10px 10px 4px 10px; }
levelbar.detalhes-ctx-barra > trough {
  min-height: 6px; padding: 0; border: none;
  border-radius: 999px;
  background-color: alpha(@window_fg_color, 0.08);
}
levelbar.detalhes-ctx-barra > trough > block { min-height: 6px; border: none; border-radius: 999px; }
levelbar.detalhes-ctx-barra > trough > block.filled { background-color: @accent_bg_color; }
levelbar.detalhes-ctx-barra > trough > block.empty { background-color: transparent; }
levelbar.detalhes-ctx-barra.alto > trough > block.filled { background-color: @warning_color; }
levelbar.detalhes-ctx-barra.critico > trough > block.filled { background-color: @error_color; }

/* cartões de agentes */
.detalhes-agentes { margin-bottom: 4px; }
.detalhes-agente {
  background-color: alpha(@view_bg_color, 0.85);
  border: 1px solid alpha(@window_fg_color, 0.08);
  border-radius: 14px;
  padding: 10px 12px;
  box-shadow: 0 1px 2px alpha(#000, 0.04);
  animation: entrar-baixo 320ms cubic-bezier(.2,.8,.2,1);
  transition: border-color 300ms ease, background-color 300ms ease;
}
.detalhes-agente.rodando {
  border-color: alpha(@accent_bg_color, 0.40);
  background-color: alpha(@accent_bg_color, 0.04);
  animation: entrar-baixo 320ms cubic-bezier(.2,.8,.2,1), borda-viva 2.4s ease-in-out 320ms infinite;
}
.detalhes-agente.erro { border-color: alpha(@error_color, 0.35); }
.detalhes-agente-avatar {
  padding: 7px;
  min-width: 16px; min-height: 16px;
  border-radius: 10px;
  background-color: alpha(@window_fg_color, 0.06);
}
.detalhes-agente.rodando .detalhes-agente-avatar { background-color: alpha(@accent_bg_color, 0.14); }
.detalhes-agente-nome { font-size: 13.5px; font-weight: 650; }
.detalhes-agente-papel { font-size: 11.5px; color: alpha(@window_fg_color, 0.50); }
.detalhes-agente-sub {
  font-size: 12px;
  color: alpha(@window_fg_color, 0.62);
  margin: 4px 0 0 40px;
}
.detalhes-agente .passo-estado { padding: 2px 9px 2px 7px; transition: background-color 300ms ease, color 300ms ease; }
.detalhes-ponto {
  min-width: 6px; min-height: 6px;
  border-radius: 999px;
  background-color: currentColor;
}
.passo-estado.rodando .detalhes-ponto { animation: ponto-vivo 1.6s ease-out infinite; }
.detalhes-sem-sub { margin: 2px 6px; }
.detalhes-vazio {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px dashed alpha(@window_fg_color, 0.14);
  color: alpha(@window_fg_color, 0.55);
  font-size: 12.5px;
  animation: surgir-suave 300ms ease-out;
}
.detalhes-vazio image { opacity: 0.7; }
.detalhes-sep { margin: 0; background-color: alpha(@window_fg_color, 0.07); min-height: 1px; }
.detalhes-resumo {
  margin: 0 4px 8px 4px;
  font-size: 12px; font-weight: 600;
  color: alpha(@window_fg_color, 0.62);
  font-feature-settings: "tnum";
}
.detalhes-racio { margin: 0 4px 8px 4px; font-size: 13px; }
.detalhes-linha-do-tempo { margin: 0 2px; }
.painel-detalhes .passo-cartao { margin: 4px 0; padding: 5px 6px 5px 5px; }
.painel-detalhes .passo-cartao .passo-estado { font-size: 10.5px; padding: 1px 6px; }
.painel-detalhes .passo-botao { min-width: 24px; min-height: 24px; }
.painel-detalhes .passo-codigo { font-size: 12px; padding: 8px 10px; }
.seletor-gratis {
  font-size: 10.5px; font-weight: 700;
  color: @success_color;
  background-color: alpha(@success_color, 0.13);
  border-radius: 999px; padding: 1px 8px;
}
"""


_destaque_prov = None


def _cor_destaque():
    """Cor de destaque legível sobre o fundo atual (claro ou escuro), calculada aqui.

    O @accent_color do libadwaita chegou a aparecer preto/branco em sessões reais
    (texto preto no tema escuro); com a cor calculada pelo próprio app isso não acontece.
    """
    from gi.repository import Adw
    estilo = Adw.StyleManager.get_default()
    escuro = estilo.get_dark()
    try:
        return Adw.AccentColor.to_standalone_rgba(estilo.get_accent_color(), escuro).to_string()
    except Exception:  # noqa: BLE001 — libadwaita antiga
        return "#78aeed" if escuro else "#1c71d8"


def aplicar_destaque(display):
    """Define @simba_destaque e o mantém em dia quando o tema ou a cor de destaque mudam."""
    global _destaque_prov
    from gi.repository import Adw, Gtk
    primeiro = _destaque_prov is None
    if primeiro:
        _destaque_prov = Gtk.CssProvider()
        # prioridade acima da folha do app: a definição vale para as regras dela
        Gtk.StyleContext.add_provider_for_display(display, _destaque_prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    _destaque_prov.load_from_data(f"@define-color simba_destaque {_cor_destaque()};".encode())
    if primeiro:
        estilo = Adw.StyleManager.get_default()
        for sinal in ("notify::dark", "notify::accent-color"):
            try:
                estilo.connect(sinal, lambda *_: aplicar_destaque(display))
            except TypeError:  # propriedade inexistente nesta versão
                pass
