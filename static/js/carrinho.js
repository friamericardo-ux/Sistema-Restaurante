// Carrinho.js — Delivery

function lerCarrinho() {
  const carrinho = localStorage.getItem('comanda_carrinho');
  return carrinho ? JSON.parse(carrinho) : [];
}

function salvarCarrinho(carrinho) {
  localStorage.setItem('comanda_carrinho', JSON.stringify(carrinho));
}

function renderizarCarrinho() {
  const itens = lerCarrinho();
  const badge = document.getElementById('badge-count');
  if (badge) badge.textContent = itens.reduce((s, i) => s + i.quantidade, 0);
  if (!itens.length) {
    cartItems.innerHTML = '<div class="cart-empty">Carrinho vazio</div>';
    document.getElementById('cart-subtotal').textContent = 'R$ 0,00';
    document.getElementById('cart-total').textContent = 'R$ 0,00';
    return;
  }
  let subtotal = 0;
  cartItems.innerHTML = itens.map((item, idx) => {
    subtotal += parseFloat(item.preco) * parseInt(item.quantidade);
    const adicionais = item.adicionais && item.adicionais.length
      ? '<div class="cart-item-extra">' + item.adicionais.map(a => `${a.nome} (+R$ ${parseFloat(a.preco).toFixed(2)})`).join(', ') + '</div>'
      : '';
    return `<div class="cart-item">
      <div class="cart-item-nome">${item.nome}</div>
      ${adicionais}
      <div class="qty-ctrl">
        <button class="qty-btn" onclick="mudarQtd(${idx}, -1)">-</button>
        <span class="qty-num">${item.quantidade}</span>
        <button class="qty-btn" onclick="mudarQtd(${idx}, 1)">+</button>
      </div>
      <div class="cart-item-preco">R$ ${(parseFloat(item.preco) * parseInt(item.quantidade)).toFixed(2)}</div>
    </div>`;
  }).join('');
  document.getElementById('cart-subtotal').textContent = `R$ ${subtotal.toFixed(2)}`;
  document.getElementById('cart-entrega').textContent = 'R$ 5,00';
  document.getElementById('cart-total').textContent = `R$ ${(subtotal + 5).toFixed(2)}`;
}

function mudarQtd(idx, delta) {
  let carrinho = lerCarrinho();
  carrinho[idx].quantidade += delta;
  if (carrinho[idx].quantidade < 1) carrinho[idx].quantidade = 1;
  salvarCarrinho(carrinho);
  renderizarCarrinho();
}

function finalizarPedido() {
  const itens = lerCarrinho();
  if (!itens.length) return toast('Carrinho vazio');
  const nome = document.getElementById('nome').value;
  const telefone = document.getElementById('telefone').value;
  const endereco = document.getElementById('endereco').value;
  const observacao = document.getElementById('observacao').value;
  const pagamento = document.querySelector('input[name="pagamento"]:checked')?.value;
  const troco = pagamento === 'dinheiro' ? document.getElementById('troco').value : '';
  if (!nome || !telefone || !endereco || !pagamento) return toast('Preencha todos os campos obrigatórios');
  const pedido = {
    nome, telefone, endereco, observacao, pagamento, troco,
    itens: itens.map(i => ({
      nome: i.nome,
      preco: i.preco,
      quantidade: i.quantidade,
      adicionais: i.adicionais || []
    }))
  };
  fetch('/api/pedido', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(pedido)
  }).then(res => res.json()).then(data => {
    if (data.sucesso) {
      document.getElementById('form-box').style.display = 'none';
      document.getElementById('sucesso-box').style.display = 'block';
      document.getElementById('btn-whatsapp').onclick = () => {
        limparPedido();
        window.open('https://wa.me/5567993487509?text=' + encodeURIComponent(data.resumo), '_blank');
      };
      document.getElementById('btn-novo').onclick = () => {
        limparPedido();
        window.location.href = '/cardapio';
      };
    } else {
      toast('Erro ao criar pedido');
    }
  }).catch(() => toast('Erro ao criar pedido'));
}

function limparPedido() {
  localStorage.removeItem('comanda_carrinho');
  document.getElementById('nome').value = '';
  document.getElementById('telefone').value = '';
  document.getElementById('endereco').value = '';
  document.getElementById('observacao').value = '';
  document.querySelectorAll('input[name="pagamento"]').forEach(r => r.checked = false);
  document.getElementById('troco-section').style.display = 'none';
  document.getElementById('troco').value = '';
  document.getElementById('sucesso-box').style.display = 'none';
  document.getElementById('form-box').style.display = 'block';
  document.getElementById('cart-items').innerHTML = '<div class="cart-empty">Carrinho vazio</div>';
  document.getElementById('cart-subtotal').textContent = 'R$ 0,00';
  document.getElementById('cart-entrega').textContent = 'R$ 5,00';
  document.getElementById('cart-total').textContent = 'R$ 0,00';
}

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 2000);
}
window.onload = function() {
  renderizarCarrinho();
  // Atualiza badge
  const itens = lerCarrinho();
  const badge = document.getElementById('badge-count');
  if (badge) badge.textContent = itens.reduce((s, i) => s + i.quantidade, 0);

  document.querySelectorAll('input[name="pagamento"]').forEach(r => {
    r.onchange = () => {
      document.getElementById('troco-section').style.display = r.value === 'dinheiro' && r.checked ? 'block' : 'none';
    };
  });
};
