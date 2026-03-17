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

});