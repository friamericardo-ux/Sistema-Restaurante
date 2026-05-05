// Carrinho.js — Delivery

let taxaEntrega = 0;
let configsRestaurante = { whatsapp: '5567993487509' };

async function carregarConfigs() {
  try {
    const slug = document.getElementById('restauranteSlug')?.value || '';
    const res = await fetch(`/api/configuracoes?slug=${encodeURIComponent(slug)}`);
    const data = await res.json();
    if (data.sucesso) {
      taxaEntrega = parseFloat(window._freteCalculado) || 0;
      configsRestaurante.whatsapp = data.whatsapp_restaurante || configsRestaurante.whatsapp;
      const el = document.getElementById('cart-entrega');
      if (el) el.textContent = window._freteCalculado != null ?
        'R$ ' + parseFloat(window._freteCalculado).toFixed(2).replace('.', ',') :
        'Calculando...';
      atualizarTotal();
    }
  } catch (e) {
    
  }
}

function atualizarTotal() {
  const itens = lerCarrinho();
  if (!itens.length) return;
  const subtotal = itens.reduce((s, i) => s + parseFloat(i.preco) * parseInt(i.quantidade), 0);
  const elSub = document.getElementById('cart-subtotal');
  const elTotal = document.getElementById('cart-total');
  if (elSub) elSub.textContent = `R$ ${subtotal.toFixed(2)}`;
  const freteAtual = parseFloat(window._freteCalculado) || 0;
  if (elTotal) elTotal.textContent = `R$ ${(subtotal + freteAtual).toFixed(2)}`;
}

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
    document.getElementById('cart-entrega').textContent = `a calcular...`;
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
  document.getElementById('cart-entrega').textContent = window._freteCalculado != null ?
    'R$ ' + parseFloat(window._freteCalculado).toFixed(2).replace('.', ',') :
    'Calculando...';
  document.getElementById('cart-total').textContent = `R$ ${(subtotal + (parseFloat(window._freteCalculado) || 0)).toFixed(2)}`;
}

function mudarQtd(idx, delta) {
  let carrinho = lerCarrinho();
  carrinho[idx].quantidade += delta;
  if (carrinho[idx].quantidade < 1) carrinho[idx].quantidade = 1;
  salvarCarrinho(carrinho);
  renderizarCarrinho();
}

async function finalizarPedido() {
  const itens = lerCarrinho();
  if (!itens.length) return toast('Carrinho vazio');

  const nome = document.getElementById('nome').value.trim();
  const telefone = document.getElementById('telefone').value.trim();
  const endereco = document.getElementById('endereco').value.trim();
  const observacao = document.getElementById('observacao').value.trim();
  const pagamento = document.querySelector('input[name="pagamento"]:checked')?.value;

  if (!nome || !telefone || !endereco || !pagamento)
    return toast('Preencha todos os campos obrigatórios');

  if (window._freteCalculado == null && endereco) {
    if (typeof calcularFrete === 'function') {
       toast('Calculando frete, aguarde...');
       await calcularFrete(endereco);
    }
  }

  const freteAtual = parseFloat(window._freteCalculado) || parseFloat(window.taxaEntrega) || 0;

  let troco = 0;
  let trocoTexto = '';
  if (pagamento === 'dinheiro') {
    const precisaTroco = document.getElementById('troco-sim')?.checked;
    if (precisaTroco) {
      const valorPago = parseFloat(document.getElementById('troco').value);
      const totalPedido = itens.reduce((s, i) => s + parseFloat(i.preco) * i.quantidade, 0) + freteAtual;
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

  const rid = document.getElementById('restauranteId')?.value || 1;
  const slug = document.getElementById('restauranteSlug')?.value || '';
  console.log('forma_pagamento:', pagamento, 'troco:', troco);
  fetch('/api/pedido', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nome, telefone, endereco, observacao, pagamento, troco,
      slug,
      taxa_entrega: freteAtual,
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
        body: JSON.stringify({ telefone, nome, endereco, slug })
      }).catch(() => {});

      const subtotal = itens.reduce((s, i) => s + parseFloat(i.preco) * i.quantidade, 0);
      const total = subtotal + freteAtual;
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
        `🚚 *Entrega:* R$ ${freteAtual.toFixed(2)}\n` +
        `💵 *Total:* R$ ${total.toFixed(2)}\n` +
        `💳 *Pagamento:* ${pagTexto}\n` +
        (trocoTexto ? `💵 *Troco:* ${trocoTexto}\n` : '') +
        `\nPedido ID: ${data.pedido_id}`;

      const numero = (typeof configsRestaurante !== 'undefined' && configsRestaurante.whatsapp)
        ? configsRestaurante.whatsapp : '5567993487509';
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
  document.getElementById('cart-entrega').textContent = 'R$ ' + taxaEntrega.toFixed(2).replace('.', ',');
  document.getElementById('cart-total').textContent = 'R$ 0,00';
}

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 2000);
}
window.onload = function () {
  carregarConfigs();
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
    const slug = document.getElementById('restauranteSlug')?.value || '';
    fetch(`/api/cliente/${encodeURIComponent(tel)}?slug=${encodeURIComponent(slug)}`)
      .then(r => r.json())
      .then(data => {
        if (data.sucesso) {
          document.getElementById('nome').value = data.nome || '';
          document.getElementById('endereco').value = data.endereco || '';
          document.getElementById('msg-autopreenchido').style.display = 'block';
          if (data.endereco && typeof calcularFrete === 'function') calcularFrete(data.endereco);
        } else {
          document.getElementById('msg-autopreenchido').style.display = 'none';
        }
      })
      .catch(() => {});
  });
};
