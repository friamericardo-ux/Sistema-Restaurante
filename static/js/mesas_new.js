/* ============================================================
   Comanda Digital — Mesas (mesas_new.js)
   Lógica exclusiva da página admin_mesas.html.
   Integra com as APIs existentes:
     GET  /api/mesas
     POST /api/mesa/abrir
     POST /api/mesa/item
     POST /api/mesa/item/remover
     POST /api/mesa/fechar
     GET  /api/cardapio
     GET  /api/adicionais?categoria=X
============================================================ */

'use strict';

/* ── Estado ────────────────────────────────────────────── */
let _mesaAtual = null;   // número da mesa aberta no modal
let _itemSelecionado = null;   // produto pendente de adicionais
let _intervalId = null;   // ID do único setInterval de polling

/* ── Helpers ────────────────────────────────────────────── */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

function fmtBRL(valor) {
    return 'R$ ' + parseFloat(valor || 0).toFixed(2);
}

/* ── Determina o status visual de uma mesa ─────────────── */
function getStatusMesa(mesa) {
    if (!mesa) return 'livre';
    if (mesa.status === 'conta_pedida' || mesa.pediu_conta) return 'conta_pedida';
    if (mesa.status === 'ocupada' || parseFloat(mesa.total) > 0) return 'ocupada';
    if (mesa.status === 'aberta') return 'aberta';
    return 'livre';
}

function getLabelStatus(status) {
    const map = {
        livre: 'Livre',
        aberta: 'Aberta',
        ocupada: 'Ocupada',
        conta_pedida: 'Conta Pedida',
    };
    return map[status] || status;
}

/* ── Renderizar grid de mesas ──────────────────────────── */
async function renderizarMesas() {
    const container = document.getElementById('mesas-grid');
    if (!container) return;

    try {
        const res = await fetch('/api/mesas');
        const data = await res.json();

        const filtro = (document.getElementById('mesas-busca')?.value || '').trim().toLowerCase();

        if (!data.sucesso || !data.mesas || data.mesas.length === 0) {
            container.innerHTML = `
                <div class="mesas-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                        <polyline points="9 22 9 12 15 12 15 22"/>
                    </svg>
                    <h3>Nenhuma mesa aberta</h3>
                    <p>Clique em "+ Nova Mesa" para começar.</p>
                </div>`;
            atualizarContadores({ mesas: [] });
            return;
        }

        // Aplica filtro de busca
        const mesas = filtro
            ? data.mesas.filter(m => String(m.numero).toLowerCase().includes(filtro))
            : data.mesas;

        if (mesas.length === 0) {
            container.innerHTML = `
                <div class="mesas-empty">
                    <h3>Nenhuma mesa encontrada</h3>
                    <p>Tente outro número na busca.</p>
                </div>`;
            return;
        }

        // Ordena: conta_pedida > ocupadas > abertas
        mesas.sort((a, b) => {
            const order = { conta_pedida: 0, ocupada: 1, aberta: 2, livre: 3 };
            return (order[getStatusMesa(a)] ?? 99) - (order[getStatusMesa(b)] ?? 99);
        });

        const userRole = typeof USER_ROLE !== 'undefined' ? USER_ROLE : 'admin';
        const podeFechar = ['admin', 'caixa', 'superadmin', 'super_admin'].includes(userRole);
        const podePedirConta = !podeFechar;

        container.innerHTML = mesas.map(m => {
            const status = getStatusMesa(m);
            const qtdItens = m.itens ? m.itens.length : 0;
            let botoes = '';

            if (status === 'conta_pedida') {
                if (podeFechar) {
                    botoes = `
                        <button class="btn-mesa-action ver" onclick="event.stopPropagation(); abrirModal('${m.numero}')" title="Ver consumo">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            Ver
                        </button>
                        <button class="btn-mesa-action fechar" onclick="event.stopPropagation(); fecharMesaPorId(${m.id})" title="Fechar Mesa">
                            🔒 Fechar
                        </button>`;
                } else {
                    botoes = `
                        <button class="btn-mesa-action ver" onclick="event.stopPropagation(); abrirModal('${m.numero}')" title="Ver consumo">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            Ver
                        </button>
                        <button class="btn-mesa-action conta" title="Aguardando fechamento" style="cursor: not-allowed; opacity: 0.6;">
                            ⏳ Conta Pedida
                        </button>`;
                }
            } else if (status === 'ocupada' || status === 'aberta') {
                if (podePedirConta) {
                    botoes = `
                        <button class="btn-mesa-action ver" onclick="event.stopPropagation(); abrirModal('${m.numero}')" title="Ver consumo">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            Ver
                        </button>
                        <button class="btn-mesa-action conta" onclick="event.stopPropagation(); pedirContaPorId(${m.id})" title="Pedir Conta">
                            🧾 Pedir Conta
                        </button>`;
                } else {
                    botoes = `
                        <button class="btn-mesa-action ver" onclick="event.stopPropagation(); abrirModal('${m.numero}')" title="Ver consumo">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            Ver
                        </button>
                        <button class="btn-mesa-action fechar" onclick="event.stopPropagation(); confirmarFechamento('${m.numero}')" title="Encerrar mesa">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                            Encerrar
                        </button>`;
                }
            } else {
                botoes = `
                    <button class="btn-mesa-action abrir" onclick="event.stopPropagation(); abrirModal('${m.numero}')" title="Abrir Mesa">
                        ➕ Abrir
                    </button>`;
            }

            return `
            <div class="mesa-card-new ${status}" id="mesa-card-${m.numero}"
                 role="button" tabindex="0"
                 aria-label="Mesa ${m.numero} — ${getLabelStatus(status)}"
                 onclick="abrirModal('${m.numero}')"
                 onkeydown="if(event.key==='Enter')abrirModal('${m.numero}')">
                <div class="mesa-card-body">
                    <div class="mesa-numero">Mesa ${escapeHtml(m.numero)}</div>
                    <span class="mesa-status-badge ${status}">${getLabelStatus(status)}</span>
                    <div class="mesa-itens-count">${qtdItens} item${qtdItens !== 1 ? 's' : ''}</div>
                    <div class="mesa-total">${fmtBRL(m.total)}</div>
                </div>
                <div class="mesa-card-footer">
                    ${botoes}
                </div>
            </div>`;
        }).join('');

        atualizarContadores(data);
    } catch (err) {
        console.error('[mesas_new] Erro ao renderizar mesas:', err);
    }
}

