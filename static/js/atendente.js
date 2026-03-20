/* ============================================================
   ATENDENTE — JavaScript do painel interno de mesas
============================================================ */

function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

var mesaAtual = null;
var _itemSelecionado = null;

async function montarCardapio() {
    var grid = document.getElementById("cardapio-grid");
    grid.innerHTML = '<span style="color:#aaa;font-size:12px;">Carregando...</span>';
    try {
        var res = await fetch('/api/cardapio');
        var data = await res.json();
        grid.innerHTML = "";
        if (!data.sucesso || !data.produtos.length) {
            grid.innerHTML = '<span style="color:#aaa;font-size:12px;">Nenhum produto cadastrado.</span>';
            return;
        }
        data.produtos.forEach(function(p) {
            var btn = document.createElement('button');
            btn.className = 'btn-cardapio';
            var label = (p.emoji ? p.emoji + ' ' : '') + p.nome;
            btn.appendChild(document.createTextNode(label));
            var span = document.createElement('span');
            span.textContent = 'R$ ' + parseFloat(p.preco).toFixed(2);
            btn.appendChild(span);
            btn.dataset.nome = p.nome;
            btn.dataset.preco = p.preco;
            btn.dataset.categoria = p.categoria || '';
            btn.dataset.descricao = p.descricao || '';
            btn.addEventListener('click', function() {
                selecionarProduto({
                    nome: this.dataset.nome,
                    preco: parseFloat(this.dataset.preco),
                    categoria: this.dataset.categoria,
                    descricao: this.dataset.descricao
                });
            });
            grid.appendChild(btn);
        });
    } catch (e) {
        grid.innerHTML = '<span style="color:#aaa;font-size:12px;">Erro ao carregar produtos.</span>';
    }
}

function adicionarDoCardapio(nome, preco) {
    fetch("/api/mesa/item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ numero: mesaAtual, nome: nome, preco: preco, quantidade: 1 })
    })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.sucesso) {
                atualizarConsumoModal(mesaAtual);
            } else {
                alert("Erro: " + data.erro);
            }
        });
}

function adicionarItem() {
    var nome = document.getElementById("item-nome").value.trim();
    var preco = parseFloat(document.getElementById("item-preco").value);
    var qtd = parseInt(document.getElementById("item-qtd").value) || 1;

    if (!nome || isNaN(preco) || preco <= 0) {
        alert("Preencha o nome e o preço corretamente!");
        return;
    }

    fetch("/api/mesa/item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ numero: mesaAtual, nome: nome, preco: preco, quantidade: qtd })
    })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.sucesso) {
                document.getElementById("item-nome").value = "";
                document.getElementById("item-preco").value = "";
                document.getElementById("item-qtd").value = "1";
                atualizarConsumoModal(mesaAtual);
            } else {
                alert("Erro: " + data.erro);
            }
        });
}

// Usa item.id do banco, não o índice
function removerItem(id) {
    fetch("/api/mesa/item/remover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: id })
    })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.sucesso) atualizarConsumoModal(mesaAtual);
        });
}

function fecharMesa() {
    if (!confirm("Encerrar a mesa " + mesaAtual + "? Isso vai apagar todos os itens.")) return;
    fetch("/api/mesa/fechar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ numero: mesaAtual })
    })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.sucesso) {
                fecharModal();
            } else {
                alert("Erro: " + data.erro);
            }
        });
}

// Atualiza apenas lista de itens e total sem recarregar o cardápio
function atualizarConsumoModal(numMesa) {
    fetch("/api/mesas")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var mesa = data.mesas.find(function(m) { return m.numero == numMesa; });
            if (!mesa) return;
            var lista = document.getElementById("lista-itens-modal");
            lista.innerHTML = "";
            if (mesa.itens && mesa.itens.length > 0) {
                mesa.itens.forEach(function(item) {
                    lista.innerHTML +=
                        '<div class="item-linha">' +
                            '<span class="item-nome">' + item.quantidade + 'x ' + escapeHtml(item.nome) + '</span>' +
                            '<span class="item-preco">R$ ' + (item.preco * item.quantidade).toFixed(2) + '</span>' +
                            '<button class="btn-remover" onclick="removerItem(' + item.id + ')">✖</button>' +
                        '</div>';
                });
            } else {
                lista.innerHTML = "<p style='color:#aaa;'>Nenhum item ainda.</p>";
            }
            document.getElementById("total-modal").innerText = "Total: R$ " + mesa.total.toFixed(2);
        });
}

