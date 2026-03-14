/* ============================================================
   CARDAPIO.JS — Lógica do cardápio do cliente (delivery)
   ============================================================ */

// ── Proteção contra XSS ────────────────────────────────────────
function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

// ── Estado global ──────────────────────────────────────────────
let carrinho = [];
let modalProduto = null;
let adicionaisDisponiveis = [];

// ── Inicialização ──────────────────────────────────────────────
window.addEventListener('load', async () => {
  await carregarCardapio();
});

// ── Carrega cardápio da API ────────────────────────────────────
async function carregarCardapio() {
  try {
    const res  = await fetch('/api/cardapio');
    const data = await res.json();
    if (data.sucesso) exibirCardapio(data.produtos);
  } catch {
    document.getElementById('cardapio').innerHTML =
      '<div class="empty-state">Erro ao carregar cardápio. Recarregue a página.</div>';
  }
}

// ── Carrega adicionais da API ──────────────────────────────────
async function carregarAdicionais() {
  try {
    const res  = await fetch('/api/adicionais');
    const data = await res.json();
    if (data.sucesso) adicionaisDisponiveis = data.adicionais;
  } catch {
    adicionaisDisponiveis = [];
  }
}

// ── Emoji fallback por nome de produto ─────────────────────────
function getEmoji(nome) {
  const n = nome.toLowerCase();
  if (n.includes('x-bacon') || n.includes('bacon'))    return '🥓';
  if (n.includes('burguer') || n.includes('burger') || n.includes('x-'))  return '🍔';
  if (n.includes('salada') || n.includes('x-salada'))  return '🥗';
  if (n.includes('fritas'))    return '🍟';
  if (n.includes('sorvete'))   return '🍦';
  if (n.includes('pizza'))     return '🍕';
  if (n.includes('coca') || n.includes('refri') || n.includes('suco')) return '🥤';
  if (n.includes('frango') || n.includes('galinha'))   return '🍗';
  if (n.includes('porcao') || n.includes('porção'))    return '🍖';
  return '🍽️';
}

// ── Helper: gera ID DOM seguro a partir da categoria ──────────
function slugify(str) {
  return str
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

// ── Renderiza cards agrupados por categoria ────────────────────
function exibirCardapio(produtos) {
// ...existing code...
  if (!produtos.length) {
    if (navEl) navEl.innerHTML = '';
    el.innerHTML = '<div class="empty-state">📭 Nenhum produto cadastrado ainda</div>';
    return;
  }

  const grupos = new Map();
  for (const p of produtos) {
    const cat = (p.categoria || 'Outros').trim();
    if (!grupos.has(cat)) grupos.set(cat, []);
    // Adiciona event listener para os botões de adicionar rápido
    document.querySelectorAll('.btn-adicionar-rapido').forEach(btn => {
      btn.addEventListener('click', function(e) {
        e.stopPropagation(); // Impede propagação para o card
        const produtoJson = btn.getAttribute('data-produto').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
        const produto = JSON.parse(produtoJson);
        abrirModal(produto);
      });
    });
    grupos.get(cat).push(p);
  }

  if (navEl) {
    navEl.innerHTML = `
      <div class="categoria-nav-inner">
        ${[...grupos.keys()].map(cat => `
          <button class="categoria-btn"
                  data-slug="secao-${slugify(cat)}"
                  onclick="irParaCategoria('secao-${slugify(cat)}')">
            ${cat}
          </button>`).join('')}
      </div>`;
    const primeiro = navEl.querySelector('.categoria-btn');
    if (primeiro) primeiro.classList.add('ativo');
  }

  el.innerHTML = [...grupos.entries()].map(([cat, prods]) => {
    const slug = slugify(cat);
    const cardsHtml = prods.map(p => {
      const imagemHtml = p.foto
        ? `<img src="/static/img/produtos/${escapeHtml(p.foto)}" alt="${escapeHtml(p.nome)}">`
        : `<span class="produto-emoji">${getEmoji(p.nome)}</span>`;

      const descHtml = p.descricao
        ? `<div class="produto-descricao">${escapeHtml(p.descricao)}</div>`
        : `<div class="produto-categoria">${escapeHtml(p.categoria)}</div>`;

      return `
        <div class="produto-card" onclick="abrirModal(${JSON.stringify(p).replace(/"/g, '&quot;')})">
          ${imagemHtml}
          <div class="produto-nome">${escapeHtml(p.nome)}</div>
          ${descHtml}
          <div class="produto-preco">R$ ${p.preco.toFixed(2)}</div>
          <div class="add-icon" aria-hidden="true">+</div>
          <button class="btn-adicionar-rapido" aria-label="Adicionar ${p.nome} ao pedido">
            + Adicionar ao Pedido
          </button>
        </div>`;
    }).join('');

    return `
      <section class="categoria-section" id="secao-${slug}">
        <div class="categoria-titulo">${cat}</div>
        <div class="cardapio-grid">${cardsHtml}</div>
      </section>`;
  }).join('');

  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        document.querySelectorAll('.categoria-btn').forEach(btn => {
          btn.classList.toggle('ativo', btn.dataset.slug === id);
        });
      }
    }
  }, { rootMargin: '-30% 0px -60% 0px', threshold: 0 });

  document.querySelectorAll('.categoria-section').forEach(sec => observer.observe(sec));
}

