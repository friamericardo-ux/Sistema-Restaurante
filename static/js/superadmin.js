// superadmin.js

function gerarSlug(nome) {
    return nome
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .trim()
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-');
}

document.addEventListener('DOMContentLoaded', function () {
    const nomeInput = document.getElementById('novo-nome');
    const slugPreview = document.getElementById('slug-preview');
    if (nomeInput && slugPreview) {
        nomeInput.addEventListener('input', function () {
            const slug = gerarSlug(this.value);
            slugPreview.textContent = slug ? '/cardapio/' + slug : '';
        });
    }
});

async function criarRestaurante() {
    const nome = document.getElementById('novo-nome').value.trim();
    const username = document.getElementById('novo-username').value.trim();
    const senha = document.getElementById('novo-senha').value.trim();
    const msg = document.getElementById('criar-msg');

    if (!nome || !username || !senha) {
        msg.style.color = '#ef5350';
        msg.textContent = 'Preencha todos os campos.';
        return;
    }

    const res = await fetch('/superadmin/criar-restaurante', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome, username, senha })
    });
    const data = await res.json();

    if (data.sucesso) {
        msg.style.color = '#66bb6a';
        msg.textContent = `Restaurante criado! Acesso em ${data.url}`;
        setTimeout(() => location.reload(), 1500);
    } else {
        msg.style.color = '#ef5350';
        msg.textContent = data.erro || 'Erro ao criar restaurante.';
    }
}

async function renovar(userId, dias) {
    const res = await fetch(`/superadmin/renovar/${userId}/${dias}`, { method: 'POST' });
    const data = await res.json();
    if (data.sucesso) location.reload();
}

async function bloquear(userId, username) {
    if (!confirm(`Bloquear "${username}"? O cardápio ficará inacessível imediatamente.`)) return;
    const res = await fetch(`/superadmin/bloquear/${userId}`, { method: 'POST' });
    const data = await res.json();
    if (data.sucesso) location.reload();
}