function abrirModal(numMesa) {
    mesaAtual = numMesa;
    montarCardapio();
    fetch("/api/mesas")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var mesa = data.mesas.find(function(m) { return m.numero == numMesa; });
            if (!mesa) return;

            document.getElementById("modal-titulo").innerText = "🍽️ MESA " + mesa.numero;

            var lista = document.getElementById("lista-itens-modal");
            lista.innerHTML = "";
            if (mesa.itens && mesa.itens.length > 0) {
                mesa.itens.forEach(function(item) {
                    lista.innerHTML +=
                        '<div class="item-linha">' +
                            '<span class="item-nome">' + item.quantidade + 'x ' + escapeHtml(item.nome) + '</span>' +
                            '<span class="item-preco">R$ ' + (item.preco * item.quantidade).toFixed(2) + '</span>' +
                            '<button class="btn-remover" onclick="removerItem(' + item.id + ')">✖</button>' +
                        '</div>';
                });
            } else {
                lista.innerHTML = "<p style='color:#aaa;'>Nenhum item ainda.</p>";
            }

            document.getElementById("total-modal").innerText = "Total: R$ " + mesa.total.toFixed(2);
            document.getElementById("modalItens").classList.add("ativo");
        });
}

function fecharModal() {
    document.getElementById("modalItens").classList.remove("ativo");
    mesaAtual = null;
    renderizarMesas();
}

function renderizarMesas() {
    fetch("/api/mesas")
        .then(function(res) { return res.json(); })
        .then(function(data) {
            var container = document.getElementById("lista-mesas");
            container.innerHTML = "";
            if (data.sucesso && data.mesas) {
                data.mesas.forEach(function(m) {
                    container.innerHTML +=
                        '<div class="mesa-card" onclick="abrirModal(' + m.numero + ')">' +
                            '<strong style="color:#f5a623;font-size:1.2rem;">MESA ' + m.numero + '</strong><br>' +
                            '<span style="color:#4caf50;font-weight:bold;">R$ ' + m.total.toFixed(2) + '</span><br>' +
                            '<small style="color:#aaa;">' + (m.itens ? m.itens.length : 0) + ' item(s)</small>' +
                        '</div>';
                });
            }
        });
}

function abrirModalNovaMesa() {
    var num = prompt("Digite o número da mesa:");
    if (num) {
        fetch("/api/mesa/abrir", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ numero: num })
        })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.sucesso) {
                    renderizarMesas();
                } else {
                    alert("Erro: " + data.erro);
                }
            });
    }
}

// Mostra adicionais disponíveis para o produto clicado
async function selecionarProduto(produto) {
    _itemSelecionado = { nome: produto.nome, preco: produto.preco };
    document.getElementById('adicionais-produto-label').textContent =
        produto.nome + '  —  R$ ' + produto.preco.toFixed(2);
    document.getElementById('adicionais-produto-desc').textContent = produto.descricao || '';
    var lista = document.getElementById('adicionais-lista');
    lista.innerHTML = '<span style="color:#aaa;font-size:12px;">Carregando adicionais...</span>';
    document.getElementById('adicionais-area').style.display = 'block';
    try {
        var url = '/api/adicionais' + (produto.categoria ? '?categoria=' + encodeURIComponent(produto.categoria) : '');
        var res = await fetch(url);
        var data = await res.json();
        lista.innerHTML = '';
        if (data.sucesso && data.adicionais.length > 0) {
            data.adicionais.forEach(function(a) {
                var lbl = document.createElement('label');
                lbl.style.cssText = 'display:inline-flex;align-items:center;gap:4px;background:#2a2a2a;padding:4px 10px;border-radius:4px;cursor:pointer;color:#ddd;font-size:13px;';
                var cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.dataset.nome = a.nome;
                cb.dataset.preco = a.preco;
                lbl.appendChild(cb);
                lbl.appendChild(document.createTextNode(
                    a.nome + (parseFloat(a.preco) > 0 ? '  +R$' + parseFloat(a.preco).toFixed(2) : '')
                ));
                lista.appendChild(lbl);
            });
        } else {
            lista.innerHTML = '<span style="color:#aaa;font-size:12px;">Sem adicionais para esta categoria.</span>';
        }
    } catch (e) {
        lista.innerHTML = '<span style="color:#aaa;font-size:12px;">Erro ao carregar adicionais.</span>';
    }
}

// Confirma adição do item com os adicionais selecionados
function confirmarItemComAdicionais() {
    if (!_itemSelecionado) return;
    var checkboxes = document.querySelectorAll('#adicionais-lista input[type=checkbox]:checked');
    var adicionais = [];
    checkboxes.forEach(function(cb) {
        adicionais.push({ nome: cb.dataset.nome, preco: parseFloat(cb.dataset.preco) });
    });
    var nomeCompleto = _itemSelecionado.nome;
    var precoTotal = _itemSelecionado.preco;
    if (adicionais.length > 0) {
        nomeCompleto += ' (+ ' + adicionais.map(function(a) { return a.nome; }).join(', ') + ')';
        precoTotal += adicionais.reduce(function(s, a) { return s + a.preco; }, 0);
    }
    cancelarAdicionais();
    adicionarDoCardapio(nomeCompleto, precoTotal);
}

// Oculta a área de adicionais
function cancelarAdicionais() {
    _itemSelecionado = null;
    document.getElementById('adicionais-area').style.display = 'none';
    document.getElementById('adicionais-lista').innerHTML = '';
}

window.onload = renderizarMesas;
