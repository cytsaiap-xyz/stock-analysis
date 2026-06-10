"use strict";
// Mirror of committee/markdown.py: splitThinking + a small safe markdown subset.
(function (global) {
  const TAG = /<(thought|think)\b[^>]*>([\s\S]*?)<\/\1>/gi;
  const OPEN = /<(thought|think)\b[^>]*>([\s\S]*)$/i;

  function splitThinking(text) {
    text = text || "";
    const thoughts = [];
    let answer = text.replace(TAG, (m, tag, body) => { thoughts.push(body.trim()); return ""; });
    const m = answer.match(OPEN);
    if (m) { thoughts.push(m[2].trim()); answer = answer.slice(0, m.index); }
    const thinking = thoughts.filter(Boolean).join("\n\n").trim();
    return { answer: answer.trim(), thinking: thinking };
  }

  function esc(s) {
    return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function inline(s) {
    s = s.replace(/`([^`]+)`/g, (m, c) => "<code>" + c + "</code>");
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) =>
      (u.indexOf("http://") === 0 || u.indexOf("https://") === 0)
        ? '<a href="' + u + '" target="_blank" rel="noopener">' + t + "</a>" : m);
    s = s.replace(/\*\*([^*]+)\*\*/g, (m, t) => "<strong>" + t + "</strong>");
    s = s.replace(/\*([^*]+)\*/g, (m, t) => "<em>" + t + "</em>");
    return s;
  }

  const HEADING = /^(#{1,3})\s+(.*)$/;
  const ULI = /^[-*]\s+(.*)$/;
  const OLI = /^\d+\.\s+(.*)$/;

  function renderMarkdown(text) {
    const lines = esc(text || "").split("\n");
    const out = [];
    let i = 0;
    const n = lines.length;
    while (i < n) {
      const line = lines[i];
      const stripped = line.trim();
      if (stripped.indexOf("```") === 0) {
        i++;
        const code = [];
        while (i < n && lines[i].trim().indexOf("```") !== 0) { code.push(lines[i]); i++; }
        i++;
        out.push("<pre><code>" + code.join("\n") + "</code></pre>");
        continue;
      }
      if (stripped === "") { i++; continue; }
      const h = line.match(HEADING);
      if (h) { const lvl = h[1].length + 2; out.push("<h" + lvl + ">" + inline(h[2].trim()) + "</h" + lvl + ">"); i++; continue; }
      if (ULI.test(line)) {
        const items = [];
        while (i < n && ULI.test(lines[i])) { items.push("<li>" + inline(lines[i].match(ULI)[1].trim()) + "</li>"); i++; }
        out.push("<ul>" + items.join("") + "</ul>");
        continue;
      }
      if (OLI.test(line)) {
        const items = [];
        while (i < n && OLI.test(lines[i])) { items.push("<li>" + inline(lines[i].match(OLI)[1].trim()) + "</li>"); i++; }
        out.push("<ol>" + items.join("") + "</ol>");
        continue;
      }
      const para = [];
      while (i < n && lines[i].trim() !== "" && !HEADING.test(lines[i]) && !ULI.test(lines[i])
             && !OLI.test(lines[i]) && lines[i].trim().indexOf("```") !== 0) {
        para.push(inline(lines[i].trim())); i++;
      }
      out.push("<p>" + para.join("<br>") + "</p>");
    }
    return out.join("");
  }

  function renderInline(text) { return inline(esc(text || "")); }

  global.MD = { splitThinking: splitThinking, renderMarkdown: renderMarkdown, renderInline: renderInline };
})(window);
