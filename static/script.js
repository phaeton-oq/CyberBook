/* CyberBook — фронт, подключённый к Flask API (/api/*). Сессия — по cookie. */

// ---------- API-слой ----------
async function apiFetch(path, { method = "GET", body } = {}) {
    const opts = { method, headers: { "Content-Type": "application/json" }, credentials: "same-origin" };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
        const err = new Error((data && data.error) || `Ошибка ${res.status}`);
        err.status = res.status;
        throw err;
    }
    return data;
}
const API = {
    me: () => apiFetch("/api/auth/me"),
    login: (email, password) => apiFetch("/api/auth/login", { method: "POST", body: { email, password } }),
    register: (p) => apiFetch("/api/auth/register", { method: "POST", body: p }),
    logout: () => apiFetch("/api/auth/logout", { method: "POST" }),
    updateProfile: (p) => apiFetch("/api/auth/me", { method: "PATCH", body: p }),
    createUser: (p) => apiFetch("/api/admin/users", { method: "POST", body: p }),
    deleteUser: (id) => apiFetch(`/api/admin/users/${id}`, { method: "DELETE" }),
    courses: () => apiFetch("/api/courses"),
    course: (id) => apiFetch(`/api/courses/${id}`),
    completeCourse: (id) => apiFetch(`/api/courses/${id}/complete`, { method: "POST" }),
    completeLesson: (id) => apiFetch(`/api/courses/lessons/${id}/complete`, { method: "POST" }),
    quizzes: () => apiFetch("/api/quiz"),
    quiz: (id) => apiFetch(`/api/quiz/${id}`),
    submitQuiz: (id, answers) => apiFetch(`/api/quiz/${id}/submit`, { method: "POST", body: { answers } }),
    inbox: () => apiFetch("/api/phishing/inbox"),
    email: (id) => apiFetch(`/api/phishing/email/${id}`),
    answerPhishing: (email_id, action) => apiFetch("/api/phishing/answer", { method: "POST", body: { email_id, action } }),
    generatePhishing: (p) => apiFetch("/api/phishing/generate", { method: "POST", body: p || {} }),
    chat: (message, history) => apiFetch("/api/assistant/chat", { method: "POST", body: { message, history } }),
    myStats: () => apiFetch("/api/stats/me"),
    leaderboard: () => apiFetch("/api/stats/leaderboard"),
    usersStats: () => apiFetch("/api/stats/users"),
};

// ---------- утилиты ----------
function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, c =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
// мини-markdown для AI-ответов (**жирный**, списки, переносы)
function md(text) {
    const lines = esc(text).split(/\r?\n/);
    let html = "", inList = false;
    const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
    for (const raw of lines) {
        const line = raw.trim();
        if (!line) { closeList(); continue; }
        let m = line.match(/^[-*•]\s+(.*)$/);
        if (m) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(m[1])}</li>`; }
        else { closeList(); html += `<p style="margin:6px 0;">${inline(line)}</p>`; }
    }
    closeList();
    return html;
    function inline(s) {
        return s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
                .replace(/`([^`]+)`/g, "<code>$1</code>");
    }
}

async function ensureAuth() {
    try { return await API.me(); }
    catch (e) { window.location.href = "index.html"; throw e; }
}

// ---------- авторизация ----------
async function doLogin() {
    const err = document.getElementById("auth-error");
    try {
        const user = await API.login(
            document.getElementById("login-email").value.trim(),
            document.getElementById("login-password").value,
        );
        window.location.href = user.role === "admin" ? "admin.html" : "dashboard.html";
    } catch (e) { if (err) err.textContent = e.message; }
}
async function doRegister() {
    const err = document.getElementById("auth-error");
    try {
        await API.register({
            name: document.getElementById("reg-name").value.trim(),
            email: document.getElementById("reg-email").value.trim(),
            department: document.getElementById("reg-department").value.trim() || "Общий",
            password: document.getElementById("reg-password").value,
        });
        window.location.href = "dashboard.html";
    } catch (e) { if (err) err.textContent = e.message; }
}
async function doLogout() {
    try { await API.logout(); } catch (_) {}
    window.location.href = "index.html";
}

