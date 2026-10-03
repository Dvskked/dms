/* ==========================================================================
   Panel de administracion — comportamiento propio del dashboard
   ========================================================================== */
(function () {
    "use strict";

    const $ = (s, c = document) => c.querySelector(s);
    const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));

    /* -------------------------------------------------- Navegacion lateral movil */
    function nav() {
        const shell = $(".admin-shell");
        const toggle = $(".admin-nav-toggle");
        const scrim = $(".admin-scrim");
        if (!shell || !toggle) return;
        const setOpen = (open) => {
            shell.classList.toggle("nav-open", open);
            toggle.setAttribute("aria-expanded", String(open));
            if (scrim) scrim.hidden = !open;
        };
        toggle.addEventListener("click", () => setOpen(!shell.classList.contains("nav-open")));
        if (scrim) scrim.addEventListener("click", () => setOpen(false));
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") setOpen(false);
        });
    }

    /* ------------------------------------------------- Confirmar acciones graves */
    function confirmDangerous() {
        $$("form[data-confirm]").forEach((form) => {
            form.addEventListener("submit", (e) => {
                if (!window.confirm(form.dataset.confirm)) e.preventDefault();
            });
        });
    }

    /* -------------------------------------------------- Previsualizacion de imagen */
    function imagePreview() {
        $$("input[type=file][data-preview]").forEach((input) => {
            const target = $(input.dataset.preview);
            if (!target) return;
            input.addEventListener("change", () => {
                const file = input.files && input.files[0];
                if (!file || !file.type.startsWith("image/")) return;
                const url = URL.createObjectURL(file);
                target.src = url;
                target.classList.remove("is-hidden");
                target.onload = () => URL.revokeObjectURL(url);
            });
        });
    }

    /* --------------------------------------------------- Slug automatico (titulo) */
    function slugifyField() {
        $$("[data-slug-source], [data-slug-source-to]").forEach((target) => {
            const selector = target.dataset.slugSource || `[name="${target.dataset.slugSourceTo}"]`;
            const source = document.querySelector(selector);
            if (!source) return;
            const sync = () => {
                if (target.value.trim()) return;
                target.value = source.value
                    .toLowerCase()
                    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
                    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
            };
            source.addEventListener("input", sync);
            target.addEventListener("input", () => { target.dataset.touched = "1"; });
        });
    }

    /* -------------------------------------------------------- Guardado de ajustes */
    function settingsForm() {
        const form = $("[data-settings-form]");
        if (!form) return;
        const hidden = $("[data-settings-json]", form);
        const collect = () => {
            const data = {};
            $$("[data-setting]", form).forEach((input) => {
                const key = input.dataset.setting;
                data[key] = input.type === "checkbox" ? input.checked : input.value;
            });
            if (hidden) hidden.value = JSON.stringify(data);
            return data;
        };

        form.addEventListener("input", collect);
        form.addEventListener("change", collect);
        form.addEventListener("submit", collect);
        collect();
    }

    /* ------------------------------------------------- Filtrado instantaneo tabla */
    function quickFilter() {
        $$("[data-quick-filter]").forEach((input) => {
            const table = $(input.dataset.quickFilter);
            if (!table) return;
            input.addEventListener("input", () => {
                const q = input.value.trim().toLowerCase();
                let visible = 0;
                $$("tbody tr", table).forEach((tr) => {
                    const match = !q || tr.textContent.toLowerCase().indexOf(q) !== -1;
                    tr.hidden = !match;
                    if (match) visible += 1;
                });
                const counter = $("[data-filter-count]");
                if (counter) counter.textContent = visible;
            });
        });
    }

    /* ------------------------------------------------------------- Copiar texto */
    function copy() {
        document.addEventListener("click", async (e) => {
            const btn = e.target.closest("[data-copy]");
            if (!btn) return;
            e.preventDefault();
            const original = btn.textContent;
            try {
                await navigator.clipboard.writeText(btn.dataset.copy);
            } catch (_) {
                /* clipboard bloqueado: no hacemos nada */
            }
            btn.textContent = "COPIADO";
            setTimeout(() => { btn.textContent = original; }, 1500);
        });
    }

    function init() {
        nav();
        confirmDangerous();
        imagePreview();
        slugifyField();
        settingsForm();
        quickFilter();
        copy();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();