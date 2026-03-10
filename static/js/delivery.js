/* ============================================================
   DELIVERY — JavaScript do painel Kanban de pedidos
   (Sem flickering + status imediato)
============================================================ */

function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function formatarHora(dataStr) {
    const d = new Date(dataStr);
    return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function mostrarToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 3000);
}

const proximoStatus = {
    'novo':         { status: 'em_preparo',   label: '→ Iniciar preparo' },
    'em_preparo':   { status: 'saiu_entrega', label: '→ Saiu para entrega' },
    'saiu_entrega': { status: 'entregue',     label: '✓ Marcar entregue' }
};

function criarCard(pedido) {
    const div = document.createElement('div');
    div.className = 'card-pedido';
    div.id = `pedido-${pedido.id}`;
    div.dataset.status = pedido.status;

    const prox = proximoStatus[pedido.status];
    const itensHtml = pedido.itens.map(i =>
        `<div class="item-linha">
            <span><span class="item-qtd">${i.quantidade}x</span> ${escapeHtml(i.nome)}</span>
            <span>R$ ${(i.preco * i.quantidade).toFixed(2)}</span>
        </div>`
    ).join('');

    div.innerHTML = `
        <div class="card-header">
            <span class="pedido-id">#${pedido.id}</span>
            <span class="pedido-hora">${formatarHora(pedido.criado_em)}</span>
        </div>
        <div class="cliente-info">
            <div class="cliente-nome">&#128100; ${escapeHtml(pedido.cliente_nome)}</div>
            <div class="cliente-endereco">&#128205; ${escapeHtml(pedido.cliente_endereco || '—')}</div>
        </div>
        <div class="itens-lista">${itensHtml}</div>
        <div class="card-footer">
            <span class="total-pedido">R$ ${pedido.total.toFixed(2)}</span>
            <a href="/pedido/${pedido.id}/imprimir" target="_blank" class="btn-avancar" style="text-decoration:none;background:#555;">🖨️ Imprimir</a>
            ${prox ? `<button class="btn-avancar" onclick="avancarStatus(${pedido.id}, '${prox.status}')">${prox.label}</button>` : ''}
        </div>
    `;

    return div;
}

/* ── Avançar status com feedback imediato ── */
async function avancarStatus(pedido_id, novoStatus) {
    // Feedback visual imediato: remove o card da coluna atual
    const cardAtual = document.getElementById(`pedido-${pedido_id}`);
    if (cardAtual) cardAtual.remove();

    try {
        const res = await fetch('/api/pedido/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pedido_id, status: novoStatus })
        });
        const data = await res.json();

        if (data.sucesso) {
            const labels = {
                'em_preparo':   '🍳 Pedido em preparo!',
                'saiu_entrega': '🛵 Saiu para entrega!',
                'entregue':     '✅ Pedido entregue!'
            };
            mostrarToast(labels[novoStatus] || 'Status atualizado!');
        } else {
            mostrarToast('❌ Erro: ' + (data.erro || 'Falha ao atualizar'));
        }
    } catch (e) {
        mostrarToast('❌ Erro de conexão ao atualizar status');
    }

    // Recarrega dados do servidor para sincronizar
    await buscarPedidos();
}

/* ── Estado atual dos pedidos (para diff) ── */
let pedidosAtuais = {};

/* ── Buscar pedidos com DOM diffing (sem flickering) ── */
async function buscarPedidos() {
    try {
        const res = await fetch('/api/pedidos/delivery');
        const data = await res.json();

        if (!data.sucesso) return;

        const listas = {
            'novo':         document.getElementById('lista-novo'),
            'em_preparo':   document.getElementById('lista-em_preparo'),
            'saiu_entrega': document.getElementById('lista-saiu_entrega')
        };

        // Agrupar pedidos novos por status
        const pedidosNovos = {};
        const pedidosPorStatus = { novo: [], em_preparo: [], saiu_entrega: [] };

        data.pedidos.forEach(pedido => {
            pedidosNovos[pedido.id] = pedido;
            if (pedidosPorStatus[pedido.status]) {
                pedidosPorStatus[pedido.status].push(pedido);
            }
        });

        // IDs que existem agora no servidor
        const idsNovos = new Set(Object.keys(pedidosNovos).map(Number));

        // 1) Remover cards que não existem mais (entregues ou deletados)
        Object.keys(pedidosAtuais).forEach(id => {
            id = Number(id);
            if (!idsNovos.has(id)) {
                const card = document.getElementById(`pedido-${id}`);
                if (card) card.remove();
                delete pedidosAtuais[id];
            }
        });

        // 2) Atualizar ou adicionar cards
        Object.entries(pedidosPorStatus).forEach(([status, pedidos]) => {
            const lista = listas[status];
            if (!lista) return;

            pedidos.forEach(pedido => {
                const cardExistente = document.getElementById(`pedido-${pedido.id}`);

                if (cardExistente) {
                    // Card existe — verificar se mudou de coluna
                    if (cardExistente.dataset.status !== pedido.status) {
                        cardExistente.remove();
                        lista.appendChild(criarCard(pedido));
                    }
                    // Se está na mesma coluna, não toca (evita flicker)
                } else {
                    // Card novo — adicionar e notificar
                    if (!pedidosAtuais[pedido.id] && pedido.status === 'novo') {
                        mostrarToast(`🔔 Novo pedido #${pedido.id} — ${pedido.cliente_nome}!`);
                    }
                    lista.appendChild(criarCard(pedido));
                }
            });
        });

        // 3) Atualizar contadores
        Object.entries(pedidosPorStatus).forEach(([status, pedidos]) => {
            const el = document.getElementById(`count-${status}`);
            if (el) el.textContent = pedidos.length;
        });

        // 4) Mensagem de vazio em cada coluna
        Object.entries(listas).forEach(([status, lista]) => {
            if (!lista) return;
            const vazioExistente = lista.querySelector('.vazio');
            if (pedidosPorStatus[status].length === 0) {
                if (!vazioExistente) {
                    lista.innerHTML = '<div class="vazio"><span>✓</span>Nenhum pedido</div>';
                }
            } else {
                if (vazioExistente) vazioExistente.remove();
            }
        });

        // 5) Salvar estado atual
        pedidosAtuais = pedidosNovos;

        // 6) Atualizar hora
        const agora = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
        const el = document.getElementById('ultima-atualizacao');
        if (el) el.textContent = `Atualizado às ${agora}`;

    } catch (e) {
        const el = document.getElementById('ultima-atualizacao');
        if (el) el.textContent = 'Erro ao carregar';
    }
}

buscarPedidos();
setInterval(buscarPedidos, 5000);
