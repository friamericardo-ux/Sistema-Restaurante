/* ============================================================
   ESTACIONAMENTO — JavaScript (requer Socket.io carregado antes)
============================================================ */

let mesas = {};
const socket = io();

// Relógio em tempo real
setInterval(() => {
    const el = document.getElementById('relogio');
    if (el) el.textContent = new Date().toLocaleTimeString('pt-BR');
}, 1000);

// Eventos Socket.io
socket.on('mesas_iniciais', lista => {
    lista.forEach(m => { mesas[m.numero] = m; });
    render();
});

socket.on('mesa_atualizada', m => {
    mesas[m.numero] = m;
    render();
});

socket.on('mesa_fechada', d => {
    delete mesas[d.numero];
    render();
});

function render() {
    const lista = Object.values(mesas);

    if (lista.length === 0) {
        document.getElementById('grid').innerHTML =
            '<div class="vazio">&#9203; Aguardando pedidos...</div>';
        return;
    }

    document.getElementById('grid').innerHTML = lista.map(m => `
        <div class="mesa-card">
            <div class="mesa-header">
                <div>
                    <div class="mesa-num">MESA ${m.numero}</div>
                    <div class="mesa-atendente">${m.atendente || '—'}</div>
                </div>
                <div class="mesa-hora">${m.abertura}</div>
            </div>
            <div class="mesa-itens">
                ${m.itens.length === 0
                    ? '<p style="color:#4a6080">Nenhum item</p>'
                    : m.itens.map(i => `
                        <div class="item">
                            <div class="item-qtd">${i.quantidade}x</div>
                            <div class="item-nome">
                                ${i.nome}
                                ${i.obs ? `<div class="item-obs">&#9888; ${i.obs}</div>` : ''}
                            </div>
                            <div class="item-preco">R$ ${i.subtotal.toFixed(2)}</div>
                        </div>`).join('')}
            </div>
            <div class="mesa-footer">
                <span class="total-label">TOTAL</span>
                <span class="total-valor">R$ ${m.total.toFixed(2)}</span>
            </div>
        </div>
    `).join('');
}
