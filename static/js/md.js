// Мини-рендер Markdown для AI-ответов (gpt-oss любит **жирный**, списки, `код`).
// Сначала экранируем HTML, потом включаем ограниченный набор разметки — XSS-safe.
(function () {
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, c =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function renderInline(s) {
    return s
      // `код`
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      // **жирный**
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      // *курсив* или _курсив_ (не задевая уже вставленный <strong>)
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/_([^_\n]+)_/g, "<em>$1</em>")
      // [текст](url)
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }

  // Markdown -> HTML. Поддержка: заголовки ###, списки - / *, нумерация 1., абзацы.
  function render(md) {
    const lines = escapeHtml(md == null ? "" : md).split(/\r?\n/);
    let html = "";
    let listType = null; // 'ul' | 'ol' | null

    const closeList = () => { if (listType) { html += `</${listType}>`; listType = null; } };

    for (let raw of lines) {
      const line = raw.trim();
      if (!line) { closeList(); continue; }

      let m;
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
        closeList();
        const level = Math.min(m[1].length + 2, 6); // ## -> h4 и т.п.
        html += `<h${level}>${renderInline(m[2])}</h${level}>`;
      } else if ((m = line.match(/^[-*•]\s+(.*)$/))) {
        if (listType !== "ul") { closeList(); html += "<ul>"; listType = "ul"; }
        html += `<li>${renderInline(m[1])}</li>`;
      } else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) {
        if (listType !== "ol") { closeList(); html += "<ol>"; listType = "ol"; }
        html += `<li>${renderInline(m[1])}</li>`;
      } else {
        closeList();
        html += `<p>${renderInline(line)}</p>`;
      }
    }
    closeList();
    return html;
  }

  window.renderMarkdown = render;
})();
