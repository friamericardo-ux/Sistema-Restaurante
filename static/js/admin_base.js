(function() {
  let ultimoTotal = null;

  function tocarNotificacao() {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    function beep(freq, start, duration, volume) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'square';
      osc.frequency.setValueAtTime(freq, ctx.currentTime + start);
      gain.gain.setValueAtTime(volume, ctx.currentTime + start);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + duration);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + duration);
    }
    beep(880, 0.0, 0.18, 1.5);
    beep(880, 0.20, 0.18, 1.5);
    beep(880, 0.40, 0.18, 1.5);
    beep(880, 0.60, 0.18, 1.5);
    beep(880, 0.80, 0.18, 1.5);
    beep(1100, 1.05, 0.35, 1.8);
  }

  function checar() {
    fetch('/api/novos-pedidos')
      .then(r => r.json())
      .then(data => {
        if (ultimoTotal !== null && data.pendentes > ultimoTotal) {
          tocarNotificacao();
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
