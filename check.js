
console.log("🟢 chat.html JS loaded v2");
const chatBox = document.getElementById("chatBox");
if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;

// ===== خلفية =====
function openBgModal() { const m = document.getElementById("bgModal"); if (m) m.classList.add("active"); }
function closeBgModal() { const m = document.getElementById("bgModal"); if (m) m.classList.remove("active"); }

// ===== قصة =====
function viewStory(url, username) {
    const win = window.open();
    win.document.write("<body style='margin:0;background:#000;display:flex;justify-content:center;align-items:center;height:100vh;'><img src='" + url + "' style='max-width:100%;max-height:100%;'><h2 style='position:absolute;top:20px;color:white;font-family:sans-serif;'>@" + username + "</h2>    
    

    <!-- Media Inputs (Clean) -->

    <!-- Media Inputs (Clean) -->
    
    

    <input type="file" id="imageInput" accept="image/*" style="display:none;" onchange="sendImage(this)">
    <input type="file" id="videoInput" accept="video/*" style="display:none;" onchange="sendVideo(this)">
</body>");
}

// ===== الرد على رسالة =====
function openReplyMenu(e, msgId, username, content) {
    e.preventDefault();
    const rid = document.getElementById("replyToId");
    const rt = document.getElementById("replyText");
    const ri = document.getElementById("replyIndicator");
    const mi = document.getElementById("messageInput");
    if (rid) rid.value = msgId;
    if (rt) rt.innerText = "@" + username + ": " + content;
    if (ri) ri.classList.add("active");
    if (mi) mi.focus();
}

function cancelReply() {
    const rid = document.getElementById("replyToId");
    const ri = document.getElementById("replyIndicator");
    if (rid) rid.value = "";
    if (ri) ri.classList.remove("active");
}

// ===== تسجيل الصوت =====
let mediaRecorder, audioChunks = [], isRecording = false;
const micBtn = document.getElementById("micBtn");
const messageInput = document.getElementById("messageInput");

async function toggleRecord() {
    if (!micBtn) return;
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            mediaRecorder.ondataavailable = ev => audioChunks.push(ev.data);
            mediaRecorder.onstop = async () => {
                const blob = new Blob(audioChunks, { type: "audio/webm" });
                const fd = new FormData();
                fd.append("audio", blob, "voice.webm");
                fd.append(window.CHAT_CONFIG.groupId ? "group_id" : "receiver_id", window.CHAT_CONFIG.groupId || window.CHAT_CONFIG.otherUserId || "");
                micBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
                try {
                    const res = await fetch("/api/chat/audio", { method: "POST", body: fd });
                    if (res.ok) window.location.reload();
                    else alert("فشل إرسال الصوت");
                } catch (e) { alert("خطأ"); }
            };
            mediaRecorder.start();
            isRecording = true;
            micBtn.classList.add("recording");
            micBtn.innerHTML = '<i class="fa-solid fa-stop"></i>';
        } catch (err) { alert("تعذر الوصول للميكروفون"); }
    } else {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(t => t.stop());
        isRecording = false;
        micBtn.classList.remove("recording");
        micBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    }
}

// ===== قائمة الرسالة =====
let currentMsgEl = null, currentMsgData = null, longPressTimer = null;
let __menuOpenedAt = 0;