// ---------- дашборд ----------
async function initDashboard() {
    await ensureAuth();
    const [stats, courses, quizzes] = await Promise.all([API.myStats(), API.courses(), API.quizzes()]);
    document.getElementById("score-value").textContent = `${stats.security_score}/100`;
    document.getElementById("score-hint").textContent =
        stats.security_score >= 80 ? "Отличный уровень!" :
        stats.security_score >= 50 ? "Хороший результат!" : "В зоне риска — тренируйтесь!";
    document.getElementById("stat-courses").textContent = `${stats.courses_completed} из ${courses.length}`;
    document.getElementById("stat-quizzes").textContent = `${stats.quiz_attempts} из ${quizzes.length}`;
    document.getElementById("stat-phishing").textContent = `${stats.phishing_caught} из ${stats.phishing_seen}`;
}

// ---------- курсы ----------
async function initCourses() {
    await ensureAuth();
    const courses = await API.courses();
    document.getElementById("courses-grid").innerHTML = courses.map(c => `
        <div class="box item-card" onclick="showCourse(${c.id})">
            <h4>${esc(c.title)}</h4>
            <p>${esc(c.description)}</p>
            <span style="font-size:13px;color:var(--gray-muted);">${c.lesson_count} урок(ов) · ${esc(c.topic)}</span>
        </div>`).join("");
}
async function showCourse(id) {
    const c = await API.course(id);
    const view = document.getElementById("lesson-view");
    const video = c.video_url
        ? `<iframe src="${esc(c.video_url)}" style="width:100%;aspect-ratio:16/9;border:none;border-radius:8px;margin:12px 0;" allowfullscreen></iframe>` : "";
    const lessons = (c.lessons || []).map(l => `
        <div style="padding:12px 0;border-bottom:1px solid var(--gray-light);">
            <strong>${esc(l.title)}</strong> ${l.completed ? "✅" : ""}
            <p style="color:var(--gray-muted);font-size:14px;margin-top:4px;">${esc(l.content)}</p>
        </div>`).join("");
    const quizBtn = (c.quizzes && c.quizzes.length)
        ? `<a href="quiz.html?quiz=${c.quizzes[0].id}" class="btn btn-main" style="margin-top:14px;">Пройти тест по курсу</a>` : "";
    document.getElementById("lesson-title").textContent = c.title;
    document.getElementById("lesson-text").innerHTML =
        `<div style="white-space:pre-wrap;line-height:1.6;">${md(c.content)}</div>${video}
         <h4 style="margin-top:16px;">Уроки</h4>${lessons}
         <button class="btn btn-ok" style="margin-top:14px;" onclick="finishCourse(${c.id})">Отметить курс пройденным</button> ${quizBtn}`;
    view.style.display = "block";
    view.scrollIntoView({ behavior: "smooth" });
}
async function finishCourse(id) {
    try {
        const r = await API.completeCourse(id);
        alert(`Курс пройден! Security Score: ${r.security_score}/100` +
            (r.new_badges && r.new_badges.length ? `\nНовый значок: ${r.new_badges.join(", ")}` : ""));
    } catch (e) { alert(e.message); }
}