// ── Navega até uma seção de categoria ─────────────────────────
function irParaCategoria(id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}


/* ============================================================
   MODAL — STEPPER (Adicionais → Observação → Pagamento)
   ============================================================ */

let stepAtual = 1;
const TOTAL_STEPS = 3;

// ── Atualiza visual do stepper ─────────────────────────────────
function atualizarStepper() {
  for (let i = 1; i <= TOTAL_STEPS; i++) {
    const indicador = document.getElementById(`step-ind-${i}`);
    const conteudo  = document.getElementById(`step-${i}`);

    indicador.classList.remove('active', 'done');
    if (i < stepAtual) indicador.classList.add('done');
    if (i === stepAtual) indicador.classList.add('active');

    conteudo.style.display = i === stepAtual ? 'block' : 'none';
  }

  const btnVoltar    = document.getElementById('btn-voltar');
  const btnContinuar = document.getElementById('btn-continuar');
  const btnConfirmar = document.getElementById('btn-confirmar');

  btnVoltar.style.display    = stepAtual > 1 ? 'inline-flex' : 'none';
  btnContinuar.style.display = stepAtual < TOTAL_STEPS ? 'inline-flex' : 'none';
  btnConfirmar.style.display = stepAtual === TOTAL_STEPS ? 'inline-flex' : 'none';
}

// ── Avança para próxima etapa ──────────────────────────────────
function stepProximo() {
  if (stepAtual >= TOTAL_STEPS) return;
  stepAtual++;
  atualizarStepper();
}

// ── Volta para etapa anterior ──────────────────────────────────
function stepAnterior() {
  if (stepAtual <= 1) return;
  stepAtual--;
  atualizarStepper();
}

// ── Reseta o stepper ao abrir o modal ─────────────────────────
function resetarStepper(temAdicionais) {
  stepAtual = 1;
  // Limpa campos do modal (apenas adicionais)
  // ...existing code...
  atualizarStepper();
}

// ── Lógica de pagamento ────────────────────────────────────────
function onPagamentoChange() {
  const dinheiroSelecionado = document.getElementById('pag-dinheiro').checked;
  document.getElementById('troco-section').style.display = dinheiroSelecionado ? 'block' : 'none';

  if (!dinheiroSelecionado) {
    document.getElementById('troco-nao').checked = true;
    document.getElementById('troco-valor-section').style.display = 'none';
    document.getElementById('troco-valor').value = '';
  }
}

function onTrocoChange() {
  const precisaTroco = document.getElementById('troco-sim').checked;
  document.getElementById('troco-valor-section').style.display = precisaTroco ? 'block' : 'none';
}

// ── Coleta dados de pagamento ──────────────────────────────────
// Retorna { pagamento, troco } ou null se inválido
function coletarPagamento() {
  const selecionado = document.querySelector('input[name="pagamento"]:checked');

  if (!selecionado) {
    showToast('⚠️ Escolha a forma de pagamento!');
    return null;
  }

  const pagamento = selecionado.value; // 'cartao' ou 'dinheiro'
  let troco = null;

  if (pagamento === 'dinheiro') {
    const precisaTroco = document.getElementById('troco-sim').checked;
    if (precisaTroco) {
      const valor = parseFloat(document.getElementById('troco-valor').value);
      troco = (!isNaN(valor) && valor > 0) ? `R$ ${valor.toFixed(2)}` : 'Não informado';
    } else {
      troco = 'Não precisa';
    }
  }

  return { pagamento, troco };
}


