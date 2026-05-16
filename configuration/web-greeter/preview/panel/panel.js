// Preview panel: theme switcher, event triggers, live-color overrides,
// theme.json persistence, WebSocket hot reload.

(function () {
    const $ = (id) => document.getElementById(id);

    const stage = $("stage");
    const ws_status = $("ws_status");

    const state = {
        themes: [],
        active_theme: null,
        theme_json: null,
        global_config: null,
        color_overrides: {},
    };

    const CSS_VARS = [
        ["background",         "--background"],
        ["foreground",         "--foreground"],
        ["foreground_variant", "--foreground-variant"],
        ["neutral",            "--neutral"],
        ["highlight",          "--highlight"],
        ["failure",            "--failure"],
        ["success",            "--success"],
        ["notification",       "--notification"],
        ["warning",            "--warning"],
    ];

    const LAYOUT_ROLES = {
        nuunamnir: {
            status_bar:  ["top-left", "top-right", "bottom-left", "bottom-right"],
            input_bar:   ["top", "center", "bottom"],
            message_bar: ["top", "center", "bottom"],
        },
        // standard theme keeps its zones fixed; expose nothing for now
        standard: {},
    };

    // ---- helpers ----

    async function json_get(url) {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) throw new Error(`${url} -> ${r.status}`);
        return await r.json();
    }

    async function json_post(url, payload) {
        const r = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!r.ok) throw new Error(`${url} -> ${r.status}`);
        return await r.json();
    }

    function toast(text, kind) {
        const ul = $("toasts");
        const li = document.createElement("li");
        const ts = new Date().toLocaleTimeString();
        li.textContent = `[${ts}] ${text}`;
        if (kind === "warn") li.classList.add("warn");
        ul.prepend(li);
        while (ul.children.length > 25) ul.removeChild(ul.lastChild);
    }

    function iframe_lightdm() {
        try { return stage.contentWindow && stage.contentWindow.lightdm; }
        catch (_) { return null; }
    }

    function iframe_root() {
        try { return stage.contentDocument && stage.contentDocument.documentElement; }
        catch (_) { return null; }
    }

    function wait_for_iframe() {
        return new Promise((resolve) => {
            const check = () => {
                if (iframe_lightdm()) return resolve();
                setTimeout(check, 50);
            };
            check();
        });
    }

    function load_overrides_storage(theme) {
        try { return JSON.parse(localStorage.getItem(`override:${theme}`) || "{}"); }
        catch (_) { return {}; }
    }
    function save_overrides_storage(theme, obj) {
        localStorage.setItem(`override:${theme}`, JSON.stringify(obj));
    }

    // ---- theme switching ----

    function render_theme_picker() {
        const wrap = $("theme_picker");
        wrap.innerHTML = "";
        for (const t of state.themes) {
            const b = document.createElement("button");
            b.className = "theme_button";
            b.textContent = t;
            if (t === state.active_theme) b.classList.add("active");
            b.addEventListener("click", () => set_active_theme(t));
            wrap.appendChild(b);
        }
    }

    async function set_active_theme(theme) {
        state.active_theme = theme;
        localStorage.setItem("active_theme", theme);
        render_theme_picker();
        stage.src = `/${theme}/?preview=1`;
        await refresh_theme_json();
        await wait_for_iframe();
        apply_color_overrides();
        listen_to_mock_events();
    }

    // ---- theme.json ----

    async function refresh_theme_json() {
        state.theme_json = await json_get(`/__api/theme.json?theme=${state.active_theme}`);
        render_wallpaper_picker();
        render_layout_controls();
        render_font_inputs();
        render_kv("symbols");
        render_kv("strings");
    }

    async function save_theme_json() {
        await json_post(`/__api/theme.json?theme=${state.active_theme}`, state.theme_json);
        toast(`saved theme.json for ${state.active_theme}`);
    }

    // ---- color overrides (preview-only) ----

    function render_color_overrides() {
        const wrap = $("color_overrides");
        wrap.innerHTML = "";
        const overrides = state.color_overrides;
        for (const [key, cssVar] of CSS_VARS) {
            const label = document.createElement("label");
            label.textContent = key;
            const input = document.createElement("input");
            input.type = "color";
            input.dataset.var = cssVar;
            input.dataset.key = key;
            input.value = overrides[key] || palette_color(key) || "#000000";
            input.addEventListener("input", () => {
                overrides[key] = input.value;
                save_overrides_storage(state.active_theme, overrides);
                apply_color_overrides();
            });
            wrap.appendChild(label);
            wrap.appendChild(input);
        }
    }

    function palette_color(key) {
        const cfg = state.global_config;
        if (!cfg || !cfg.palette) return null;
        const theme_state = cfg.state && cfg.state.theme;
        const palette = cfg.palette[theme_state] || cfg.palette.dark || cfg.palette.light;
        if (!palette) return null;
        return palette[key] || null;
    }

    function apply_color_overrides() {
        const root = iframe_root();
        if (!root) return;
        for (const [key, cssVar] of CSS_VARS) {
            const v = state.color_overrides[key];
            if (v) root.style.setProperty(cssVar, v);
            else root.style.removeProperty(cssVar);
        }
    }

    // ---- wallpaper ----

    function render_wallpaper_picker() {
        const select = $("wallpaper_key");
        select.innerHTML = "";
        const cfg_keys = state.global_config && state.global_config.wallpapers
            ? Object.keys(state.global_config.wallpapers)
            : ["dark", "light", "dark-highlight", "light-highlight"];
        for (const k of cfg_keys) {
            const opt = document.createElement("option");
            opt.value = k;
            opt.textContent = k;
            if (k === state.theme_json.wallpaper_key) opt.selected = true;
            select.appendChild(opt);
        }
        select.onchange = async () => {
            state.theme_json.wallpaper_key = select.value;
            await save_theme_json();
        };
    }

    // ---- layout ----

    function render_layout_controls() {
        const wrap = $("layout_controls");
        wrap.innerHTML = "";
        const roles = LAYOUT_ROLES[state.active_theme] || {};
        const current = state.theme_json.layout || {};
        if (Object.keys(roles).length === 0) {
            const span = document.createElement("span");
            span.textContent = "no layout knobs for this theme";
            wrap.appendChild(span);
            return;
        }
        for (const [role, values] of Object.entries(roles)) {
            const label = document.createElement("span");
            label.textContent = role;
            const select = document.createElement("select");
            for (const v of values) {
                const opt = document.createElement("option");
                opt.value = v;
                opt.textContent = v;
                if (current[role] === v) opt.selected = true;
                select.appendChild(opt);
            }
            select.addEventListener("change", async () => {
                state.theme_json.layout = state.theme_json.layout || {};
                state.theme_json.layout[role] = select.value;
                await save_theme_json();
            });
            wrap.appendChild(label);
            wrap.appendChild(select);
        }
    }

    // ---- symbols / strings (key-value editors) ----

    function render_kv(section) {
        const wrap = $(`${section}_controls`);
        const map = state.theme_json[section] || {};
        state.theme_json[section] = map;
        wrap.innerHTML = "";
        for (const key of Object.keys(map)) {
            wrap.appendChild(kv_row(section, key));
        }
        $(`${section}_add`).onclick = () => {
            const name = prompt(`new ${section.slice(0, -1)} key (lowercase, snake_case)`);
            if (!name) return;
            if (!/^[a-z][a-z0-9_]*$/.test(name)) { toast(`invalid ${section} key`, "warn"); return; }
            if (name in map) { toast("already exists", "warn"); return; }
            map[name] = "";
            render_kv(section);
            save_theme_json();
        };
    }

    function kv_row(section, key) {
        const wrap = document.createElement("div");
        wrap.style.display = "contents";
        const key_input = document.createElement("input");
        key_input.className = "key";
        key_input.value = key;
        key_input.readOnly = true;
        key_input.title = "drag-rename is not supported; delete and re-add to change key";
        const value_input = document.createElement("input");
        value_input.value = state.theme_json[section][key] || "";
        value_input.spellcheck = false;
        value_input.addEventListener("input", () => {
            state.theme_json[section][key] = value_input.value;
        });
        value_input.addEventListener("change", () => { save_theme_json(); });
        const del = document.createElement("button");
        del.className = "del";
        del.textContent = "×";
        del.title = "remove";
        del.addEventListener("click", () => {
            delete state.theme_json[section][key];
            render_kv(section);
            save_theme_json();
        });
        wrap.appendChild(key_input);
        wrap.appendChild(value_input);
        wrap.appendChild(del);
        return wrap;
    }

    // ---- clone ----

    async function clone_theme() {
        const name_input = $("clone_name");
        const msg = $("clone_msg");
        const name = name_input.value.trim();
        msg.className = "";
        if (!name) { msg.textContent = "name required"; msg.classList.add("error"); return; }
        try {
            const r = await json_post("/__api/themes/clone", { source: state.active_theme, name });
            if (!r.ok) throw new Error(r.error || "clone failed");
            msg.textContent = `cloned -> ${r.name}`;
            msg.classList.add("ok");
            name_input.value = "";
            const themes = await json_get("/__api/themes");
            state.themes = themes.themes;
            render_theme_picker();
            await set_active_theme(r.name);
        } catch (exc) {
            msg.textContent = String(exc.message || exc);
            msg.classList.add("error");
        }
    }

    // ---- font ----

    function render_font_inputs() {
        const overrides = state.theme_json.font_overrides || {};
        $("font_family").value = overrides.family || "";
        $("font_size").value = overrides.size || "";
        $("save_font").onclick = async () => {
            const family = $("font_family").value.trim();
            const size = parseInt($("font_size").value, 10);
            const fo = {};
            if (family) fo.family = family;
            if (Number.isFinite(size) && size > 0) fo.size = size;
            state.theme_json.font_overrides = fo;
            await save_theme_json();
        };
    }

    // ---- events to iframe ----

    function emit_to(signal, ...args) {
        const lightdm = iframe_lightdm();
        if (!lightdm || !lightdm[signal] || !lightdm[signal].emit) {
            toast(`signal '${signal}' unavailable`, "warn");
            return;
        }
        lightdm[signal].emit(...args);
    }

    function trigger(action) {
        const lightdm = iframe_lightdm();
        if (!lightdm) { toast("iframe not ready", "warn"); return; }
        switch (action) {
            case "show_prompt:info":     return emit_to("show_prompt", "Username:", 0);
            case "show_prompt:password": return emit_to("show_prompt", "Password:", 1);
            case "show_message:info":    return emit_to("show_message", "info: hello", 0);
            case "show_message:error":   return emit_to("show_message", "auth failed", 1);
            case "auth:success":
                lightdm.is_authenticated = true;
                return emit_to("authentication_complete");
            case "auth:fail":
                lightdm.is_authenticated = false;
                return emit_to("authentication_complete");
            case "idle":                 return emit_to("idle");
            case "reset":                return emit_to("reset");
            case "battery:+10":          return lightdm.set_battery && lightdm.set_battery(+10);
            case "battery:-10":          return lightdm.set_battery && lightdm.set_battery(-10);
            case "brightness:+20":       return lightdm.brightness_set && lightdm.brightness_set((lightdm.brightness || 0) + 20);
            case "brightness:-20":       return lightdm.brightness_set && lightdm.brightness_set((lightdm.brightness || 0) - 20);
        }
    }

    function listen_to_mock_events() {
        try {
            stage.contentWindow.removeEventListener("lightdm-mock:event", on_mock_event);
        } catch (_) { /* iframe maybe not ready yet */ }
        try {
            stage.contentWindow.addEventListener("lightdm-mock:event", on_mock_event);
        } catch (_) { /* will retry on next load */ }
    }

    function on_mock_event(ev) {
        const { action, ...rest } = ev.detail || {};
        const note = Object.keys(rest).length
            ? `${action} ${JSON.stringify(rest)}`
            : action;
        const kind = ["shutdown", "restart"].includes(action) ? "warn" : null;
        toast(note, kind);
    }

    // ---- wiring ----

    function bind_events() {
        for (const btn of document.querySelectorAll("button[data-event]")) {
            btn.addEventListener("click", () => trigger(btn.dataset.event));
        }
        $("force_fail_auth").addEventListener("change", (e) => {
            try { stage.contentWindow.__force_fail_auth = e.target.checked; }
            catch (_) { /* iframe not ready */ }
        });
        $("clone_theme").addEventListener("click", clone_theme);
        $("copy_diff").addEventListener("click", async () => {
            const overrides = state.color_overrides;
            const theme_state = (state.global_config && state.global_config.state && state.global_config.state.theme) || "dark";
            const fragment = { palette: { [theme_state]: { ...overrides } } };
            const text = JSON.stringify(fragment, null, 4);
            try { await navigator.clipboard.writeText(text); toast("copied color diff"); }
            catch (_) { toast("clipboard blocked; check console"); console.log(text); }
        });
        stage.addEventListener("load", async () => {
            await wait_for_iframe();
            apply_color_overrides();
            listen_to_mock_events();
        });
    }

    function connect_ws() {
        const ws_port = Number(location.port || 8765) + 1;
        let ws;
        const open = () => {
            ws = new WebSocket(`ws://${location.hostname}:${ws_port}/`);
            ws.onopen = () => { ws_status.textContent = "connected"; ws_status.classList.add("connected"); };
            ws.onclose = () => {
                ws_status.textContent = "disconnected";
                ws_status.classList.remove("connected");
                setTimeout(open, 1000);
            };
            ws.onerror = () => { try { ws.close(); } catch (_) {} };
            ws.onmessage = (ev) => {
                let msg;
                try { msg = JSON.parse(ev.data); } catch (_) { return; }
                if (msg.event === "reload") {
                    toast("reload (" + (msg.changed || []).map(p => p.split("/").pop()).join(", ") + ")");
                    stage.contentWindow.location.reload();
                    refresh_theme_json().catch(() => {});
                }
            };
        };
        open();
    }

    async function init() {
        state.color_overrides = {};
        bind_events();
        connect_ws();

        try { state.global_config = await json_get("/__api/config.json"); }
        catch (_) { state.global_config = null; toast("global config.json not readable", "warn"); }

        const { themes } = await json_get("/__api/themes");
        state.themes = themes;
        const stored = localStorage.getItem("active_theme");
        state.active_theme = themes.includes(stored) ? stored : themes[0];

        state.color_overrides = load_overrides_storage(state.active_theme);
        render_color_overrides();
        render_theme_picker();
        await set_active_theme(state.active_theme);
    }

    document.addEventListener("DOMContentLoaded", init);
})();
