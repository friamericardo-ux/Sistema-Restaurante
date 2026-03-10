// ── Caixa JS — Polling + Gráfico + Fechamento ──

let dadosResumo = null;

function formatarReais(valor) {
  return 'R$ ' + valor.toFixed(2).replace('.', ',');
}

function extrairHora(timestamp) {
  if (!timestamp) return '--:--';
  const str = String(timestamp);
  // Tenta pegar HH:MM do timestamp
  const match = str.match(/(\d{2}:\d{2})/);
  return match ? match[1] : str.slice(11, 16);
}

// ── Carregar resumo ──
async function carregarResumo() {
  try {
    const res = await fetch('/api/caixa/resumo');
    const data = await res.json();
    if (!data.sucesso) return;

    dadosResumo = data;

    document.getElementById('val-delivery').textContent = formatarReais(data.total_delivery);
    document.getElementById('val-mesas').textContent = formatarReais(data.total_mesas);
    document.getElementById('val-total').textContent = formatarReais(data.total_geral);
    document.getElementById('qtd-delivery').textContent = data.qtd_delivery;
    document.getElementById('qtd-mesas').textContent = data.qtd_mesas;

    const statusDiv = document.getElementById('caixa-status');
    const btnFechar = document.getElementById('btn-fechar');

    if (data.caixa_fechado) {
      statusDiv.style.display = 'block';
      statusDiv.className = 'caixa-status fechado';
      document.getElementById('caixa-status-texto').textContent =
        '🔒 Caixa fechado por ' + data.fechamento.fechado_por;
      btnFechar.disabled = true;
      btnFechar.textContent = '🔒 Caixa já fechado';
    } else {
      statusDiv.style.display = 'block';
      statusDiv.className = 'caixa-status aberto';
      document.getElementById('caixa-status-texto').textContent = '✅ Caixa aberto';
      btnFechar.disabled = false;
      btnFechar.textContent = '🔒 Fechar Caixa do Dia';
    }
  } catch (e) {
    console.error('Erro ao carregar resumo:', e);
  }
}

// ── Carregar movimentações ──
async function carregarMovimentacoes() {
  try {
    const res = await fetch('/api/caixa/movimentacoes');
    const data = await res.json();
    if (!data.sucesso) return;

    const tbody = document.getElementById('tabela-movimentacoes');

    if (!data.movimentacoes.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="sem-dados">Nenhuma movimentação hoje.</td></tr>';
      return;
    }

    tbody.innerHTML = data.movimentacoes.map(m => {
      const hora = extrairHora(m.hora);
      const badgeClass = m.tipo === 'delivery' ? 'delivery' : 'mesa';
      const badgeText = m.tipo === 'delivery' ? '🛵 Delivery' : '🍽️ Mesa';
      const descricao = escapeHtml(m.descricao);
      return `<tr>
        <td>${hora}</td>
        <td><span class="badge-tipo ${badgeClass}">${badgeText}</span></td>
        <td>${descricao}</td>
        <td class="valor-positivo">${formatarReais(m.valor)}</td>
      </tr>`;
    }).join('');
  } catch (e) {
    console.error('Erro ao carregar movimentações:', e);
  }
}

// ── Carregar gráfico ──
async function carregarGrafico() {
  try {
    const res = await fetch('/api/caixa/grafico');
    const data = await res.json();
    if (!data.sucesso) return;

    const container = document.getElementById('grafico-horas');
    const maxValor = Math.max(...data.horas.map(h => h.total), 1);

    container.innerHTML = data.horas.map(h => {
      const pct = (h.total / maxValor) * 100;
      const alturaMin = h.total > 0 ? Math.max(pct, 3) : 0;
      const valorLabel = h.total > 0 ? formatarReais(h.total) : '';
      return `<div class="barra-hora">
        <div class="barra-valor">${valorLabel}</div>
        <div class="barra-fill" style="height:${alturaMin}%" title="${h.hora}h — ${formatarReais(h.total)}"></div>
        <div class="barra-label">${String(h.hora).padStart(2, '0')}</div>
      </div>`;
    }).join('');
  } catch (e) {
    console.error('Erro ao carregar gráfico:', e);
  }
}

// ── Modal fechar caixa ──
function confirmarFechamento() {
  if (!dadosResumo || dadosResumo.caixa_fechado) return;

  const modal = document.getElementById('modal-fechar');
  const resumo = document.getElementById('modal-resumo');

  resumo.innerHTML = `
    <div class="linha"><span>🛵 Delivery (${dadosResumo.qtd_delivery})</span><span>${formatarReais(dadosResumo.total_delivery)}</span></div>
    <div class="linha"><span>🍽️ Mesas (${dadosResumo.qtd_mesas})</span><span>${formatarReais(dadosResumo.total_mesas)}</span></div>
    <div class="linha total"><span>💰 Total Geral</span><span>${formatarReais(dadosResumo.total_geral)}</span></div>
  `;

  modal.style.display = 'flex';
}

function fecharModal() {
  document.getElementById('modal-fechar').style.display = 'none';
}

async function executarFechamento() {
  try {
    const res = await fetch('/api/caixa/fechar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();

    if (data.sucesso) {
      fecharModal();
      carregarResumo();
      carregarMovimentacoes();
      carregarGrafico();
    } else {
      alert(data.erro || 'Erro ao fechar caixa.');
    }
  } catch (e) {
    console.error('Erro ao fechar caixa:', e);
    alert('Erro de conexão.');
  }
}

// ── Escape HTML ──
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Inicialização ──
carregarResumo();
carregarMovimentacoes();
carregarGrafico();
setInterval(() => {
  carregarResumo();
  carregarMovimentacoes();
  carregarGrafico();
}, 15000);
