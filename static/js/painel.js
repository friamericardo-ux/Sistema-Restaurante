/* ═══════════════════════════════════════
   Comanda Digital — Painel Admin
   static/js/painel.js
═══════════════════════════════════════ */

// ── WhatsApp ──────────────────────────────────────────────────────────────────
// Troca pelo número real do restaurante (DDI+DDD+número, sem + ou espaços)
// Exemplo: '5567999998888'
const WHATSAPP_NUMERO = '5567993487509';

function abrirWhatsApp() {
  const msg = encodeURIComponent('Olá! Aqui é o painel Comanda Digital.');
  window.open(`https://wa.me/${WHATSAPP_NUMERO}?text=${msg}`, '_blank');
}

// ── Relógio da última atualização ─────────────────────────────────────────────
function atualizarHorario() {
  const agora = new Date();
  const h = String(agora.getHours()).padStart(2, '0');
  const m = String(agora.getMinutes()).padStart(2, '0');
  const s = String(agora.getSeconds()).padStart(2, '0');
  const el = document.getElementById('subtitulo');
  if (el) el.textContent = `Última atualização: ${h}:${m}:${s} — atualiza a cada 30s`;
}

// ── Buscar dados reais via /api/dashboard/resumo ──────────────────────────────
async function carregarStatus() {
  try {
    const r = await fetch('/api/dashboard/resumo');
    if (!r.ok) return;
    const d = await r.json();

    // Checa se API retornou sucesso
    if (!d.sucesso) return;

    // Atualiza os 4 cards de status
    // Nomes dos campos batem exatamente com o que app.py retorna
    setValor('val-mesas',   d.mesas_abertas);
    setValor('val-novos',   d.pedidos_novos);
    setValor('val-preparo', d.pedidos_preparo);
    setValor('val-entrega', d.pedidos_entrega);

    // Badge delivery — soma todos os pedidos ativos
    const pendentes = (d.pedidos_novos || 0) + (d.pedidos_preparo || 0) + (d.pedidos_entrega || 0);
    const badge = document.getElementById('badge-delivery');
    if (badge) {
      if (pendentes > 0) {
        badge.className = 'badge-pill badge-warn';
        badge.textContent = `⚠ ${pendentes} pedido${pendentes > 1 ? 's' : ''} ativo${pendentes > 1 ? 's' : ''}`;
      } else {
        badge.className = 'badge-pill badge-ok';
        badge.textContent = '✓ Sem pedidos pendentes';
      }
    }

    atualizarHorario();

  } catch (e) {
    // Silencia — mantém valores anteriores na tela
  }
}

// Helper: só atualiza o elemento se o valor vier na resposta
function setValor(id, valor) {
  if (valor === undefined || valor === null) return;
  const el = document.getElementById(id);
  if (el) el.textContent = valor;
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  atualizarHorario();
  carregarStatus();
  setInterval(carregarStatus, 30000);
});