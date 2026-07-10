// Общий помощник для запросов к API CyberBook.
// Все запросы идут на тот же origin (Flask раздаёт и статику, и /api),
// поэтому куки-сессия Flask-Login работает автоматически.

const API = {
  async request(path, { method = "GET", body } = {}) {
    const opts = {
      method,
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin", // важно: тянем cookie сессии
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
      const err = new Error((data && data.error) || `Ошибка ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  },
  get(p) { return this.request(p); },
  post(p, body) { return this.request(p, { method: "POST", body }); },

  // ---- auth ----
  me() { return this.get("/api/auth/me"); },
  login(email, password) { return this.post("/api/auth/login", { email, password }); },
  register(payload) { return this.post("/api/auth/register", payload); },
  logout() { return this.post("/api/auth/logout"); },

  // ---- courses ----
  courses() { return this.get("/api/courses"); },
  course(id) { return this.get(`/api/courses/${id}`); },

  // ---- quiz ----
  quiz(id) { return this.get(`/api/quiz/${id}`); },
  submitQuiz(id, answers) { return this.post(`/api/quiz/${id}/submit`, { answers }); },
  generateQuiz(payload) { return this.post("/api/quiz/generate", payload); },

  // ---- phishing ----
  inbox() { return this.get("/api/phishing/inbox"); },
  email(id) { return this.get(`/api/phishing/email/${id}`); },
  answerPhishing(email_id, action) { return this.post("/api/phishing/answer", { email_id, action }); },
  generatePhishing(payload) { return this.post("/api/phishing/generate", payload); },

  // ---- assistant ----
  chat(message, history) { return this.post("/api/assistant/chat", { message, history }); },

  // ---- stats ----
  overview() { return this.get("/api/stats/overview"); },
  leaderboard() { return this.get("/api/stats/leaderboard"); },
  myStats() { return this.get("/api/stats/me"); },
};

// Гард: редиректит на логин, если не авторизован. Возвращает user.
async function requireAuth() {
  try {
    return await API.me();
  } catch (e) {
    window.location.href = "/index.html";
    throw e;
  }
}

window.API = API;
window.requireAuth = requireAuth;