function openMsgMenu(e, el) {
    e.preventDefault();
    e.stopPropagation();
    currentMsgEl = el;
    currentMsgData = {
        id: el.dataset.msgId,
        sender: el.dataset.sender,
        content: el.dataset.content,
        type: el.dataset.type,
        canEdit: el.dataset.canEdit === "true",
        canDelete: el.dataset.canDelete === "true"
    };
    const menu = document.getElementById("msgMenu");
    if (!menu) return;
    const editBtn = menu.querySelector(".only-edit");
    const delBtn = menu.querySelector(".only-delete");
    const pinBtn = menu.querySelector(".only-pin");
    if (editBtn) editBtn.style.display = currentMsgData.canEdit ? "flex" : "none";
    if (delBtn) delBtn.style.display = currentMsgData.canDelete ? "flex" : "none";
    if (pinBtn) pinBtn.style.display = (currentMsgData.type !== "system") ? "flex" : "none";
    const x = e.touches ? e.touches[0].clientX : e.clientX;
    const y = e.touches ? e.touches[0].clientY : e.clientY;
    menu.style.left = Math.min(x, window.innerWidth - 200) + "px";
    menu.style.top = Math.min(y, window.innerHeight - 320) + "px";
    menu.classList.add("active");
    __menuOpenedAt = Date.now();
}

document.addEventListener("touchstart", function(e) {
    const w = e.target.closest(".message-wrapper");
    if (!w) return;
    longPressTimer = setTimeout(() => openMsgMenu(e, w), 500);
}, { passive: true });

document.addEventListener("touchend", () => clearTimeout(longPressTimer));
document.addEventListener("touchmove", () => clearTimeout(longPressTimer));

document.addEventListener("click", function(e) {
    if (Date.now() - __menuOpenedAt < 400) return;
    const menu = document.getElementById("msgMenu");
    const picker = document.getElementById("reactionPicker");
    if (menu && menu.contains(e.target)) return;
    if (picker && picker.contains(e.target)) return;
    if (menu) menu.classList.remove("active");
    if (picker) picker.classList.remove("active");
});

function toast(msg) {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2200);
}

async function msgAction(action) {
    const menu = document.getElementById("msgMenu");
    if (menu) menu.classList.remove("active");
    if (!currentMsgData) return;

    if (action === "reply") {
        const rid = document.getElementById("replyToId");
        const rt = document.getElementById("replyText");
        const ri = document.getElementById("replyIndicator");
        const mi = document.getElementById("messageInput");
        if (rid) rid.value = currentMsgData.id;
        if (rt) rt.innerText = "@" + currentMsgData.sender + ": " + currentMsgData.content.substring(0, 50);
        if (ri) ri.classList.add("active");
        if (mi) mi.focus();
    } else if (action === "copy") {
        navigator.clipboard.writeText(currentMsgData.content).then(() => toast("✅ تم النسخ"));
    } else if (action === "react") {
        const picker = document.getElementById("reactionPicker");
        if (picker) {
            picker.style.left = "50%";
            picker.style.top = "50%";
            picker.style.transform = "translate(-50%, -50%)";
            picker.classList.add("active");
        }
    } else if (action === "delete") {
        if (confirm("حذف هذه الرسالة؟")) {
            fetch("/api/message/delete/" + currentMsgData.id, { method: "POST" })
                .then(r => r.json()).then(d => {
                    if (d.success) { currentMsgEl.remove(); toast("🗑️ تم الحذف"); }
                    else alert("فشل الحذف");
                });
        }
    } else if (action === "edit") {
        const n = prompt("تعديل الرسالة:", currentMsgData.content);
        if (n && n.trim() && n.trim() !== currentMsgData.content) {
            fetch("/api/message/edit/" + currentMsgData.id, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content: n.trim() })
            }).then(r => r.json()).then(d => {
                if (d.success) {
                    const body = currentMsgEl.querySelector(".message");
                    const meta = body.querySelector(".msg-meta");
                    body.innerHTML = "";
                    body.appendChild(document.createTextNode(d.content));
                    body.appendChild(meta);
                    toast("✏️ تم التعديل");
                } else alert("فشل التعديل");
            });
        }
    } else if (action === "forward") {
        openForward();
    } else if (action === "pin") {
        if (window.CHAT_CONFIG.groupId) {
            fetch("/group/" + window.CHAT_CONFIG.groupId + "/pin/" + currentMsgData.id, { method: "POST" })
                .then(() => location.reload());
        }
    }
}

