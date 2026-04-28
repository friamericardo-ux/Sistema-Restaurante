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
    console.log('[DEBUG CAIXA] Resumo:', data);
    if (!data.sucesso) return;

    dadosResumo = data;

    document.getElementById('val-delivery').textContent = formatarReais(data.total_delivery);
    document.getElementById('val-mesas').textContent = formatarReais(data.total_mesas);
    document.getElementById('val-total').textContent = formatarReais(data.total_geral);
    document.getElementById('qtd-delivery').textContent = data.qtd_delivery;
    document.getElementById('qtd-mesas').textContent = data.qtd_mesas;
    document.getElementById('val-taxa-entrega').textContent = formatarReais(data.taxa_entrega_total || 0);
    document.getElementById('qtd-entregas-taxa').textContent = data.qtd_entregas_taxa || 0;

    const statusDiv = document.getElementById('caixa-status');
    const btnFechar = document.getElementById('btn-fechar');

    const historicoSection = document.getElementById('historico-section');

    if (data.caixa_fechado) {
      statusDiv.style.display = 'block';
      statusDiv.className = 'caixa-status fechado';
      document.getElementById('caixa-status-texto').textContent =
        '🔒 Caixa fechado por ' + data.fechamento.fechado_por;
      btnFechar.disabled = false;
      btnFechar.style.cursor = 'pointer';
      btnFechar.textContent = '🔓 Abrir Caixa';
      btnFechar.onclick = abrirCaixa;
      if (historicoSection.style.display === 'none') {
        historicoSection.style.display = 'block';
        carregarHistorico();
      }
    } else {
      statusDiv.style.display = 'block';
      statusDiv.className = 'caixa-status aberto';
      document.getElementById('caixa-status-texto').textContent = '✅ Caixa aberto';
      btnFechar.disabled = false;
      btnFechar.style.cursor = 'pointer';
      btnFechar.textContent = '🔒 Fechar Caixa do Dia';
      btnFechar.onclick = confirmarFechamento;
      historicoSection.style.display = 'none';
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

// ── Abrir caixa ──
async function abrirCaixa() {
  if (!confirm('Deseja reabrir o caixa?')) return;
  try {
    const res = await fetch('/api/caixa/abrir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.sucesso) {
      carregarResumo();
      carregarMovimentacoes();
      carregarGrafico();
    } else {
      alert(data.erro || 'Erro ao abrir caixa.');
    }
  } catch (e) {
    console.error('Erro ao abrir caixa:', e);
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

// ── Histórico mensal ──
const MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
               'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];

function inicializarFiltros() {
  const agora = new Date();
  const selMes = document.getElementById('filtro-mes');
  const selAno = document.getElementById('filtro-ano');

  selMes.innerHTML = MESES.map((nome, i) => {
    const val = String(i + 1).padStart(2, '0');
    const sel = (i + 1 === agora.getMonth() + 1) ? ' selected' : '';
    return `<option value="${val}"${sel}>${nome}</option>`;
  }).join('');

  for (let y = agora.getFullYear(); y >= agora.getFullYear() - 3; y--) {
    const opt = document.createElement('option');
    opt.value = y;
    opt.textContent = y;
    if (y === agora.getFullYear()) opt.selected = true;
    selAno.appendChild(opt);
  }
}

async function carregarHistorico() {
  const mes = document.getElementById('filtro-mes').value;
  const ano = document.getElementById('filtro-ano').value;
  const tbody = document.getElementById('tabela-historico');
  const tfoot = document.getElementById('historico-rodape');

  tbody.innerHTML = '<tr><td colspan="5" class="sem-dados">Carregando...</td></tr>';
  tfoot.style.display = 'none';

  try {
    const res = await fetch(`/api/caixa/historico?mes=${mes}&ano=${ano}`);
    const data = await res.json();
    if (!data.sucesso) return;

    if (!data.fechamentos.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="sem-dados">Nenhum fechamento neste período.</td></tr>';
      return;
    }

    tbody.innerHTML = data.fechamentos.map(f => {
      const data_fmt = f.data ? f.data.slice(8, 10) + '/' + f.data.slice(5, 7) + '/' + f.data.slice(0, 4) : f.data;
      return `<tr>
        <td>${data_fmt}</td>
        <td>${f.total_pedidos}</td>
        <td>${f.total_entregas}</td>
        <td class="valor-positivo">${formatarReais(f.valor_entregas)}</td>
        <td class="valor-positivo">${formatarReais(f.total_faturado)}</td>
      </tr>`;
    }).join('');

    const t = data.totais;
    document.getElementById('hist-total-pedidos').textContent = t.total_pedidos;
    document.getElementById('hist-total-entregas').textContent = t.total_entregas;
    document.getElementById('hist-valor-entregas').innerHTML = `<strong>${formatarReais(t.valor_entregas)}</strong>`;
    document.getElementById('hist-total-faturado').innerHTML = `<strong>${formatarReais(t.total_faturado)}</strong>`;
    tfoot.style.display = '';
  } catch (e) {
    console.error('Erro ao carregar histórico:', e);
  }
}

// ── Inicialização ──
inicializarFiltros();
carregarResumo();
carregarMovimentacoes();
carregarGrafico();
setInterval(() => {
  carregarResumo();
  carregarMovimentacoes();
  carregarGrafico();
}, 15000);