/* ============================================================
   MODAL — Abrir / Fechar
   ============================================================ */

// ── Abre modal de personalização ──────────────────────────────
async function abrirModal(produto) {
  modalProduto = produto;

  document.getElementById('modal-nome').textContent      = produto.nome;
  document.getElementById('modal-preco-base').textContent = `R$ ${produto.preco.toFixed(2)}`;

  const descEl = document.getElementById('modal-descricao');
  if (descEl) {
    descEl.textContent   = produto.descricao || '';
    descEl.style.display = produto.descricao ? 'block' : 'none';
  }

  // Busca adicionais específicos do produto
  const lista   = document.getElementById('modal-adicionais-lista');
  const section = document.getElementById('modal-adicionais-section');

  try {
    const res  = await fetch(`/api/adicionais?produto_id=${produto.id}`);
    const data = await res.json();
    adicionaisDisponiveis = data.sucesso ? data.adicionais : [];
  } catch {
    adicionaisDisponiveis = [];
  }

  const temAdicionais = adicionaisDisponiveis.length > 0;

  if (temAdicionais) {
    section.style.display = 'block';
    lista.innerHTML = adicionaisDisponiveis.map(a => `
      <label class="adicional-opcao">
        <input type="checkbox"
               data-id="${a.id}"
               data-nome="${escapeHtml(a.nome)}"
               data-preco="${a.preco}"
               onchange="atualizarTotalModal()">
        <span class="adicional-opcao-nome">${escapeHtml(a.nome)}</span>
        <span class="adicional-opcao-preco">+R$ ${a.preco.toFixed(2)}</span>
      </label>`).join('');
  } else {
    section.style.display = 'none';
    lista.innerHTML = '';
  }

  atualizarTotalModal();
  resetarStepper(temAdicionais); // ← inicia stepper na etapa correta

  const overlay = document.getElementById('modal-overlay');
  overlay.classList.add('aberto');
  document.body.style.overflow = 'hidden';
}

// ── Fecha modal ────────────────────────────────────────────────
function fecharModal() {
  document.getElementById('modal-overlay').classList.remove('aberto');
  document.body.style.overflow = '';
  modalProduto = null;
}

// Fecha ao clicar fora do conteúdo
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('modal-overlay').addEventListener('click', function (e) {
    if (e.target === this) fecharModal();
  });
});

// ── Atualiza total no modal ao marcar adicionais ───────────────
function atualizarTotalModal() {
  if (!modalProduto) return;
  let total = modalProduto.preco;
  document.querySelectorAll('#modal-adicionais-lista input:checked').forEach(cb => {
    total += parseFloat(cb.dataset.preco);
  });
  document.getElementById('modal-total').textContent = `R$ ${total.toFixed(2)}`;
}

// ── Confirma seleção e adiciona ao carrinho ────────────────────
function confirmarAdicional() {
  if (!modalProduto) return;

  // Apenas adicionais por item
  const adicionaisSelecionados = [];
  let extraPreco = 0;

  document.querySelectorAll('#modal-adicionais-lista input:checked').forEach(cb => {
    adicionaisSelecionados.push({
      id:    parseInt(cb.dataset.id),
      nome:  cb.dataset.nome,
      preco: parseFloat(cb.dataset.preco)
    });
    extraPreco += parseFloat(cb.dataset.preco);
  });

  const precoFinal = modalProduto.preco + extraPreco;
  const chave     = modalProduto.id + ':' + JSON.stringify(adicionaisSelecionados);
  const existente = carrinho.find(i => i._chave === chave);

  if (existente) {
    existente.quantidade++;
  } else {
    carrinho.push({
      _chave:     chave,
      nome:       modalProduto.nome,
      preco:      precoFinal,
      quantidade: 1,
      adicionais: adicionaisSelecionados
    });
  }

  fecharModal();
  renderizarCarrinho();
  showToast(`✅ ${modalProduto.nome} adicionado!`);
}