/* ── Atualiza os counters no top-bar ──────────────────── */
function atualizarContadores(data) {
    const total = document.getElementById('contador-total');
    const abertas = document.getElementById('contador-abertas');
    const ocupadas = document.getElementById('contador-ocupadas');
    if (!total) return;

    const mesas = data.mesas || [];
    total.textContent = mesas.length;
    if (abertas) abertas.textContent = mesas.filter(m => getStatusMesa(m) === 'aberta').length;
    if (ocupadas) ocupadas.textContent = mesas.filter(m => getStatusMesa(m) === 'ocupada').length;
}

/* ── Polling único (30s) ───────────────────────────────── */
function iniciarPolling() {
    if (_intervalId) clearInterval(_intervalId);
    _intervalId = setInterval(renderizarMesas, 30000);
}

/* ── Nova Mesa ─────────────────────────────────────────── */
function abrirModalNovaMesa() {
    const num = prompt('Digite o número da mesa:');
    if (!num || !num.trim()) return;

    fetch('/api/mesa/abrir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero: num.trim() })
    })
        .then(r => r.json())
        .then(data => {
            if (data.sucesso) {
                renderizarMesas();
            } else {
                alert('Erro: ' + (data.erro || 'Não foi possível abrir a mesa.'));
            }
        })
        .catch(err => {
            console.error('[mesas_new] Erro ao abrir mesa:', err);
        });
}

/* ── Encerrar Mesa (com confirm) ───────────────────────── */
function confirmarFechamento(numMesa) {
    if (!confirm(`Encerrar a Mesa ${numMesa}? Todos os itens serão apagados.`)) return;
    fecharMesa(numMesa);
}

function fecharMesa(numMesa) {
    fetch('/api/mesa/fechar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero: numMesa })
    })
        .then(r => r.json())
        .then(data => {
            if (data.sucesso) {
                fecharModal();
                renderizarMesas();
            } else {
                alert('Erro: ' + (data.erro || 'Não foi possível encerrar a mesa.'));
            }
        });
}