// ---------- квизы ----------
let currentQuiz = null;
async function initQuiz() {
    await ensureAuth();
    const quizzes = await API.quizzes();
    document.getElementById("quiz-list").innerHTML = quizzes.map(q => `
        <div class="box item-card" onclick="loadQuiz(${q.id})">
            <h4>${esc(q.title)}</h4>
            <p>${q.question_count} вопрос(ов)</p>
        </div>`).join("");
    const pre = new URLSearchParams(location.search).get("quiz");
    if (pre) loadQuiz(+pre);
}
async function loadQuiz(id) {
    currentQuiz = await API.quiz(id);
    document.getElementById("quiz-picker").style.display = "none";
    document.getElementById("quiz-result").innerHTML = "";
    document.getElementById("quiz-container").innerHTML = `
        <div class="box">
            <h3>${esc(currentQuiz.title)}</h3>
            ${currentQuiz.questions.map((q, qi) => `
                <div class="q-block" data-qi="${qi}" style="margin-bottom:20px;">
                    <p class="q-title"><strong>Вопрос ${qi + 1}:</strong> ${esc(q.text)}</p>
                    <div class="q-list">
                        ${q.options.map((o, oi) => `
                            <button class="btn-option opt-btn" data-oi="${oi}" onclick="pickAnswer(${qi}, ${oi})">${esc(o)}</button>`).join("")}
                    </div>
                </div>`).join("")}
            <button class="btn btn-main" id="quiz-submit" onclick="submitCurrentQuiz()">Проверить</button>
        </div>`;
}
const quizAnswers = {};
function pickAnswer(qi, oi) {
    quizAnswers[qi] = oi;
    document.querySelectorAll(`[data-qi="${qi}"] .opt-btn`).forEach(b => {
        const sel = +b.dataset.oi === oi;
        b.style.backgroundColor = sel ? "#fdeaeb" : "#f2f3f5";
        b.style.borderColor = sel ? "#e30613" : "transparent";
    });
}
async function submitCurrentQuiz() {
    const answers = currentQuiz.questions.map((_, i) => (i in quizAnswers ? quizAnswers[i] : -1));
    const res = await API.submitQuiz(currentQuiz.id, answers);
    res.review.forEach((r, qi) => {
        document.querySelectorAll(`[data-qi="${qi}"] .opt-btn`).forEach(b => {
            const oi = +b.dataset.oi;
            b.disabled = true;
            if (oi === r.correct_index) { b.style.backgroundColor = "#1aa64b"; b.style.color = "#fff"; }
            else if (oi === r.chosen) { b.style.backgroundColor = "#e30613"; b.style.color = "#fff"; }
        });
        if (r.explanation) {
            const block = document.querySelector(`[data-qi="${qi}"]`);
            const ex = document.createElement("div");
            ex.className = "alert-panel";
            ex.innerHTML = `<strong>Разбор:</strong> ${esc(r.explanation)}`;
            block.appendChild(ex);
        }
    });
    const btn = document.getElementById("quiz-submit");
    if (btn) btn.remove();
    const badges = res.new_badges && res.new_badges.length ? `<p>🎉 Новый значок: ${esc(res.new_badges.join(", "))}</p>` : "";
    document.getElementById("quiz-result").innerHTML = `
        <div class="box" style="border-left:4px solid ${res.score >= 60 ? "#1aa64b" : "#e30613"};">
            <h3>Результат: ${res.score}% (${res.correct} из ${res.total})</h3>
            <p>Security Score: <strong>${res.security_score}/100</strong> · Очки: <strong>${res.points}</strong></p>
            ${badges}
        </div>`;
    document.getElementById("quiz-result").scrollIntoView({ behavior: "smooth" });
}

// ---------- AI-чат ----------
const chatHistory = [];
async function sendChatMessage() {
    const input = document.getElementById("chat-input");
    const area = document.getElementById("chat-area");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    const u = document.createElement("div");
    u.className = "msg out";
    u.textContent = text;
    area.appendChild(u);
    chatHistory.push({ role: "user", content: text });
    const typing = document.createElement("div");
    typing.className = "msg in";
    typing.textContent = "…";
    area.appendChild(typing);
    area.scrollTop = area.scrollHeight;
    try {
        const res = await API.chat(text, chatHistory);
        typing.innerHTML = md(res.reply);
        chatHistory.push({ role: "assistant", content: res.reply });
    } catch (e) {
        typing.textContent = "Ошибка: " + e.message;
    }
    area.scrollTop = area.scrollHeight;
}

