/* SiteChat widget. Embed with:
 *   <script src="https://YOUR-SITECHAT-HOST/widget.js" data-site="your-site" async></script>
 * Optional attributes: data-open="true" (start opened), data-position="left".
 * Everything renders inside a shadow root, so the host page's CSS and the widget's CSS never collide.
 */
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script || window.__sitechatLoaded) return;
  window.__sitechatLoaded = true;

  var base = new URL(script.src).origin;
  var siteSlug = script.getAttribute("data-site") || "demo";
  var startOpen = script.getAttribute("data-open") === "true";
  var onLeft = script.getAttribute("data-position") === "left";
  var storageKey = "sitechat:" + siteSlug;
  var conversationId = null;
  var busy = false;

  try { conversationId = localStorage.getItem(storageKey); } catch (e) { /* storage blocked: chat still works */ }

  function api(path, options) {
    return fetch(base + path, options).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (!res.ok) throw new Error(body.error || "Something went wrong. Please try again.");
        return body;
      });
    });
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  var host = el("div");
  host.setAttribute("data-sitechat", "");
  var root = host.attachShadow({ mode: "open" });
  var style = el("style");
  style.textContent = [
    ":host{all:initial}",
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif}",
    ".wrap{position:fixed;bottom:20px;" + (onLeft ? "left" : "right") + ":20px;z-index:2147483000;display:flex;flex-direction:column;align-items:" + (onLeft ? "flex-start" : "flex-end") + ";gap:12px}",
    ".launch{width:58px;height:58px;border-radius:50%;border:0;background:var(--accent);color:#fff;cursor:pointer;box-shadow:0 8px 24px rgba(20,30,45,.28);display:grid;place-items:center}",
    ".launch:focus-visible,.send:focus-visible,.close:focus-visible,textarea:focus-visible{outline:3px solid #1c2b39;outline-offset:2px}",
    ".launch svg{width:28px;height:28px}",
    ".panel{width:370px;max-width:calc(100vw - 24px);height:540px;max-height:calc(100vh - 110px);background:#fff;border-radius:16px;box-shadow:0 18px 50px rgba(20,30,45,.3);display:flex;flex-direction:column;overflow:hidden;border:1px solid #d9e0e6}",
    ".panel[hidden]{display:none}",
    ".head{background:#213343;color:#fff;padding:14px 16px;display:flex;align-items:center;gap:10px}",
    ".head strong{font-size:16px;flex:1;line-height:1.2}",
    ".head small{display:block;font-weight:400;font-size:12px;opacity:.8;margin-top:2px}",
    ".close{background:none;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer;padding:4px 8px;border-radius:6px}",
    ".log{flex:1;overflow-y:auto;padding:16px;background:#f5f7f9;display:flex;flex-direction:column;gap:10px}",
    ".msg{max-width:84%;padding:10px 13px;border-radius:14px;font-size:14.5px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere;color:#1c2b39}",
    ".msg.bot{background:#fff;border:1px solid #d9e0e6;align-self:flex-start;border-bottom-left-radius:4px}",
    ".msg.me{background:var(--accent);color:#fff;align-self:flex-end;border-bottom-right-radius:4px}",
    ".msg.note{align-self:center;background:#e7f4ec;color:#1b6e4b;font-size:13px;font-weight:600;border-radius:999px;padding:6px 12px;max-width:100%}",
    ".msg.err{align-self:center;background:#fdecea;color:#b3261e;font-size:13px;max-width:100%}",
    ".typing{color:#5b6b7b;font-style:italic}",
    "form{display:flex;gap:8px;padding:12px;border-top:1px solid #d9e0e6;background:#fff}",
    "textarea{flex:1;resize:none;border:1.5px solid #d9e0e6;border-radius:10px;padding:9px 11px;font-size:14.5px;line-height:1.35;height:42px;max-height:96px;color:#1c2b39}",
    ".send{border:0;border-radius:10px;background:var(--accent);color:#fff;font-weight:700;padding:0 15px;cursor:pointer;font-size:14.5px}",
    ".send:disabled{opacity:.55;cursor:progress}",
    ".foot{font-size:11px;color:#5b6b7b;text-align:center;padding:0 12px 9px;background:#fff}",
    ".foot a{color:inherit}",
    "@media (max-width:480px){.wrap{bottom:12px;" + (onLeft ? "left" : "right") + ":12px}.panel{height:calc(100vh - 96px)}}",
  ].join("");
  root.appendChild(style);

  var wrap = el("div", "wrap");
  var panel = el("section", "panel");
  panel.hidden = true;
  panel.setAttribute("aria-label", "Chat");
  var head = el("div", "head");
  var title = el("strong", "", "Chat");
  var close = el("button", "close", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Close chat");
  head.appendChild(title);
  head.appendChild(close);
  var log = el("div", "log");
  log.setAttribute("aria-live", "polite");
  var form = el("form");
  var input = el("textarea");
  input.placeholder = "Type your question";
  input.maxLength = 500;
  input.setAttribute("aria-label", "Your message");
  var send = el("button", "send", "Send");
  send.type = "submit";
  form.appendChild(input);
  form.appendChild(send);
  var foot = el("div", "foot");
  foot.appendChild(document.createTextNode("AI assistant. Answers come from this site's help articles. "));
  var credit = el("a", "", "Powered by SiteChat");
  credit.href = base + "/";
  credit.target = "_blank";
  credit.rel = "noopener";
  foot.appendChild(credit);
  panel.appendChild(head);
  panel.appendChild(log);
  panel.appendChild(form);
  panel.appendChild(foot);

  var launch = el("button", "launch");
  launch.type = "button";
  launch.setAttribute("aria-label", "Open chat");
  launch.setAttribute("aria-expanded", "false");
  launch.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>';
  wrap.appendChild(panel);
  wrap.appendChild(launch);
  root.appendChild(wrap);

  function add(kind, text) {
    var node = el("div", "msg " + kind, text);
    log.appendChild(node);
    log.scrollTop = log.scrollHeight;
    return node;
  }

  function announce(name, detail) {
    try { window.dispatchEvent(new CustomEvent("sitechat:" + name, { detail: detail })); } catch (e) { /* old browser */ }
  }

  // The greeting always sits first, even if the visitor sent a message before the config arrived.
  function greet(text) {
    var node = el("div", "msg bot", text);
    log.insertBefore(node, log.firstChild);
  }

  var loaded = false;
  function load() {
    if (loaded) return;
    loaded = true;
    api("/api/sites/" + encodeURIComponent(siteSlug) + "/config")
      .then(function (cfg) {
        title.textContent = cfg.name;
        title.appendChild(el("small", "", "Usually replies in a few seconds"));
        wrap.style.setProperty("--accent", cfg.accent);
        greet(cfg.greeting);
        if (!conversationId || busy) return null;
        return api("/api/conversations/" + conversationId).then(function (conv) {
          conv.messages.forEach(function (m) { add(m.role === "user" ? "me" : "bot", m.text); });
        }).catch(function () {
          conversationId = null;  // expired or deleted on the server: start fresh
          try { localStorage.removeItem(storageKey); } catch (e) { /* ignore */ }
        });
      })
      .catch(function (err) { add("err", err.message); });
  }

  function setOpen(open) {
    panel.hidden = !open;
    launch.setAttribute("aria-expanded", String(open));
    launch.setAttribute("aria-label", open ? "Close chat" : "Open chat");
    if (open) { load(); input.focus(); }
  }

  function submit() {
    var text = input.value.trim();
    if (!text || busy) return;
    busy = true;
    send.disabled = true;
    input.value = "";
    add("me", text);
    var typing = add("bot typing", "Typing...");
    api("/api/sites/" + encodeURIComponent(siteSlug) + "/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation: conversationId, text: text, page: location.href }),
    })
      .then(function (data) {
        typing.remove();
        conversationId = data.conversation;
        try { localStorage.setItem(storageKey, conversationId); } catch (e) { /* ignore */ }
        add("bot", data.reply);
        if (data.lead_saved) add("note", "Your details were sent to the team");
        announce("message", { conversation: conversationId, leadSaved: data.lead_saved, needsHuman: data.needs_human });
      })
      .catch(function (err) { typing.remove(); add("err", err.message); })
      .then(function () { busy = false; send.disabled = false; input.focus(); });
  }

  wrap.style.setProperty("--accent", "#ff7a59");
  launch.addEventListener("click", function () { setOpen(panel.hidden); });
  close.addEventListener("click", function () { setOpen(false); launch.focus(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); submit(); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
    if (e.key === "Escape") { setOpen(false); launch.focus(); }
  });

  window.SiteChat = {
    open: function () { setOpen(true); },
    close: function () { setOpen(false); },
    conversation: function () { return conversationId; },
    reset: function () {
      conversationId = null;
      try { localStorage.removeItem(storageKey); } catch (e) { /* ignore */ }
      log.textContent = "";
      loaded = false;
      if (!panel.hidden) load();
    },
  };

  function mount() { document.body.appendChild(host); if (startOpen) setOpen(true); }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
})();