async function sendReaction(emoji) {
    const picker = document.getElementById("reactionPicker");
    if (picker) picker.classList.remove("active");
    if (!currentMsgData) return;
    const res = await fetch("/api/message/react/" + currentMsgData.id, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reaction: emoji })
    });
    const data = await res.json();
    if (data.success) {
        const body = currentMsgEl.querySelector(".message");
        const meta = body.querySelector(".msg-meta");
        let re = meta.querySelector(".msg-reaction");
        if (data.reaction) {
            if (!re) { re = document.createElement("span"); re.className = "msg-reaction"; meta.appendChild(re); }
            re.textContent = data.reaction;
        } else if (re) { re.remove(); }
    }
}

function scrollToBottom() {
    const box = document.getElementById("chatBox");
    if (box) box.scrollTop = box.scrollHeight;
}

function scrollToMsg(id) {
    const el = document.querySelector('[data-msg-id="' + id + '"]');
    if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.style.transition = "background 0.5s";
        el.style.background = "rgba(255,204,0,0.3)";
        setTimeout(() => el.style.background = "", 1500);
    }
}

if (chatBox) {
    chatBox.addEventListener("scroll", () => {
        const sb = document.getElementById("scrollBtn");
        if (!sb) return;
        const near = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight < 100;
        sb.classList.toggle("visible", !near);
    });
}

// ===== التحويل =====
function openForward() {
    const fm = document.getElementById("forwardModal");
    if (!fm) return;
    fm.classList.add("active");
    const list = document.getElementById("forwardList");
    if (!list) return;
    list.innerHTML = "جاري التحميل...";
    fetch("/api/get_forward_targets").then(r => r.json()).then(t => {
        list.innerHTML = "";
        if (!t || t.length === 0) { list.innerHTML = "<p style='color:#888;'>لا يوجد مستلمون</p>"; return; }
        t.forEach(tg => {
            const b = document.createElement("button");
            b.style.cssText = "display:block;width:100%;padding:12px;margin-bottom:6px;background:#333;color:white;border:none;border-radius:8px;text-align:right;cursor:pointer;font-family:inherit;";
            b.innerHTML = '<i class="fa-solid fa-users"></i> ' + tg.name;
            b.onclick = () => doForward(tg.type, tg.id);
            list.appendChild(b);
        });
    });
}

function closeForward() {
    const fm = document.getElementById("forwardModal");
    if (fm) fm.classList.remove("active");
}

async function doForward(type, id) {
    const res = await fetch("/api/message/forward/" + currentMsgData.id, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_type: type, target_id: id })
    });
    const d = await res.json();
    if (d.success) { toast("➡️ تم التحويل"); closeForward(); }
    else alert("فشل: " + (d.error || ""));
}

// ===== صور وفيديو =====
function sendImage(input) {
    if (!input.files || !input.files[0]) return;
    const fd = new FormData();
    fd.append("image", input.files[0]);
    fd.append(window.CHAT_CONFIG.groupId ? "group_id" : "receiver_id", window.CHAT_CONFIG.groupId || window.CHAT_CONFIG.otherUserId || "");
    toast("📤 جاري الرفع...");
    fetch("/api/chat/image", { method: "POST", body: fd })
        .then(r => r.json()).then(d => {
            if (d.success) location.reload();
            else alert("فشل الرفع: " + (d.error || ""));
        });
    input.value = "";
}

function sendVideo(input) {
    if (!input.files || !input.files[0]) return;
    const fd = new FormData();
    fd.append("video", input.files[0]);
    fd.append(window.CHAT_CONFIG.groupId ? "group_id" : "receiver_id", window.CHAT_CONFIG.groupId || window.CHAT_CONFIG.otherUserId || "");
    toast("📤 جاري رفع الفيديو...");
    fetch("/api/chat/video", { method: "POST", body: fd })
        .then(r => r.json()).then(d => {
            if (d.success) location.reload();
            else alert("فشل الرفع: " + (d.error || ""));
        });
    input.value = "";
}