// ---------- инбокс (фишинг) ----------
async function initInbox() {
    await ensureAuth();
    const emails = await API.inbox();
    document.getElementById("inbox-list").innerHTML = emails.map(e => {
        const controls = e.answered
            ? `<div class="alert-panel" style="border-color:${e.was_correct ? "#1aa64b" : "#e30613"};">
                   <strong style="color:${e.was_correct ? "#1aa64b" : "#e30613"};">
                   ${e.was_correct ? "✅ Вы ответили верно" : "❌ Вы ошиблись"}</strong> — письмо уже разобрано.
               </div>`
            : `<div class="btn-group">
                   <button class="btn btn-bad" onclick="answerMail(${e.id}, 'trusted')">Доверять письму</button>
                   <button class="btn btn-ok" onclick="answerMail(${e.id}, 'reported')">Пожаловаться на фишинг</button>
               </div>
               <div class="alert-panel" id="mail-fb-${e.id}" style="display:none;"></div>`;
        return `
        <div class="box mail-box" data-email="${e.id}">
            <div class="mail-top">
                <strong>От:</strong> ${esc(e.sender_name || "")} &lt;${esc(e.sender)}&gt;<br>
                <strong>Тема:</strong> ${esc(e.subject)}
            </div>
            <div class="mail-text">${esc(e.body).replace(/\n/g, "<br>")}</div>
            ${controls}
        </div>`;
    }).join("");
}
async function answerMail(id, action) {
    const fb = document.getElementById(`mail-fb-${id}`);
    try {
        const res = await API.answerPhishing(id, action);
        document.querySelectorAll(`[data-email="${id}"] .btn`).forEach(b => b.disabled = true);
        const flags = (res.red_flags && res.red_flags.length)
            ? `<p style="margin-top:8px;"><strong>🚩 Признаки:</strong></p><ul>${res.red_flags.map(f => `<li>${esc(f)}</li>`).join("")}</ul>` : "";
        const ai = res.explanation ? `<div style="margin-top:8px;"><strong>🤖 Ассистент:</strong> ${md(res.explanation)}</div>` : "";
        fb.style.display = "block";
        fb.style.borderColor = res.correct ? "#1aa64b" : "#e30613";
        fb.style.color = "#1d2023";
        fb.innerHTML = `<strong style="color:${res.correct ? "#1aa64b" : "#e30613"};">${res.correct ? "Верно!" : "Ошибка."}</strong> ` +
            `${res.is_phishing ? "Это фишинг." : "Письмо безопасное."}${flags}${ai}` +
            `<p style="margin-top:8px;">Security Score: <strong>${res.security_score}/100</strong></p>`;
    } catch (e) { if (fb) { fb.style.display = "block"; fb.textContent = e.message; } }
}

// ---------- рейтинг ----------
async function initRating() {
    await ensureAuth();
    const rows = await API.leaderboard();
    const medal = { 1: "🥇", 2: "🥈", 3: "🥉" };
    document.getElementById("rating-list").innerHTML = rows.map(r => `
        <tr>
            <td style="text-align:center;font-weight:700;">${medal[r.rank] || r.rank}</td>
            <td>${esc(r.name)}</td>
            <td>${esc(r.department)}</td>
            <td style="text-align:center;">${(r.badges || []).map(b => b.icon).join(" ") || "—"}</td>
            <td style="text-align:right;padding-right:24px;" class="${r.security_score >= 75 ? "ok-status" : "warn-status"}">${r.security_score} / 100</td>
        </tr>`).join("") || `<tr><td colspan="5">Нет данных</td></tr>`;
}

// ---------- ачивки ----------
async function initAchievements() {
    await ensureAuth();
    const stats = await API.myStats();
    const grid = document.getElementById("achievements-grid");
    const badges = stats.badges || [];
    if (!badges.length) {
        grid.innerHTML = `<div class="box"><p style="color:var(--gray-muted);">Пока нет значков — проходите курсы, тесты и ловите фишинг!</p></div>`;
        return;
    }
    grid.innerHTML = badges.map(b => `
        <div class="box" style="border-left:4px solid #0a9396;display:flex;gap:20px;align-items:center;">
            <div style="font-size:36px;background:var(--gray-light);width:70px;height:70px;border-radius:50%;display:flex;align-items:center;justify-content:center;">${b.icon}</div>
            <div>
                <h4 style="margin-bottom:4px;">${esc(b.name)}</h4>
                <span style="font-size:12px;color:#0a9396;font-weight:600;">Получено</span>
            </div>
        </div>`).join("");
}

