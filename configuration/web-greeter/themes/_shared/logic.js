// Shared greeter logic. Loaded by every theme. Element lookups are
// guarded so the same file works whether a theme renders the minimal
// prompt or the full UI.

(function () {
    const state = {
        selected_user: null,
        selected_session: null,
        config: { symbols: {}, strings: {}, layout: {} },
    };

    function $(id) { return document.getElementById(id); }

    function get_query(name) {
        return new URLSearchParams(window.location.search).get(name);
    }

    function strings() { return state.config.strings || {}; }
    function symbols() { return state.config.symbols || {}; }

    async function load_theme_config() {
        try {
            const r = await fetch("theme.json", { cache: "no-store" });
            if (!r.ok) return null;
            return await r.json();
        } catch (_) { return null; }
    }

    function apply_theme_config(tj) {
        if (!tj) return;
        state.config = { symbols: tj.symbols || {}, strings: tj.strings || {}, layout: tj.layout || {} };

        // layout -> body data attributes
        const body = document.body;
        if (tj.layout) {
            if (tj.layout.status_bar)  body.dataset.statusBar  = tj.layout.status_bar;
            if (tj.layout.input_bar)   body.dataset.inputBar   = tj.layout.input_bar;
            if (tj.layout.message_bar) body.dataset.messageBar = tj.layout.message_bar;
        }

        // symbols -> CSS custom properties
        if (tj.symbols) {
            for (const [name, glyph] of Object.entries(tj.symbols)) {
                document.documentElement.style.setProperty(`--symbol-${name}`, JSON.stringify(glyph));
            }
        }

        // strings -> data-string / data-placeholder / data-title elements
        for (const [key, value] of Object.entries(tj.strings || {})) {
            for (const el of document.querySelectorAll(`[data-string="${key}"]`)) {
                el.textContent = value;
            }
            for (const el of document.querySelectorAll(`[data-placeholder="${key}"]`)) {
                el.placeholder = value;
            }
            for (const el of document.querySelectorAll(`[data-title="${key}"]`)) {
                el.title = value;
            }
        }

        // symbol glyphs that need to appear as element text (not via ::before)
        for (const [key, glyph] of Object.entries(tj.symbols || {})) {
            for (const el of document.querySelectorAll(`[data-symbol="${key}"]`)) {
                el.textContent = glyph;
            }
        }
    }

    function pad(n, len) {
        return String(n).padStart(len || 2, "0");
    }

    function show_time() {
        const time = $("time") || $("clock");
        if (!time) return;
        const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        const dt = new Date();
        time.textContent = `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())} ${days[dt.getDay()]} ${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
    }

    function show_message(text, type) {
        const message = $("message");
        const bar = $("message_bar");
        if (!message || !bar) return;
        if (!text || text.length === 0) {
            message.innerHTML = "&nbsp;";
            bar.style.visibility = "hidden";
            return;
        }
        const cls = (type === "error" || type === 1) ? "error_message" : "info_message";
        message.innerHTML = `<span class="${cls}">${text}</span>`;
        bar.style.visibility = "visible";
        clearTimeout(window.__msg_timeout);
        window.__msg_timeout = setTimeout(hide_message, 5000);
    }

    function hide_message() {
        const bar = $("message_bar");
        if (bar) bar.style.visibility = "hidden";
    }

    function show_prompt(text, type) {
        const input = $("user_input");
        if (!input) return;
        input.placeholder = text || "";
        input.value = "";
        input.type = (type === 1 || type === "password") ? "password" : "text";
        input.focus();
    }

    function handle_input() {
        const input = $("user_input");
        if (!input) return;
        window.lightdm.respond(input.value);
    }

    function authenticate() {
        if (window.lightdm.is_authenticated) {
            const session = state.selected_session || window.lightdm.default_session || "xinitrc";
            window.lightdm.start_session(session);
        } else {
            show_message(strings().auth_failed || "authentication failed", "error");
            window.lightdm.authenticate(state.selected_user);
        }
    }

    // The web-greeter / nody-greeter API does not expose a "default user".
    // Resolve the user to preselect from the signals it does provide, falling
    // back to a value we persist ourselves on every click.
    function resolve_initial_user() {
        const users = window.lightdm.users || [];
        if (users.length === 0) return null;
        const hint = window.lightdm.select_user_hint;
        if (hint && users.some(u => u.username === hint)) return hint;
        const active = users.find(u => u.logged_in);
        if (active) return active.username;
        try {
            const stored = localStorage.getItem("last_user");
            if (stored && users.some(u => u.username === stored)) return stored;
        } catch (_) { /* localStorage may be unavailable */ }
        return users[0].username;
    }

    function render_users() {
        const list = $("user_list");
        if (!list || !window.lightdm.users) return;
        list.innerHTML = "";
        const initial_user = resolve_initial_user();
        for (const user of window.lightdm.users) {
            const item = document.createElement("li");
            item.className = "user_item";
            item.dataset.username = user.username;
            if (user.image) {
                const img = document.createElement("img");
                img.alt = "";
                img.addEventListener("error", () => img.remove());
                img.src = user.image;
                item.appendChild(img);
            }
            const label = document.createElement("span");
            label.textContent = user.display_name || user.username;
            item.appendChild(label);
            if (user.username === initial_user) item.classList.add("selected");
            item.addEventListener("click", () => select_user(user.username));
            list.appendChild(item);
        }
        if (initial_user) state.selected_user = initial_user;
    }

    function select_user(username) {
        state.selected_user = username;
        try { localStorage.setItem("last_user", username); } catch (_) { /* ignore */ }
        const list = $("user_list");
        if (list) {
            for (const item of list.children) {
                item.classList.toggle("selected", item.dataset.username === username);
            }
        }
        if (window.lightdm.in_authentication) window.lightdm.cancel_authentication();
        window.lightdm.authenticate(username);
    }

    // lightdm.default_session is the system-wide fallback; the per-user last
    // session lives on the user record (XSession in AccountsService).
    function resolve_initial_session() {
        const sessions = window.lightdm.sessions || [];
        const user_entry = (window.lightdm.users || []).find(u => u.username === state.selected_user);
        if (user_entry && user_entry.session && sessions.some(s => s.key === user_entry.session)) {
            return user_entry.session;
        }
        try {
            const stored = localStorage.getItem("last_session");
            if (stored && sessions.some(s => s.key === stored)) return stored;
        } catch (_) { /* ignore */ }
        return window.lightdm.default_session;
    }

    function render_sessions() {
        const picker = $("session_picker");
        if (!picker || !window.lightdm.sessions) return;
        const default_session = resolve_initial_session();
        if (picker.tagName === "SELECT") {
            picker.innerHTML = "";
            for (const session of window.lightdm.sessions) {
                const opt = document.createElement("option");
                opt.value = session.key;
                opt.textContent = session.name || session.key;
                if (session.key === default_session) opt.selected = true;
                picker.appendChild(opt);
            }
            state.selected_session = picker.value || default_session;
            picker.addEventListener("change", () => {
                state.selected_session = picker.value;
                try { localStorage.setItem("last_session", picker.value); } catch (_) { /* ignore */ }
            });
            return;
        }
        const current = picker.querySelector(".session_current");
        const options = picker.querySelector(".session_options");
        if (!current || !options) return;
        options.innerHTML = "";
        let chosen = null;
        for (const session of window.lightdm.sessions) {
            const li = document.createElement("li");
            li.dataset.key = session.key;
            li.textContent = session.name || session.key;
            if (session.key === default_session) {
                li.classList.add("active");
                chosen = session;
            }
            li.addEventListener("click", (e) => {
                e.stopPropagation();
                state.selected_session = session.key;
                try { localStorage.setItem("last_session", session.key); } catch (_) { /* ignore */ }
                current.textContent = session.name || session.key;
                for (const sib of options.children) sib.classList.toggle("active", sib === li);
                picker.classList.remove("open");
            });
            options.appendChild(li);
        }
        if (!chosen && window.lightdm.sessions.length > 0) chosen = window.lightdm.sessions[0];
        if (chosen) {
            current.textContent = chosen.name || chosen.key;
            state.selected_session = chosen.key;
        }
        picker.addEventListener("click", (e) => {
            if (e.target.closest(".session_options")) return;
            picker.classList.toggle("open");
        });
        document.addEventListener("click", (e) => {
            if (!picker.contains(e.target)) picker.classList.remove("open");
        });
        picker.addEventListener("keydown", (e) => {
            if (e.key === "Escape") picker.classList.remove("open");
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                picker.classList.toggle("open");
            }
        });
    }

    function render_power_actions() {
        const actions = [
            ["btn_shutdown", "can_shutdown", "shutdown"],
            ["btn_restart", "can_restart", "restart"],
            ["btn_suspend", "can_suspend", "suspend"],
            ["btn_hibernate", "can_hibernate", "hibernate"],
        ];
        for (const [id, cap, fn] of actions) {
            const btn = $(id);
            if (!btn) continue;
            if (!window.lightdm[cap]) {
                btn.disabled = true;
                btn.classList.add("disabled");
            }
            btn.addEventListener("click", () => window.lightdm[fn]());
        }
    }

    function render_layout() {
        const el = $("kb_layout");
        if (!el) return;
        const layout = window.lightdm.layout;
        el.textContent = layout ? (layout.short_description || layout.name || layout) : "";
        const picker = $("kb_layout_picker");
        if (picker && window.lightdm.layouts) {
            picker.innerHTML = "";
            for (const l of window.lightdm.layouts) {
                const opt = document.createElement("option");
                opt.value = l.name || l;
                opt.textContent = l.short_description || l.name || l;
                if (window.lightdm.layout && (l.name === window.lightdm.layout.name || l === window.lightdm.layout)) opt.selected = true;
                picker.appendChild(opt);
            }
            picker.addEventListener("change", () => {
                const choice = window.lightdm.layouts.find(l => (l.name || l) === picker.value);
                if (window.lightdm.set_layout) window.lightdm.set_layout(choice);
            });
        }
    }

    function render_battery() {
        const el = $("battery");
        if (!el) return;
        update_battery();
        if (window.lightdm.battery_update && window.lightdm.battery_update.connect) {
            window.lightdm.battery_update.connect(update_battery);
        }
    }

    function update_battery() {
        const el = $("battery");
        if (!el) return;
        const data = window.lightdm.battery_data;
        if (!data) { el.textContent = ""; el.style.display = "none"; return; }
        el.style.display = "";
        const level = Math.round(data.level);
        const charging = data.status === "Charging" || data.ac_status;
        const charge_glyph = symbols().battery_charging    || "⚡";
        const drain_glyph  = symbols().battery_discharging || "▮";
        el.textContent = `${charging ? charge_glyph : drain_glyph} ${level}%`;
        el.dataset.level = level;
        el.dataset.charging = String(!!charging);
    }

    function render_brightness() {
        update_brightness();
        if (window.lightdm.brightness_update && window.lightdm.brightness_update.connect) {
            window.lightdm.brightness_update.connect(update_brightness);
        }
        const slider = $("brightness_slider");
        if (slider) {
            slider.addEventListener("input", () => {
                if (window.lightdm.brightness_set) window.lightdm.brightness_set(Number(slider.value));
            });
        }
    }

    function update_brightness() {
        const el = $("brightness");
        const slider = $("brightness_slider");
        const control = document.getElementById("brightness_control");
        const value = window.lightdm.brightness;
        const available = typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;
        if (!available) {
            if (el) { el.textContent = ""; el.style.display = "none"; }
            if (control) control.style.display = "none";
            else if (slider) slider.style.display = "none";
            return;
        }
        if (el) {
            el.style.display = "";
            const glyph = symbols().brightness || "☀";
            el.textContent = `${glyph} ${value}%`;
        }
        if (control) control.style.display = "";
        if (slider) { slider.style.display = ""; slider.value = value; }
    }

    function render_hostname() {
        const el = $("hostname");
        if (el) el.textContent = window.lightdm.hostname || "";
    }

    async function inject_preview_mocks() {
        if (get_query("preview") !== "1") return;
        if (window.lightdm) return;
        await new Promise((resolve, reject) => {
            const s = document.createElement("script");
            s.src = "/_shared/mock-lightdm.js";
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    async function run() {
        if (typeof window.show_message !== "function") window.show_message = show_message;
        if (typeof window.show_prompt !== "function") window.show_prompt = show_prompt;
        if (typeof window.handle_input !== "function") window.handle_input = handle_input;
        if (typeof window.authenticate !== "function") window.authenticate = authenticate;
        if (typeof window.show_time !== "function") window.show_time = show_time;
        if (typeof window.hide_message !== "function") window.hide_message = hide_message;

        show_time();
        setInterval(show_time, 1000);

        if (!window.lightdm) return;

        render_hostname();
        render_users();
        render_sessions();
        render_power_actions();
        render_layout();
        render_battery();
        render_brightness();

        if (window.lightdm.show_message && window.lightdm.show_message.connect) {
            window.lightdm.show_message.connect(show_message);
        }
        if (window.lightdm.show_prompt && window.lightdm.show_prompt.connect) {
            window.lightdm.show_prompt.connect(show_prompt);
        }
        if (window.lightdm.authentication_complete && window.lightdm.authentication_complete.connect) {
            window.lightdm.authentication_complete.connect(authenticate);
        }

        if (state.selected_user) window.lightdm.authenticate(state.selected_user);
    }

    async function bootstrap() {
        await inject_preview_mocks();
        const tj = await load_theme_config();
        apply_theme_config(tj);
        window.addEventListener("GreeterReady", run);
        if (window.lightdm) {
            run();
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bootstrap);
    } else {
        bootstrap();
    }
})();