/* ============================================================
   CARRINHO
   ============================================================ */

// ── Renderiza itens do carrinho ────────────────────────────────
function renderizarCarrinho() {
  const el      = document.getElementById('cart-items');
  const footer  = document.getElementById('cart-footer');
  const formBox = document.getElementById('form-box');
  const count   = carrinho.reduce((s, i) => s + i.quantidade, 0);

  document.getElementById('badge-count').textContent = count;

  if (!carrinho.length) {
    el.innerHTML = '<div class="cart-empty">Nenhum item adicionado</div>';
    footer.style.display = 'none';
    formBox.classList.remove('show');
    return;
  }

  el.innerHTML = carrinho.map((item, idx) => `
    <div class="cart-item">
      <div class="cart-item-nome">
        ${escapeHtml(item.nome)}
        ${item.adicionais && item.adicionais.length
          ? `<div class="cart-item-extra">➕ ${item.adicionais.map(a => escapeHtml(a.nome)).join(', ')}</div>`
          : ''}
        ${item.observacao
          ? `<div class="cart-item-extra">📝 ${escapeHtml(item.observacao)}</div>`
          : ''}
        <div class="cart-item-extra">
          ${item.pagamento === 'cartao' ? '💳 Cartão' : '💵 Dinheiro'}
          ${item.troco && item.troco !== 'Não precisa' ? ` — Troco: ${escapeHtml(item.troco)}` : ''}
        </div>
      </div>
      <div class="qty-ctrl">
        <button class="qty-btn" onclick="mudarQtd(${idx}, -1)" aria-label="Diminuir quantidade">−</button>
        <span class="qty-num">${item.quantidade}</span>
        <button class="qty-btn" onclick="mudarQtd(${idx}, 1)" aria-label="Aumentar quantidade">+</button>
      </div>
      <div class="cart-item-preco">R$ ${(item.preco * item.quantidade).toFixed(2)}</div>
    </div>`).join('');

  const subtotal = carrinho.reduce((s, i) => s + i.preco * i.quantidade, 0);
  const total    = subtotal + 5;
  document.getElementById('subtotal-val').textContent = `R$ ${subtotal.toFixed(2)}`;
  document.getElementById('total-val').textContent    = `R$ ${total.toFixed(2)}`;
  footer.style.display = 'block';
  formBox.classList.add('show');
}

// ── Altera quantidade de um item do carrinho ───────────────────
function mudarQtd(idx, delta) {
  carrinho[idx].quantidade += delta;
  if (carrinho[idx].quantidade <= 0) carrinho.splice(idx, 1);
  renderizarCarrinho();
}

// ── Scroll para o carrinho ─────────────────────────────────────
function scrollToCart() {
  document.getElementById('sidebar').scrollIntoView({ behavior: 'smooth' });
}


/* ============================================================
   FINALIZAR PEDIDO
   ============================================================ */

