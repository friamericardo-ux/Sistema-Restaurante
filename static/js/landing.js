document.addEventListener('DOMContentLoaded', function () {
    const header = document.getElementById('header');
    const mobileToggle = document.getElementById('mobile-toggle');
    const nav = document.getElementById('nav');
    const navLinks = document.querySelectorAll('.nav-link');
    const landingForm = document.getElementById('landing-form');

    // ---- Sticky header ----
    window.addEventListener('scroll', function () {
        header.classList.toggle('scrolled', window.scrollY > 40);
    });

    // ---- Mobile menu ----
    if (mobileToggle && nav) {
        mobileToggle.addEventListener('click', function () {
            this.classList.toggle('active');
            nav.classList.toggle('active');
            document.body.style.overflow = nav.classList.contains('active') ? 'hidden' : '';
        });

        navLinks.forEach(function (link) {
            link.addEventListener('click', function () {
                mobileToggle.classList.remove('active');
                nav.classList.remove('active');
                document.body.style.overflow = '';
            });
        });
    }

    // ---- Active nav link on scroll ----
    var sections = document.querySelectorAll('section[id]');
    window.addEventListener('scroll', function () {
        var scrollY = window.pageYOffset + 120;
        sections.forEach(function (section) {
            var top = section.offsetTop;
            var height = section.offsetHeight;
            var id = section.getAttribute('id');
            var link = document.querySelector('.nav-link[href="#' + id + '"]');
            if (link) {
                if (scrollY >= top && scrollY < top + height) {
                    navLinks.forEach(function (l) { l.classList.remove('active'); });
                    link.classList.add('active');
                }
            }
        });
    });

    // ---- Smooth scroll ----
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            var targetId = this.getAttribute('href');
            if (targetId === '#') return;
            var target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                var offset = 80;
                var top = target.getBoundingClientRect().top + window.pageYOffset - offset;
                window.scrollTo({ top: top, behavior: 'smooth' });
            }
        });
    });

    // ---- Reveal on scroll ----
    var revealEls = document.querySelectorAll('[data-reveal]');
    var revealObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
                revealObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    revealEls.forEach(function (el) { revealObserver.observe(el); });

    // ---- Contact form ----
    if (landingForm) {
        landingForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var btn = this.querySelector('button');
            var original = btn.innerHTML;

            btn.disabled = true;
            btn.innerHTML = '<span>Enviando...</span><i class="fas fa-spinner fa-spin"></i>';

            setTimeout(function () {
                btn.innerHTML = '<span>Mensagem Enviada!</span><i class="fas fa-check"></i>';
                btn.style.background = '#22c55e';
                btn.style.boxShadow = '0 8px 30px rgba(34,197,94,0.2)';
                landingForm.reset();

                setTimeout(function () {
                    btn.disabled = false;
                    btn.innerHTML = original;
                    btn.style.background = '';
                    btn.style.boxShadow = '';
                }, 3000);
            }, 1200);
        });
    }
});