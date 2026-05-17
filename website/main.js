const body = document.body;
const menuButton = document.querySelector('.menu-button');
const mobileMenu = document.querySelector('#mobile-menu');

if (menuButton && mobileMenu) {
    const setMenuOpen = (isOpen) => {
        body.classList.toggle('menu-open', isOpen);
        menuButton.setAttribute('aria-expanded', String(isOpen));
        mobileMenu.setAttribute('aria-hidden', String(!isOpen));
    };

    menuButton.addEventListener('click', () => {
        setMenuOpen(!body.classList.contains('menu-open'));
    });

    mobileMenu.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', () => setMenuOpen(false));
    });
}

const revealTargets = document.querySelectorAll('[data-reveal]');
const revealObserver = new IntersectionObserver(
    (entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                revealObserver.unobserve(entry.target);
            }
        });
    },
    {
        threshold: 0.18,
        rootMargin: '0px 0px -8% 0px',
    },
);

revealTargets.forEach((target) => revealObserver.observe(target));
