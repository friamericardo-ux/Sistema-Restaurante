/* ============================================================
   admin_adicionais.js — interações da página de adicionais
============================================================ */

document.addEventListener('DOMContentLoaded', function () {

  // ── Toggle visual dos chips de categoria (formulário de cadastro) ──
  document.querySelectorAll('.categorias-grid:not(#editCategorias) .categoria-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      const cb = this.querySelector('input[type="checkbox"]');
      setTimeout(() => {
        this.classList.toggle('ativa', cb.checked);
      }, 0);
    });
  });

  // ── Proteção double-submit no formulário de cadastro ──
  document.getElementById('formAdicionar').addEventListener('submit', function () {
    const btn = document.getElementById('btnAdicionar');
    btn.disabled = true;
    btn.textContent = 'Salvando...';
  });

  // ── Abrir modal de edição ──
  document.querySelectorAll('.btn-editar').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const id         = this.dataset.id;
      const nome       = this.dataset.nome;
      const preco      = this.dataset.preco;
      const categorias = JSON.parse(this.dataset.categorias || '[]');

      document.getElementById('editNome').value  = nome;
      document.getElementById('editPreco').value = preco;
      document.getElementById('formEditar').action = '/admin/adicionais/editar/' + id;

      // Marcar chips do modal
      document.querySelectorAll('#editCategorias .categoria-chip').forEach(function (chip) {
        const cb  = chip.querySelector('input[type="checkbox"]');
        const cat = chip.dataset.cat;
        cb.checked = categorias.includes(cat);
        chip.classList.toggle('ativa', cb.checked);

        // Garantir toggle ao clicar dentro do modal
        chip.onclick = function () {
          setTimeout(() => {
            chip.classList.toggle('ativa', cb.checked);
          }, 0);
        };
      });

      document.getElementById('modalEditar').classList.add('aberto');
    });
  });

  // ── Fechar modal ──
  function fecharModal() {
    document.getElementById('modalEditar').classList.remove('aberto');
  }

  document.getElementById('btnFecharModal').addEventListener('click', fecharModal);

  document.getElementById('modalEditar').addEventListener('click', function (e) {
    if (e.target === this) fecharModal();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') fecharModal();
  });

  // ── Excluir adicional via fetch (delegação) ──
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.btn-excluir');
    if (!btn) return;

    var id   = btn.dataset.id;
    var nome = btn.dataset.nome;

    if (!confirm('Tem certeza que deseja excluir "' + nome + '" permanentemente?')) return;

    var csrfToken = document.querySelector('[name=csrf_token]');
    if (!csrfToken) return;
    csrfToken = csrfToken.value;

    fetch('/admin/adicionais/excluir/' + id, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken
      }
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.sucesso) {
          var item = btn.closest('.adicional-item');
          if (item) item.remove();
        }
      })
      .catch(function () {
        alert('Erro ao excluir adicional. Tente novamente.');
      });
  });

});