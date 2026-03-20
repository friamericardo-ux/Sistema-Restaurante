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
  const cartItems = document.getElementById('cart-items');

  if (!itens.length) {
    cartItems.innerHTML = '<div class="cart-empty">Carrinho vazio</div>';
    document.getElementById('cart-subtotal').textContent = 'R$ 0,00';
    document.getElementById('cart-entrega').textContent = 'R$ 5,00';
    document.getElementById('cart-total').textContent = 'R$ 0,00';
    return;
  }

  let subtotal = 0;
  cartItems.innerHTML = itens.map((item, idx) => {
    subtotal += parseFloat(item.preco) * parseInt(item.quantidade);
    const adicionais = item.adicionais && item.adicionais.length
      ? '<div class="cart-item-extra">➕ ' + item.adicionais.map(a =>
        `${a.nome} (+R$ ${parseFloat(a.preco).toFixed(2)})`).join(', ') + '</div>'
      : '';
    return `<div class="cart-item">
      <div class="cart-item-nome">${item.nome}</div>
      ${adicionais}
      <div class="qty-ctrl">
        <button class="qty-btn" onclick="mudarQtd(${idx}, -1)">−</button>
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

  const nome = document.getElementById('nome').value.trim();
  const telefone = document.getElementById('telefone').value.trim();
  const endereco = document.getElementById('endereco').value.trim();
  const observacao = document.getElementById('observacao').value.trim();
  const pagamento = document.querySelector('input[name="pagamento"]:checked')?.value;

  let troco = 0;
  let trocoTexto = '';
  if (pagamento === 'dinheiro') {
    const precisaTroco = document.getElementById('troco-sim')?.checked;
    if (precisaTroco) {
      const valorPago = parseFloat(document.getElementById('troco').value);
      const totalPedido = itens.reduce((s, i) => s + parseFloat(i.preco) * i.quantidade, 0) + 5;
      if (!isNaN(valorPago) && valorPago > 0) {
        const trocoDar = valorPago - totalPedido;
        troco = valorPago;
        trocoTexto = trocoDar > 0
        ? `Troco para R$ ${valorPago.toFixed(2)}\n💰 *Troco a devolver:* R$ ${trocoDar.toFixed(2)}`
        : 'Valor exato';
      }
    } else {
      trocoTexto = 'Não precisa de troco';
    }
  }

  if (!nome || !telefone || !endereco || !pagamento)
    return toast('Preencha todos os campos obrigatórios');

  fetch('/api/pedido', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nome, telefone, endereco, observacao, pagamento, troco,
      itens: itens.map(i => ({
        nome: i.nome, preco: i.preco,
        quantidade: i.quantidade,
        adicionais: i.adicionais || []
      }))
    })
  }).then(res => res.json()).then(data => {
    if (data.sucesso) {
      fetch('/api/cliente', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telefone, nome, endereco })
      }).catch(() => {});

      const subtotal = itens.reduce((s, i) => s + parseFloat(i.preco) * i.quantidade, 0);
      const total = subtotal + 5;
      const pagTexto = pagamento === 'cartao' ? '💳 Cartão'
        : `💵 Dinheiro`;
      const linhaItens = itens.map(i => {
        const extras = i.adicionais?.length
          ? ` (+${i.adicionais.map(a => a.nome).join(', ')})` : '';
        return `• ${i.quantidade}x ${i.nome}${extras} — R$ ${(parseFloat(i.preco) * i.quantidade).toFixed(2)}`;
      }).join('\n');
      const mensagem =
        `*Novo Pedido — Comanda Digital*\n\n` +
        `👤 *Cliente:* ${nome}\n` +
        `📞 *Telefone:* ${telefone}\n` +
        `🏠 *Endereço:* ${endereco}\n` +
        (observacao ? `📝 *Observação:* ${observacao}\n` : '') +
        `\n📋 *Itens:*\n${linhaItens}\n\n` +
        `💰 *Subtotal:* R$ ${subtotal.toFixed(2)}\n` +
        `🚚 *Entrega:* R$ 5,00\n` +
        `💵 *Total:* R$ ${total.toFixed(2)}\n` +
        `💳 *Pagamento:* ${pagTexto}\n` +
        (trocoTexto ? `💵 *Troco:* ${trocoTexto}\n` : '') +
        `\nPedido ID: ${data.pedido_id}`;

      const numero = '5567993487509';
      document.getElementById('form-box').style.display = 'none';
      document.getElementById('cart-box').style.display = 'none';
      document.getElementById('sucesso-box').style.display = 'block';
      document.getElementById('btn-whatsapp').onclick = () => {
        limparPedido();
        window.open(`https://wa.me/${numero}?text=${encodeURIComponent(mensagem)}`, '_blank');
      };
      document.getElementById('btn-novo').onclick = () => {
        limparPedido();
        window.location.href = '/cardapio';
      };
    } else {
      toast('Erro ao criar pedido');
    }
  }).catch(() => toast('Erro de conexão'));
}

function onTrocoChange() {
  const precisaTroco = document.getElementById('troco-sim').checked;
  document.getElementById('troco-valor-section').style.display = precisaTroco ? 'block' : 'none';
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
  document.getElementById('cart-box').style.display = 'block';
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
window.onload = function () {
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
  document.querySelectorAll('input[name="troco-opcao"]').forEach(r => {
    r.onchange = onTrocoChange;
  });

  document.getElementById('telefone').addEventListener('blur', function () {
    const tel = this.value.trim();
    if (!tel) return;
    fetch(`/api/cliente/${encodeURIComponent(tel)}`)
      .then(r => r.json())
      .then(data => {
        if (data.sucesso) {
          document.getElementById('nome').value = data.nome || '';
          document.getElementById('endereco').value = data.endereco || '';
          document.getElementById('msg-autopreenchido').style.display = 'block';
        } else {
          document.getElementById('msg-autopreenchido').style.display = 'none';
        }
      })
      .catch(() => {});
  });
};