function pedirContaPorId(mesaId) {
    if (!confirm('Pedir a conta desta mesa?')) return;
    fetch(`/api/mesa/pedir-conta/${mesaId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(r => r.json())
        .then(data => {
            if (data.sucesso) {
                fecharModal();
                renderizarMesas();
            } else {
                alert('Erro: ' + (data.erro || 'Não foi possível pedir a conta.'));
            }
        });
}

function pedirContaPeloModal() {
    if (!_mesaAtual) return;
    fetch('/api/mesas')
      .then(r => r.json())
      .then(data => {
         const m = (data.mesas || []).find(x => String(x.numero) === String(_mesaAtual));
         if (m) pedirContaPorId(m.id);
      });
}

function fecharMesaPorId(mesaId) {
    if (!confirm('Fechar esta mesa? Todos os itens serão apagados.')) return;
    fetch(`/api/mesa/fechar/${mesaId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(r => r.json())
        .then(data => {
            if (data.sucesso) {
                renderizarMesas();
            } else {
                alert('Erro: ' + (data.erro || 'Não foi possível fechar a mesa.'));
            }
        });
}

/* ═══════════════════════════════════════════════════════
   MODAL — consumo da mesa
═══════════════════════════════════════════════════════ */

async function abrirModal(numMesa) {
    _mesaAtual = numMesa;
    document.getElementById('modal-titulo').textContent = '🍽️ Mesa ' + numMesa;

    // Zera área de adicionais
    _itemSelecionado = null;
    const adicionaisArea = document.getElementById('modal-adicionais-area');
    if (adicionaisArea) {
        adicionaisArea.classList.remove('ativo');
        document.getElementById('modal-adicionais-lista').innerHTML = '';
    }

    document.getElementById('modal-overlay').classList.add('ativo');

    // Carrega dados em paralelo
    await Promise.all([
        montarCardapioModal(),
        atualizarConsumoModal(numMesa)
    ]);
}

function fecharModal() {
    document.getElementById('modal-overlay').classList.remove('ativo');
    _mesaAtual = null;
    _itemSelecionado = null;
    renderizarMesas();
}

/* ── Cardápio no modal ─────────────────────────────────── */
async function montarCardapioModal() {
    const grid = document.getElementById('modal-cardapio-grid');
    if (!grid) return;
    grid.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Carregando...</span>';
    try {
        const res = await fetch('/api/cardapio');
        const data = await res.json();
        grid.innerHTML = '';
        if (!data.sucesso || !data.produtos.length) {
            grid.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Nenhum produto cadastrado.</span>';
            return;
        }
        data.produtos.forEach(p => {
            const btn = document.createElement('button');
            btn.className = 'modal-produto-btn';
            btn.dataset.nome = p.nome;
            btn.dataset.preco = p.preco;
            btn.dataset.categoria = p.categoria || '';
            btn.dataset.descricao = p.descricao || '';
            btn.innerHTML = `
                <span class="modal-produto-nome">${escapeHtml((p.emoji ? p.emoji + ' ' : '') + p.nome)}</span>
                <span class="modal-produto-preco">${fmtBRL(p.preco)}</span>`;
            btn.addEventListener('click', () => selecionarProduto({
                nome: p.nome, preco: parseFloat(p.preco),
                categoria: p.categoria || '', descricao: p.descricao || ''
            }));
            grid.appendChild(btn);
        });
    } catch (e) {
        grid.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Erro ao carregar produtos.</span>';
    }
}

/* ── Adicionais do produto selecionado ─────────────────── */
async function selecionarProduto(produto) {
    _itemSelecionado = { nome: produto.nome, preco: produto.preco };
    document.getElementById('modal-adicionais-produto-label').textContent =
        `${produto.nome}  —  ${fmtBRL(produto.preco)}`;
    const lista = document.getElementById('modal-adicionais-lista');
    lista.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Carregando adicionais...</span>';
    document.getElementById('modal-adicionais-area').classList.add('ativo');

    try {
        const url = '/api/adicionais' + (produto.categoria ? `?categoria=${encodeURIComponent(produto.categoria)}` : '');
        const res = await fetch(url);
        const data = await res.json();
        lista.innerHTML = '';
        if (data.sucesso && data.adicionais.length > 0) {
            data.adicionais.forEach(a => {
                const label = document.createElement('label');
                label.className = 'modal-adicional-chip';
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.dataset.nome = a.nome;
                cb.dataset.preco = a.preco;
                label.appendChild(cb);
                label.appendChild(document.createTextNode(
                    a.nome + (parseFloat(a.preco) > 0 ? `  +${fmtBRL(a.preco)}` : '')
                ));
                lista.appendChild(label);
            });
        } else {
            lista.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Sem adicionais para esta categoria.</span>';
        }
    } catch (e) {
        lista.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">Erro ao carregar adicionais.</span>';
    }
}

/* Confirma item com adicionais marcados + observação */
function confirmarItemComAdicionais() {
    if (!_itemSelecionado) return;
    const checks = document.querySelectorAll('#modal-adicionais-lista input[type=checkbox]:checked');
    const adicionais = Array.from(checks).map(cb => ({ nome: cb.dataset.nome, preco: parseFloat(cb.dataset.preco) }));

    let nomeCompleto = _itemSelecionado.nome;
    let precoTotal = _itemSelecionado.preco;

    if (adicionais.length > 0) {
        nomeCompleto += ' (+ ' + adicionais.map(a => a.nome).join(', ') + ')';
        precoTotal += adicionais.reduce((s, a) => s + a.preco, 0);
    }

    const observacao = (document.getElementById('modal-observacao')?.value || '').trim();

    cancelarAdicionais();
    enviarItem(nomeCompleto, precoTotal, 1, null, observacao);
}

function cancelarAdicionais() {
    _itemSelecionado = null;
    const area = document.getElementById('modal-adicionais-area');
    if (area) area.classList.remove('ativo');
    const lista = document.getElementById('modal-adicionais-lista');
    if (lista) lista.innerHTML = '';
    const obs = document.getElementById('modal-observacao');
    if (obs) obs.value = '';
}

/* ── POST genérico de item (com observação) ──────────────── */
function enviarItem(nome, preco, quantidade, onSucesso, observacao) {
    fetch('/api/mesa/item', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero: _mesaAtual, nome, preco, quantidade, observacao: observacao || '' })
    })
        .then(r => r.json())
        .then(data => {
            if (data.sucesso) {
                if (onSucesso) onSucesso();
                atualizarConsumoModal(_mesaAtual);
            } else {
                alert('Erro: ' + (data.erro || 'Não foi possível adicionar o item.'));
            }
        });
}