async function finalizarPedido() {
  const nome     = document.getElementById('nome').value.trim();
  const telefone = document.getElementById('telefone').value.trim();
  const endereco = document.getElementById('endereco').value.trim();
  const observacaoGeral = document.getElementById('observacao-geral').value.trim();

  // Coleta pagamento e troco do carrinho
  const pagamentoSelecionado = document.querySelector('input[name="pagamento-carrinho"]:checked');
  if (!pagamentoSelecionado) {
    showToast('⚠️ Escolha a forma de pagamento!');
    return;
  }
  const pagamento = pagamentoSelecionado.value;
  let troco = '';
  if (pagamento === 'dinheiro') {
    const precisaTroco = document.getElementById('troco-sim-carrinho').checked;
    if (precisaTroco) {
      const valor = parseFloat(document.getElementById('troco-valor-carrinho').value);
      troco = (!isNaN(valor) && valor > 0) ? `R$ ${valor.toFixed(2)}` : 'Não informado';
    } else {
      troco = 'Não precisa';
    }
  }

  if (!nome || !telefone || !endereco) {
    showToast('⚠️ Preencha todos os campos!');
    return;
  }
  if (!carrinho.length) {
    showToast('⚠️ Carrinho vazio!');
    return;
  }

  const btn = document.getElementById('btn-finalizar');
  btn.innerHTML = '<span class="loading"></span> Enviando...';
  btn.disabled  = true;

  try {
    const res = await fetch('/api/pedido', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome, telefone, endereco,
        observacao: observacaoGeral,
        pagamento, troco,
        itens: carrinho.map(i => ({
          nome:       i.nome,
          preco:      i.preco,
          quantidade: i.quantidade,
          adicionais: i.adicionais || []
        }))
      })
    });

    const data = await res.json();
    if (data.sucesso) {
      const subtotal   = carrinho.reduce((s, i) => s + i.preco * i.quantidade, 0);
      const total      = subtotal + 5;

      const pagamentoTexto = pagamento === 'cartao'
        ? '💳 Cartão'
        : `💵 Dinheiro${troco && troco !== 'Não precisa' ? ` (Troco: ${troco})` : ''}`;

      const linhaItens = carrinho.map(i => {
        const extras = i.adicionais && i.adicionais.length
          ? ` (+${i.adicionais.map(a => a.nome).join(', ')})` : '';
        return `• ${i.quantidade}x ${i.nome}${extras} — R$ ${(i.preco * i.quantidade).toFixed(2)}`;
      }).join('\n');

      const mensagem =
        `*Novo Pedido — Comanda Digital*\n\n` +
        `👤 *Cliente:* ${nome}\n` +
        `📞 *Telefone:* ${telefone}\n` +
        `🏠 *Endereço:* ${endereco}\n` +
        (observacaoGeral ? `📝 *Observação:* ${observacaoGeral}\n` : '') +
        `\n📋 *Itens:*\n${linhaItens}\n\n` +
        `💰 *Subtotal:* R$ ${subtotal.toFixed(2)}\n` +
        `🚚 *Entrega:* R$ 5,00\n` +
        `💵 *Total:* R$ ${total.toFixed(2)}\n` +
        `💳 *Pagamento:* ${pagamentoTexto}\n\n` +
        `Pedido ID: ${data.pedido_id}`;

      const numero = document.getElementById('numero-whatsapp').dataset.numero || '5567993487509';
      document.getElementById('btn-whatsapp').href =
        `https://wa.me/${numero}?text=${encodeURIComponent(mensagem)}`;

      document.getElementById('form-box').classList.remove('show');
      document.getElementById('sucesso-box').classList.add('show');
      showToast('✅ Pedido criado com sucesso!');
    } else {
      showToast('❌ Erro: ' + (data.erro || 'Erro desconhecido'));
    }
  } catch {
    showToast('❌ Erro de conexão. Tente novamente.');
  } finally {
    btn.innerHTML = '✅ Finalizar Pedido';
    btn.disabled  = false;
  }
}

// ── Inicia novo pedido ─────────────────────────────────────────
function novoPedido() {
  carrinho = [];
  renderizarCarrinho();
  ['nome', 'telefone', 'endereco'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('sucesso-box').classList.remove('show');
  showToast('🆕 Novo pedido iniciado!');
}

// ── Toast de notificação ───────────────────────────────────────
function showToast(mensagem) {
  const toast = document.getElementById('toast');
  toast.textContent = mensagem;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

// ── Lógica de pagamento/troco no carrinho ───────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Pagamento
  document.getElementById('pag-cartao-carrinho').addEventListener('change', () => {
    document.getElementById('troco-section-carrinho').style.display = 'none';
    document.getElementById('troco-valor-section-carrinho').style.display = 'none';
    document.getElementById('troco-nao-carrinho').checked = true;
    document.getElementById('troco-valor-carrinho').value = '';
  });
  document.getElementById('pag-dinheiro-carrinho').addEventListener('change', () => {
    document.getElementById('troco-section-carrinho').style.display = 'block';
  });
  // Troco
  document.getElementById('troco-nao-carrinho').addEventListener('change', () => {
    document.getElementById('troco-valor-section-carrinho').style.display = 'none';
    document.getElementById('troco-valor-carrinho').value = '';
  });
  document.getElementById('troco-sim-carrinho').addEventListener('change', () => {
    document.getElementById('troco-valor-section-carrinho').style.display = 'block';
  });
});