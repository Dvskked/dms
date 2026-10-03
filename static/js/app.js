/* ==========================================================================
   THE DIAMONDS LEAGUE — interaccion de la pagina publica
   Sin dependencias. Todo degrada bien si JS no carga.
   ========================================================================== */
(function () {
    "use strict";

    const $ = (sel, ctx = document) => ctx.querySelector(sel);
    const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* ---------------------------------------------------------------- Splash */
    function splash() {
        const el = $(".splash");
        if (!el) return;
        const finish = () => el.classList.add("hidden");
        if (reduceMotion) {
            setTimeout(finish, 200);
        } else {
            setTimeout(finish, 1650);
        }
        window.addEventListener("load", () => setTimeout(finish, 400), { once: true });
        document.addEventListener("keydown", finish, { once: true });
    }

    /* ------------------------------------------------------------- Menu movil */
    function mobileMenu() {
        const toggle = $(".menu-toggle");
        const menu = $(".mobile-menu");
        if (!toggle || !menu) return;

        const setOpen = (open) => {
            toggle.setAttribute("aria-expanded", String(open));
            toggle.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
            menu.classList.toggle("open", open);
            menu.setAttribute("aria-hidden", String(!open));
            document.body.classList.toggle("no-scroll", open && window.innerWidth < 1121);
        };

        toggle.addEventListener("click", () => setOpen(toggle.getAttribute("aria-expanded") !== "true"));
        $$("a", menu).forEach((a) => a.addEventListener("click", () => setOpen(false)));
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") setOpen(false);
        });
        window.addEventListener("resize", () => {
            if (window.innerWidth > 1120) setOpen(false);
        });
    }

    /* --------------------------------------------------------- Tuerca (gear) */
    function gearMenu() {
        const wrap = $(".gear");
        if (!wrap) return;
        const button = $(".gear-button", wrap);
        const menu = $(".gear-menu", wrap);
        if (!button || !menu) return;

        const setOpen = (open) => {
            button.setAttribute("aria-expanded", String(open));
            menu.classList.toggle("open", open);
        };

        button.addEventListener("click", (e) => {
            e.stopPropagation();
            setOpen(button.getAttribute("aria-expanded") !== "true");
        });
        document.addEventListener("click", (e) => {
            if (!wrap.contains(e.target)) setOpen(false);
        });
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") setOpen(false);
        });
    }

    /* ----------------------------------------------------------- Smooth scroll */
    function smoothScroll() {
        const header = $(".topbar");
        const offset = () => (header ? header.offsetHeight + 8 : 72);

        document.addEventListener("click", (e) => {
            const link = e.target.closest('a[href^="#"]');
            if (!link) return;
            const id = link.getAttribute("href");
            if (!id || id === "#" || link.hasAttribute("data-no-scroll")) return;
            const target = document.getElementById(id.slice(1));
            if (!target) return;

            e.preventDefault();
            const top = target.getBoundingClientRect().top + window.scrollY - offset();
            window.scrollTo({ top, behavior: reduceMotion ? "auto" : "smooth" });
            history.replaceState(null, "", id);

            const menu = $(".mobile-menu");
            const toggle = $(".menu-toggle");
            if (menu && menu.classList.contains("open")) {
                menu.classList.remove("open");
                if (toggle) toggle.setAttribute("aria-expanded", "false");
                document.body.classList.remove("no-scroll");
            }
        });
    }

    /* ------------------------------------------------------- Scroll spy + topbar */
    function scrollSpy() {
        const topbar = $(".topbar");
        const sections = $$("section[data-section], [data-spy]");
        if (!sections.length) return;

        const navLinks = $$('[data-spy-link]');
        let ticking = false;

        const update = () => {
            ticking = false;
            const y = window.scrollY;
            if (topbar) topbar.classList.toggle("is-scrolled", y > 24);

            const offset = (topbar ? topbar.offsetHeight : 72) + 90;
            let activeId = sections[0].id;
            for (const section of sections) {
                if (section.getBoundingClientRect().top - offset <= 0) activeId = section.id;
            }
            navLinks.forEach((link) => {
                const match = link.getAttribute("href") === `#${activeId}`;
                link.classList.toggle("is-active", match);
                if (match) link.setAttribute("aria-current", "true");
                else link.removeAttribute("aria-current");
            });
        };

        window.addEventListener("scroll", () => {
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(update);
            }
        }, { passive: true });
        update();
    }

    /* ------------------------------------------------------------------ Tabs */
    function tabs() {
        $$("[data-tabs]").forEach((group) => {
            const name = group.dataset.tabs;
            const scope = group.closest("[data-tabs-scope]") || document;
            const buttons = $$(`[data-tab-target^="${name}:"]`, scope);
            const panels = $$(`[data-tab-panel^="${name}:"]`, scope);

            buttons.forEach((btn) => {
                btn.addEventListener("click", () => {
                    const key = btn.dataset.tabTarget.split(":")[1];
                    buttons.forEach((b) => {
                        const on = b === btn;
                        b.classList.toggle("active", on);
                        b.setAttribute("aria-selected", String(on));
                    });
                    panels.forEach((p) => p.classList.toggle("active", p.dataset.tabPanel.split(":")[1] === key));
                    const scroller = $("[data-tab-scroll]", scope);
                    if (scroller) scroller.scrollTo({ left: btn.offsetLeft - 12, behavior: reduceMotion ? "auto" : "smooth" });
                });
            });
        });
    }

    /* ------------------------------------------------- Filtros del museo */
    function filters() {
        $$("[data-filter-group]").forEach((bar) => {
            const scope = $(`[data-filter-scope="${bar.dataset.filterGroup}"]`) || document;
            const chips = $$("[data-filter]", bar);
            const items = $$("[data-filter-item]", scope);

            chips.forEach((chip) => {
                chip.addEventListener("click", () => {
                    const value = chip.dataset.filter;
                    chips.forEach((c) => {
                        const on = c === chip;
                        c.classList.toggle("active", on);
                        c.setAttribute("aria-selected", String(on));
                    });
                    let shown = 0;
                    items.forEach((item) => {
                        const cats = (item.dataset.filterItem || "").split(/\s+/);
                        const show = value === "all" || cats.indexOf(value) !== -1;
                        item.hidden = !show;
                        if (show) {
                            shown += 1;
                            item.classList.remove("reveal");
                            requestAnimationFrame(() => item.classList.add("reveal", "is-visible"));
                        }
                    });
                    const empty = $("[data-filter-empty]", scope);
                    if (empty) empty.hidden = shown !== 0;
                    const counter = $("[data-filter-shown]", bar) || $("[data-filter-count]", bar);
                    if (counter) counter.textContent = shown;
                });
            });
        });
    }

    /* ------------------------------------------------------------- Lightbox */
    function lightbox() {
        const box = $(".lightbox");
        if (!box) return;
        const img = $("img", box);
        const cap = $("p", box);
        const closeBtn = $(".lightbox-close", box);
        let lastFocus = null;

        const open = (src, title) => {
            lastFocus = document.activeElement;
            img.src = src;
            img.alt = title || "";
            if (cap) cap.textContent = title || "";
            box.classList.add("open");
            box.setAttribute("aria-hidden", "false");
            document.body.classList.add("no-scroll");
            if (closeBtn) closeBtn.focus();
        };
        const close = () => {
            box.classList.remove("open");
            box.setAttribute("aria-hidden", "true");
            document.body.classList.remove("no-scroll");
            if (lastFocus) lastFocus.focus();
        };

        document.addEventListener("click", (e) => {
            const trigger = e.target.closest("[data-lightbox-src], [data-lightbox][data-full]");
            if (!trigger) return;
            e.preventDefault();
            if (trigger.dataset.lightboxSrc) {
                open(trigger.dataset.lightboxSrc, trigger.dataset.lightboxTitle || "");
            } else {
                open(trigger.dataset.full, trigger.dataset.caption || "");
            }
        });
        if (closeBtn) closeBtn.addEventListener("click", close);
        box.addEventListener("click", (e) => {
            if (e.target === box) close();
        });
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && box.classList.contains("open")) close();
        });
    }

    /* ---------------------------------------------------------------- Reveal */
    function reveal() {
        const items = $$(".reveal");
        if (!items.length) return;
        if (reduceMotion || !("IntersectionObserver" in window)) {
            items.forEach((el) => el.classList.add("is-visible"));
            return;
        }
        const io = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                const el = entry.target;
                const delay = Number(el.dataset.revealDelay || 0);
                setTimeout(() => el.classList.add("is-visible"), delay);
                io.unobserve(el);
            });
        }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
        items.forEach((el) => io.observe(el));
    }

    /* ----------------------------------------------------------------- Flash */
    function flash() {
        const stack = $(".flash-stack");
        if (!stack) return;
        $$(".flash", stack).forEach((el, i) => {
            const hide = () => {
                el.classList.add("is-hiding");
                setTimeout(() => el.remove(), 400);
            };
            setTimeout(hide, 5200 + i * 400);
            el.addEventListener("click", hide);
        });
    }

    /* --------------------------------------------------------- Copiar alias */
    function copyButtons() {
        document.addEventListener("click", async (e) => {
            const btn = e.target.closest("[data-copy]");
            if (!btn) return;
            e.preventDefault();
            const text = btn.dataset.copy;
            const original = btn.textContent;
            const label = btn.dataset.copied || "COPIADO";
            try {
                await navigator.clipboard.writeText(text);
                btn.textContent = label;
            } catch {
                const ta = document.createElement("textarea");
                ta.value = text;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                ta.remove();
                btn.textContent = label;
            }
            setTimeout(() => { btn.textContent = original; }, 1600);
        });
    }

    /* ---------------------------------------------------- Ver/ocultar password */
    function passwordToggles() {
        $$("[data-pw-toggle]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const input = document.getElementById(btn.dataset.pwToggle);
                if (!input) return;
                const show = input.type === "password";
                input.type = show ? "text" : "password";
                btn.textContent = show ? "OCULTAR" : "VER";
                btn.setAttribute("aria-pressed", String(show));
                btn.setAttribute("aria-label", show ? "Ocultar contraseña" : "Ver contraseña");
            });
        });
    }

    /* --------------------------------------------------------- Anclas del hero */
    function heroActions() {
        $$("[data-scroll]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const target = document.getElementById(btn.dataset.scroll);
                if (!target) return;
                const header = $(".topbar");
                const top = target.getBoundingClientRect().top + window.scrollY - (header ? header.offsetHeight + 8 : 72);
                window.scrollTo({ top, behavior: reduceMotion ? "auto" : "smooth" });
            });
        });
    }

    /* ------------------------------------------------------------- Contadores */
    function counters() {
        const items = $$("[data-count]");
        if (!items.length || reduceMotion) {
            items.forEach((el) => { el.textContent = el.dataset.count; });
            return;
        }
        const io = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                const el = entry.target;
                const target = parseFloat(el.dataset.count) || 0;
                const suffix = el.dataset.suffix || "";
                const dur = 1100;
                const start = performance.now();
                const tick = (now) => {
                    const p = Math.min((now - start) / dur, 1);
                    const eased = 1 - Math.pow(1 - p, 3);
                    el.textContent = (target % 1 === 0 ? Math.round(target * eased) : (target * eased).toFixed(1)) + suffix;
                    if (p < 1) requestAnimationFrame(tick);
                };
                requestAnimationFrame(tick);
                io.unobserve(el);
            });
        }, { threshold: 0.4 });
        items.forEach((el) => io.observe(el));
    }

    /* ---------------------------------------------------------------- Parallax */
    function parallax() {
        const items = $$("[data-parallax]");
        if (!items.length || reduceMotion) return;

        const update = () => {
            const vh = window.innerHeight;
            items.forEach((el) => {
                const box = el.getBoundingClientRect();
                if (box.bottom < -80 || box.top > vh + 80) return;
                const offset = (box.top + box.height / 2 - vh / 2) * -0.06;
                el.style.transform = `translate3d(0, ${offset.toFixed(1)}px, 0) scale(1.12)`;
            });
        };

        let ticking = false;
        window.addEventListener("scroll", () => {
            if (ticking) return;
            ticking = true;
            window.requestAnimationFrame(() => { ticking = false; update(); });
        }, { passive: true });
        window.addEventListener("resize", update, { passive: true });
        update();
    }

    /* ----------------------------------------------------------------- Init */
    function init() {
        splash();
        mobileMenu();
        gearMenu();
        smoothScroll();
        scrollSpy();
        tabs();
        filters();
        lightbox();
        reveal();
        flash();
        copyButtons();
        passwordToggles();
        heroActions();
        counters();
        parallax();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();