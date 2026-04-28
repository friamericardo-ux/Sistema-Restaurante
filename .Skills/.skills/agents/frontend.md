# Especialista UI/UX (React & Tailwind)

## 1. Arquitetura de Pastas (Separação de Preocupações)
- `/components`: Componentes `.jsx`/`.tsx` atômicos e reutilizáveis.
- `/styles`: Arquivos `.css` para customizações globais e @apply.
- `/hooks` ou `/js`: Lógica de estado e chamadas de API separadas da visualização.

## 2. Tecnologias Obrigatórias
- **React:** Foco em performance e reatividade granular.
- **Tailwind CSS:** Design mobile-first e classes utilitárias.
- **CSS 2026:** Utilize Scroll-Driven Animations e a função `if()` nativa para reduzir carga de JS [5].

## 3. Boas Práticas
- **Responsividade:** Teste breakpoints (sm, md, lg, xl) em todos os componentes.
- **Acessibilidade:** Utilize `contrast-color()` nativo para conformidade WCAG automática.

--------------------------------------------------------------------------------
