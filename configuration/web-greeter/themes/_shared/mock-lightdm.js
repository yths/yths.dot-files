// Fake window.lightdm / window.greeter_config / window.theme_config for
// in-browser preview. Loaded only when the page is opened with ?preview=1.
// Destructive actions (start_session, shutdown, restart, suspend, hibernate)
// dispatch a `lightdm-mock:event` CustomEvent on window and log to console
// instead of doing anything real.

(function () {
    if (window.lightdm) return;

    function Signal(name) {
        const handlers = new Set();
        return {
            name,
            connect(fn) { if (typeof fn === "function") handlers.add(fn); },
            disconnect(fn) { handlers.delete(fn); },
            emit(...args) { for (const fn of handlers) { try { fn(...args); } catch (e) { console.error(e); } } },
        };
    }

    function emit_event(action, detail) {
        const ev = new CustomEvent("lightdm-mock:event", { detail: { action, ...detail } });
        window.dispatchEvent(ev);
        console.log(`[lightdm-mock] ${action}`, detail || "");
    }

    const lightdm = {
        hostname: "preview-host",

        users: [
            { username: "alice", display_name: "Alice",       image: "", logged_in: false, session: "qtile" },
            { username: "bob",   display_name: "Bob Example", image: "", logged_in: true,  session: "xinitrc" },
            { username: "carol", display_name: "Carol",       image: "", logged_in: false, session: "qtile" },
        ],

        sessions: [
            { key: "qtile",   name: "Qtile",   comment: "Tiling window manager" },
            { key: "xinitrc", name: "xinitrc", comment: "User .xinitrc" },
            { key: "gnome",   name: "GNOME",   comment: "Wayland session" },
        ],

        languages: [
            { code: "en_US.UTF-8", name: "English (US)", territory: "United States" },
            { code: "de_DE.UTF-8", name: "German",       territory: "Germany" },
        ],

        layouts: [
            { name: "us", short_description: "us", description: "English (US)" },
            { name: "de", short_description: "de", description: "German" },
        ],

        language: { code: "en_US.UTF-8", name: "English (US)", territory: "United States" },
        layout:   { name: "us", short_description: "us", description: "English (US)" },

        // nody-greeter does not expose default_user; the greeter is told who
        // to preselect via select_user_hint (set on lock/relaunch) or by
        // marking a user as logged_in. default_session is the system fallback.
        select_user_hint: "bob",
        default_session: "qtile",

        is_authenticated: false,
        in_authentication: false,

        can_shutdown:  true,
        can_restart:   true,
        can_suspend:   true,
        can_hibernate: true,

        lock_hint: false,
        has_guest_account_hint: false,
        hide_users_hint: false,
        num_users: 3,
        autologin_user: "",
        autologin_timeout: 0,

        battery_data: { level: 80, status: "Discharging", ac_status: 0, time: "02:15", capacity: 92 },
        brightness: 70,

        show_prompt:               Signal("show_prompt"),
        show_message:              Signal("show_message"),
        authentication_complete:   Signal("authentication_complete"),
        autologin_timer_expired:   Signal("autologin_timer_expired"),
        idle:                      Signal("idle"),
        reset:                     Signal("reset"),
        brightness_update:         Signal("brightness_update"),
        battery_update:            Signal("battery_update"),
    };

    let current_user = null;

    lightdm.authenticate = function (username) {
        current_user = username || lightdm.select_user_hint || (lightdm.users[0] && lightdm.users[0].username);
        lightdm.in_authentication = true;
        lightdm.is_authenticated = false;
        emit_event("authenticate", { username: current_user });
        setTimeout(() => lightdm.show_prompt.emit("Password:", 1), 60);
    };

    lightdm.authenticate_as_guest = function () {
        lightdm.in_authentication = true;
        emit_event("authenticate_as_guest");
        setTimeout(() => lightdm.show_prompt.emit("Password:", 1), 60);
    };

    lightdm.cancel_authentication = function () {
        lightdm.in_authentication = false;
        lightdm.is_authenticated = false;
        emit_event("cancel_authentication");
    };

    lightdm.respond = function (response) {
        emit_event("respond", { length: (response || "").length });
        // panel can flip window.__force_fail_auth = true to test failure
        const succeed = !window.__force_fail_auth;
        lightdm.is_authenticated = succeed;
        lightdm.in_authentication = false;
        setTimeout(() => lightdm.authentication_complete.emit(), 80);
    };

    lightdm.start_session = function (session) {
        emit_event("start_session", { session: session || lightdm.default_session });
    };

    lightdm.shutdown  = function () { emit_event("shutdown");  };
    lightdm.restart   = function () { emit_event("restart");   };
    lightdm.suspend   = function () { emit_event("suspend");   };
    lightdm.hibernate = function () { emit_event("hibernate"); };

    lightdm.set_language = function (code) {
        const lang = lightdm.languages.find(l => l.code === code) || lightdm.language;
        lightdm.language = lang;
        emit_event("set_language", { code });
    };

    lightdm.set_layout = function (layout) {
        const choice = typeof layout === "string"
            ? (lightdm.layouts.find(l => l.name === layout) || lightdm.layout)
            : layout;
        lightdm.layout = choice;
        emit_event("set_layout", { layout: choice && choice.name });
    };

    lightdm.brightness_set = function (value) {
        lightdm.brightness = Math.max(0, Math.min(100, Number(value) || 0));
        lightdm.brightness_update.emit(lightdm.brightness);
        emit_event("brightness_set", { value: lightdm.brightness });
    };
    lightdm.brightness_increase = function () { lightdm.brightness_set(lightdm.brightness + 10); };
    lightdm.brightness_decrease = function () { lightdm.brightness_set(lightdm.brightness - 10); };

    lightdm.set_battery = function (delta) {
        if (!lightdm.battery_data) return;
        lightdm.battery_data = { ...lightdm.battery_data, level: Math.max(0, Math.min(100, lightdm.battery_data.level + delta)) };
        lightdm.battery_update.emit(lightdm.battery_data);
    };

    window.lightdm = lightdm;

    window.greeter_config = {
        branding:  { logo: "", background_images_dir: "", user_image: "" },
        greeter:   { debug_mode: true, secure_mode: false, time_language: "", screensaver_timeout: 300, theme: "" },
        layouts:   lightdm.layouts,
        features:  { battery: true, backlight: true },
    };

    window.theme_config = {};

    // Fire GreeterReady after the page bootstraps so logic.js can wire up.
    function fire_ready() {
        try { window.dispatchEvent(new Event("GreeterReady")); } catch (_) { /* ignore */ }
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fire_ready);
    } else {
        setTimeout(fire_ready, 0);
    }
})();
