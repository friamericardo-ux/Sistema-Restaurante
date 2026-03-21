// admin_configuracoes.js

// --- Máscara e preview do WhatsApp ---
const whatsappInput = document.getElementById('whatsapp_restaurante');
const whatsappPreview = document.getElementById('whatsapp-preview');

function atualizarPreviewWhatsapp() {
  const raw = whatsappInput.value.replace(/\D/g, '');
  if (raw.length >= 10) {
    const numero = raw.startsWith('55') ? raw : '55' + raw;
    whatsappPreview.innerHTML = `Link: <a href="https://wa.me/${numero}" target="_blank">wa.me/${numero}</a>`;
  } else {
    whatsappPreview.textContent = '';
  }
}

function aplicarMascaraTelefone(input) {
  let v = input.value.replace(/\D/g, '');
  if (v.length > 13) v = v.slice(0, 13);
  // Formata como: 55 (67) 99348-7509
  if (v.length <= 2) {
    input.value = v;
  } else if (v.length <= 4) {
    input.value = `${v.slice(0,2)} (${v.slice(2)}`;
  } else if (v.length <= 9) {
    input.value = `${v.slice(0,2)} (${v.slice(2,4)}) ${v.slice(4)}`;
  } else if (v.length <= 13) {
    const corpo = v.slice(4);
    const parte1 = corpo.slice(0, corpo.length - 4);
    const parte2 = corpo.slice(-4);
    input.value = `${v.slice(0,2)} (${v.slice(2,4)}) ${parte1}-${parte2}`;
  }
}

if (whatsappInput) {
  whatsappInput.addEventListener('input', function () {
    aplicarMascaraTelefone(this);
    atualizarPreviewWhatsapp();
  });
  atualizarPreviewWhatsapp();
}


// --- Toggle abrir/fechar estabelecimento ---
const btnToggle = document.getElementById('btn-toggle-status');
const statusBadge = document.getElementById('status-badge');
const avisoWhatsapp = document.getElementById('aviso-whatsapp');
const nomeRestaurante = document.querySelector('input[name="nome_restaurante"]');

function atualizarStatusUI(ativo) {
  const aberto = ativo === '1';

  statusBadge.innerHTML = aberto
    ? '<span class="badge-aberto">🟢 Aberto — recebendo pedidos</span>'
    : '<span class="badge-fechado">🔴 Fechado — não recebe pedidos</span>';

  btnToggle.textContent = aberto ? '🔒 Fechar Estabelecimento' : '🔓 Abrir Estabelecimento';
  btnToggle.className = 'btn-toggle-status ' + (aberto ? 'btn-fechar' : 'btn-abrir');
  btnToggle.dataset.ativo = ativo;

  if (!aberto) {
    const nome = (nomeRestaurante ? nomeRestaurante.value.trim() : '') || 'o restaurante';
    const msg = encodeURIComponent(
      `Olá! Informamos que ${nome} está fechado no momento e não está recebendo pedidos. Em breve voltamos! 🙏`
    );
    const linkEl = document.getElementById('link-whatsapp-fechado');
    if (linkEl) linkEl.href = `https://api.whatsapp.com/send?text=${msg}`;
    avisoWhatsapp.classList.remove('hidden');
  } else {
    avisoWhatsapp.classList.add('hidden');
  }
}

if (btnToggle) {
  btnToggle.addEventListener('click', function () {
    const ativo = this.dataset.ativo;
    const fechando = ativo === '1';

    if (fechando) {
      const confirmar = confirm('Fechar o estabelecimento agora? Os clientes não poderão fazer pedidos.');
      if (!confirmar) return;
    }

    btnToggle.disabled = true;
    btnToggle.textContent = 'Aguarde...';

    fetch('/admin/toggle-status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrf_token]') ? document.querySelector('[name=csrf_token]').value : '' },
    })
      .then(r => r.json())
      .then(data => {
        atualizarStatusUI(data.restaurante_ativo);
      })
      .catch(() => {
        alert('Erro ao alterar o status. Tente novamente.');
        btnToggle.disabled = false;
        atualizarStatusUI(ativo);
      })
      .finally(() => {
        btnToggle.disabled = false;
      });
  });
}
