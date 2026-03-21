// superadmin.js

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
