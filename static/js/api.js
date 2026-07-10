const API = {
  async request(path, { method = "GET", body } = {}) {
    const opts = {
      method,
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
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

  // авторизация
  me() { return this.get("/api/auth/me"); },
  login(email, password) { return this.post("/api/auth/login", { email, password }); },
  register(payload) { return this.post("/api/auth/register", payload); },
  logout() { return this.post("/api/auth/logout"); },

  // курсы
  courses() { return this.get("/api/courses"); },
  course(id) { return this.get(`/api/courses/${id}`); },
  createCourse(payload) { return this.post("/api/courses", payload); },
  updateCourse(id, payload) { return this.request(`/api/courses/${id}`, { method: "PUT", body: payload }); },
  deleteCourse(id) { return this.request(`/api/courses/${id}`, { method: "DELETE" }); },
  completeCourse(id) { return this.post(`/api/courses/${id}/complete`); },
  myCourseProgress() { return this.get("/api/courses/progress/me"); },
  lessons(courseId) { return this.get(`/api/courses/${courseId}/lessons`); },
  lesson(id) { return this.get(`/api/courses/lessons/${id}`); },
  completeLesson(id) { return this.post(`/api/courses/lessons/${id}/complete`); },

  // квизы
  quizzes() { return this.get("/api/quiz"); },
  quizHistory() { return this.get("/api/quiz/history"); },
  quiz(id) { return this.get(`/api/quiz/${id}`); },
  submitQuiz(id, answers) { return this.post(`/api/quiz/${id}/submit`, { answers }); },
  generateQuiz(payload) { return this.post("/api/quiz/generate", payload); },
  personalizedQuiz(payload) { return this.post("/api/quiz/personalized", payload); },

  // фишинг
  inbox() { return this.get("/api/phishing/inbox"); },
  email(id) { return this.get(`/api/phishing/email/${id}`); },
  answerPhishing(email_id, action) { return this.post("/api/phishing/answer", { email_id, action }); },
  generatePhishing(payload) { return this.post("/api/phishing/generate", payload); },

  // ассистент
  chat(message, history) { return this.post("/api/assistant/chat", { message, history }); },

  // сканер (VirusTotal + AI)
  scanStatus() { return this.get("/api/scan/status"); },
  scanHistory() { return this.get("/api/scan/history"); },
  scanUrl(url) { return this.post("/api/scan/url", { url }); },
  scanFileHash(sha256, filename) {
    return this.post("/api/scan/file", { sha256, filename });
  },
  async scanFileUpload(file) {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/scan/file", {
      method: "POST",
      credentials: "same-origin",
      body: form,
    });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
      const err = new Error((data && data.error) || `Ошибка ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return data;
  },
  scanReviewText(text) { return this.post("/api/scan/review", { text }); },

  // статистика
  overview() { return this.get("/api/stats/overview"); },
  leaderboard() { return this.get("/api/stats/leaderboard"); },
  myStats() { return this.get("/api/stats/me"); },
  statsTimeline() { return this.get("/api/stats/timeline"); },
  statsUsers() { return this.get("/api/stats/users"); },
  exportUserCsv(userId) { return this.get(`/api/stats/export/${userId}`); },
  exportUserPdf(userId) { return this.get(`/api/stats/export/${userId}/pdf`); },
};

// Гард: редирект на логин, если не авторизован.
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
