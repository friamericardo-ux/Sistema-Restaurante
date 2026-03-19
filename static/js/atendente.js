/* ============================================================
   ATENDENTE — JavaScript do painel interno de mesas
============================================================ */

function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

var mesaAtual = null;

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
            btn.addEventListener('click', function() {
                adicionarDoCardapio(this.dataset.nome, parseFloat(this.dataset.preco));
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
                abrirModal(mesaAtual);
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
                abrirModal(mesaAtual);
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
            if (data.sucesso) abrirModal(mesaAtual);
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

window.onload = renderizarMesas;
