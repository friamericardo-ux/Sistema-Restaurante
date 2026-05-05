(function() {
  let ultimoTotal = null;

  function criarSom() {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    function beep(freq, start, dur) {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.frequency.value = freq;
      o.type = 'sine';
      g.gain.setValueAtTime(0.4, ctx.currentTime + start);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
      o.start(ctx.currentTime + start);
      o.stop(ctx.currentTime + start + dur + 0.05);
    }
    beep(880, 0,    0.15);
    beep(1100, 0.2, 0.15);
    beep(880, 0.4,  0.15);
  }

  function checar() {
    fetch('/api/novos-pedidos')
      .then(r => r.json())
      .then(data => {
        if (ultimoTotal !== null && data.pendentes > ultimoTotal) {
          criarSom();
          if (Notification.permission === 'granted') {
            new Notification('🛵 Novo pedido!', { body: data.pendentes + ' pedido(s) aguardando.' });
          }
        }
        ultimoTotal = data.pendentes;
      })
      .catch(() => {});
  }

  if (Notification.permission === 'default') {
    Notification.requestPermission();
  }

  setInterval(checar, 15000);
  checar();
})();