/* ── Atualiza lista de itens no modal ──────────────────── */
async function atualizarConsumoModal(numMesa) {
    try {
        const res = await fetch('/api/mesas');
        const data = await res.json();
        const mesa = (data.mesas || []).find(m => String(m.numero) === String(numMesa));

        const lista = document.getElementById('modal-itens-lista');
        const total = document.getElementById('modal-total-valor');
        if (!lista) return;

        if (!mesa || !mesa.itens || mesa.itens.length === 0) {
            lista.innerHTML = '<div class="modal-item-linha" style="justify-content:center;color:var(--text-muted);font-size:0.85rem;">Nenhum item ainda.</div>';
            if (total) total.textContent = fmtBRL(0);
            return;
        }

        lista.innerHTML = mesa.itens.map(item => {
            const obs = item.observacao ? escapeHtml(item.observacao) : '';
            return `
            <div class="modal-item-linha">
                <div class="modal-item-info">
                    <span class="modal-item-nome">${escapeHtml(item.quantidade)}x ${escapeHtml(item.nome)}</span>
                    ${obs ? `<span class="modal-item-obs">📝 ${obs}</span>` : ''}
                </div>
                <span class="modal-item-preco">${fmtBRL(item.preco * item.quantidade)}</span>
                <button class="btn-remover-item" onclick="removerItem(${item.id})" title="Remover item">✕</button>
            </div>`;
        }).join('');

        if (total) total.textContent = fmtBRL(mesa.total);
    } catch (err) {
        console.error('[mesas_new] Erro ao atualizar consumo:', err);
    }
}

/* ── Remover item ──────────────────────────────────────── */
function removerItem(id) {
    fetch('/api/mesa/item/remover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
    })
        .then(r => r.json())
        .then(data => {
            if (data.sucesso) {
                atualizarConsumoModal(_mesaAtual);
            } else {
                alert('Erro: ' + (data.erro || 'Não foi possível remover o item.'));
            }
        });
}

/* ── Inicialização ─────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    // Fecha modal ao clicar no backdrop
    document.getElementById('modal-overlay')?.addEventListener('click', e => {
        if (e.target.id === 'modal-overlay') fecharModal();
    });

    // Fecha modal com Esc
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && _mesaAtual) fecharModal();
    });

    // Busca em tempo real (não recria o interval)
    document.getElementById('mesas-busca')?.addEventListener('input', renderizarMesas);

    // Primeiro render + polling
    renderizarMesas();
    iniciarPolling();
});
