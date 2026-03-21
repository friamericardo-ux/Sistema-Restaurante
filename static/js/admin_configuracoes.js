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


// --- Toggle ativo/bloqueado ---
const toggleAtivo = document.getElementById('toggle-ativo');
const hiddenAtivo = document.getElementById('restaurante_ativo_hidden');
const toggleLabel = document.getElementById('toggle-label');

function atualizarToggleLabel() {
  if (toggleAtivo.checked) {
    toggleLabel.innerHTML = '<span class="status-ativo">✅ Restaurante Ativo</span>';
    hiddenAtivo.value = '1';
  } else {
    toggleLabel.innerHTML = '<span class="status-bloqueado">🔒 Restaurante Bloqueado</span>';
    hiddenAtivo.value = '0';
  }
}

if (toggleAtivo) {
  toggleAtivo.addEventListener('change', function () {
    if (!this.checked) {
      const confirmar = confirm(
        'Tem certeza? O cardápio ficará inacessível para os clientes.'
      );
      if (!confirmar) {
        this.checked = true;
        return;
      }
    }
    atualizarToggleLabel();
  });
}
