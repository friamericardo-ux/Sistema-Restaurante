// ── Google Maps Autocomplete + Cálculo de Frete ──

let mapsConfig = null;
let autocomplete = null;
let freteCalculado = null;

// ── Carrega configuração do Maps ──
async function carregarMapsConfig() {
  try {
    const res = await fetch('/api/maps/config');
    const data = await res.json();
    if (data.sucesso && data.api_key) {
      mapsConfig = data;
      carregarGoogleMapsScript(data.api_key);
    }
  } catch (e) {
    console.log('Google Maps não configurado.');
  }
}

// ── Injeta o script do Google Maps ──
function carregarGoogleMapsScript(apiKey) {
  if (!apiKey) return;
  const script = document.createElement('script');
  script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places&callback=inicializarAutocomplete`;
  script.async = true;
  script.defer = true;
  document.head.appendChild(script);
}

// ── Callback do Google Maps ──
function inicializarAutocomplete() {
  const input = document.getElementById('endereco');
  if (!input) return;

  // Criar campo de input para autocomplete (substitui o textarea)
  const inputAutocomplete = document.createElement('input');
  inputAutocomplete.type = 'text';
  inputAutocomplete.id = 'endereco';
  inputAutocomplete.placeholder = 'Digite o endereço para buscar...';
  inputAutocomplete.autocomplete = 'off';
  inputAutocomplete.maxLength = 300;
  inputAutocomplete.style.cssText = input.style.cssText;
  inputAutocomplete.className = input.className;
  // Copiar estilos do textarea
  inputAutocomplete.style.width = '100%';
  inputAutocomplete.style.padding = input.style.padding || '12px 14px';

  input.parentNode.replaceChild(inputAutocomplete, input);

  autocomplete = new google.maps.places.Autocomplete(inputAutocomplete, {
    types: ['address'],
    componentRestrictions: { country: 'br' },
    fields: ['formatted_address', 'geometry']
  });

  autocomplete.addListener('place_changed', onPlaceSelected);

  // Adicionar container de frete depois do campo
  const freteContainer = document.createElement('div');
  freteContainer.id = 'frete-info';
  freteContainer.style.cssText = 'display:none; margin-top:8px; padding:10px 14px; background:#1a1a1a; border:1px solid #2e2e2e; border-radius:10px; font-size:13px; color:#f0f0f0;';
  inputAutocomplete.parentNode.appendChild(freteContainer);
}

// ── Quando endereço é selecionado ──
async function onPlaceSelected() {
  const place = autocomplete.getPlace();
  if (!place || !place.geometry) return;

  const lat = place.geometry.location.lat();
  const lng = place.geometry.location.lng();

  try {
    const res = await fetch('/api/maps/calcular-frete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lng })
    });
    const data = await res.json();

    if (data.sucesso) {
      freteCalculado = data.frete;
      window._freteCalculado = data.frete;
      window.taxaEntrega = data.frete;
      const freteInfo = document.getElementById('frete-info');
      freteInfo.style.display = 'block';
      freteInfo.innerHTML = `
        📍 <strong>${data.distancia_km} km</strong> de distância
        &nbsp;—&nbsp;
        🚚 Frete: <strong style="color:#ff6b2b">R$ ${data.frete.toFixed(2).replace('.', ',')}</strong>
      `;

      // Atualizar total no carrinho se existir a função
      atualizarFreteNoCarrinho(data.frete);
    }
  } catch (e) {
    console.error('Erro ao calcular frete:', e);
  }
}

// ── Atualiza frete no carrinho ──
function atualizarFreteNoCarrinho(frete) {
  window._freteCalculado = frete;
  window.taxaEntrega = frete;

  // Atualiza display de entrega
  const elEntrega = document.getElementById('cart-entrega');
  if (elEntrega) elEntrega.textContent = 'R$ ' + frete.toFixed(2).replace('.', ',');

  // Recalcula total
  if (typeof atualizarTotal === 'function') {
    atualizarTotal();
  } else {
    // fallback manual
    const elTotal = document.getElementById('cart-total');
    const elSub = document.getElementById('cart-subtotal');
    if (elTotal && elSub) {
      const subtotal = parseFloat(
        elSub.textContent.replace('R$', '').replace(',', '.').trim()
      ) || 0;
      elTotal.textContent = 'R$ ' + (subtotal + frete).toFixed(2).replace('.', ',');
    }
  }
}

// ── Inicialização ──
carregarMapsConfig();