// ---------- админ ----------
async function initAdmin() {
    const user = await ensureAuth();
    if (user.role !== "admin") { window.location.href = "dashboard.html"; return; }
    try {
        const rows = await API.usersStats();
        document.getElementById("employees-list").innerHTML = rows.map(u => `
            <tr>
                <td><span class="tag-name">${esc(u.name)}</span> <span style="color:var(--gray-muted);font-size:13px;">${esc(u.department)}</span></td>
                <td>${u.security_score} / 100</td>
                <td class="${u.security_score >= 50 ? "ok-status" : "warn-status"}">${u.security_score >= 50 ? "Безопасен" : "В зоне риска"}</td>
                <td><button class="btn-del" data-user-id="${u.id}" onclick="deleteEmployee(this)">Удалить</button></td>
            </tr>`).join("");
    } catch (e) { /* не админ или ошибка */ }
}
async function runPhishingCampaign() {
    try {
        const res = await API.generatePhishing({ difficulty: "medium" });
        alert(`Фишинг-кампания запущена! Новое письмо в инбоксе сотрудников:\n«${res.email.subject}»`);
    } catch (e) { alert(e.message); }
}

// ---------- профиль ----------
async function initProfile() {
    const user = await ensureAuth();
    document.getElementById("profile-display-name").textContent = user.name;
    document.getElementById("profile-display-role").textContent = user.department;
    document.getElementById("input-profile-name").value = user.name;
    document.getElementById("input-profile-role").value = user.department;
    document.getElementById("input-profile-email").value = user.email;
}
async function saveProfileData() {
    const status = document.getElementById("profile-save-status");
    const payload = {
        name: document.getElementById("input-profile-name").value.trim(),
        department: document.getElementById("input-profile-role").value.trim(),
        email: document.getElementById("input-profile-email").value.trim(),
    };
    const pass = document.getElementById("input-profile-pass").value;
    if (pass) payload.password = pass;
    try {
        const user = await API.updateProfile(payload);
        document.getElementById("profile-display-name").textContent = user.name;
        document.getElementById("profile-display-role").textContent = user.department;
        document.getElementById("input-profile-pass").value = "";
        if (status) {
            status.style.color = "var(--success)";
            status.textContent = "✓ Изменения успешно сохранены!";
            status.style.display = "block";
            setTimeout(() => status.style.display = "none", 3000);
        }
    } catch (e) {
        if (status) {
            status.style.color = "var(--primary)";
            status.textContent = e.message;
            status.style.display = "block";
        }
    }
}

// добавление/удаление сотрудников — через реальный API (только админ)
async function addEmployee() {
    const name = prompt("Имя нового сотрудника:");
    if (!name || !name.trim()) return;
    const email = prompt("Email сотрудника:");
    if (!email || !email.trim()) return;
    const department = prompt("Отдел:", "Общий") || "Общий";
    const password = prompt("Временный пароль:", "user123") || "user123";
    try {
        await API.createUser({ name: name.trim(), email: email.trim(), department, password });
        initAdmin();
    } catch (e) { alert(e.message); }
}
async function deleteEmployee(btn) {
    const id = btn.dataset.userId;
    if (!id) { btn.closest("tr")?.remove(); return; }
    if (!confirm("Удалить этого сотрудника безвозвратно?")) return;
    try {
        await API.deleteUser(id);
        btn.closest("tr")?.remove();
    } catch (e) { alert(e.message); }
}

// ---------- роутер: инициализация по элементам страницы ----------
document.addEventListener("DOMContentLoaded", () => {
    const has = (id) => document.getElementById(id);
    // авто-переход с логина, если уже авторизован
    if (has("login-form") || has("register-form")) {
        API.me().then(u => { window.location.href = u.role === "admin" ? "admin.html" : "dashboard.html"; }).catch(() => {});
        return;
    }
    if (has("score-value")) initDashboard();
    else if (has("courses-grid")) initCourses();
    else if (has("quiz-list")) initQuiz();
    else if (has("chat-area")) ensureAuth();
    else if (has("inbox-list")) initInbox();
    else if (has("rating-list")) initRating();
    else if (has("achievements-grid")) initAchievements();
    else if (has("employees-list")) initAdmin();
    else if (has("profile-display-name")) initProfile();
});
