window.handle_input = function() {
    let user_input = document.getElementById("user_input");
    window.lightdm.respond(user_input.value);
};

window.authenticate = function() {
    if(window.lightdm.is_authenticated) {
        window.lightdm.start_session("xinitrc");
    } else {
        show_message("authentication failed", "error");
        window.lightdm.authenticate(null);
    }
};

window.show_prompt = function(text, type) {
    let user_input = document.getElementById("user_input");
    user_input.placeholder = "";
    user_input.value = "";
    user_input.type = type == 0 ? "text" : "password";
    user_input.focus();
}

window.show_message = function(text, type) {
    let message = document.getElementById("message");
    let message_bar = document.getElementById("message_bar");
    if (text.length === 0) {
        message.innerHTML = `&nbsp;`;
        message_bar.style.visibility = "hidden";
        return;
    } else {
        if(type == "error") {
            message.innerHTML = ` <span class="error_message">${text}</p>`;
            message_bar.style.visibility = "visible";
        } else {
            message.innerHTML = ` <span class="info_message">${text}</p>`;
            message_bar.style.visibility = "visible";
        }

        setTimeout(hidde_message, 5000);
    }
};

async function run() {
    console.log("Greeter is ready");
    show_time();
    window.lightdm.show_message.connect(show_message)
    window.lightdm.show_prompt.connect(show_prompt);
    window.lightdm.authentication_complete.connect(authenticate)
    window.lightdm.authenticate(null);
};

window.addEventListener("GreeterReady", run);

window.show_time = function() {
    let time = document.getElementById("time");
    let dt = new Date();
    let days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    let padL = (nr, len = 2, chr = `0`) => `${nr}`.padStart(2, chr);
    time.innerHTML = `${
    dt.getFullYear()}-${
    padL(dt.getMonth()+1)}-${
    padL(dt.getDate())} ${days[dt.getDay()]} ${
    padL(dt.getHours())}:${
    padL(dt.getMinutes())}:${
    padL(dt.getSeconds())}`
};

window.hidde_message = function() {
    let message_bar = document.getElementById("message_bar");
    message_bar.style.visibility = "hidden";
}

setInterval(show_time, 1000);