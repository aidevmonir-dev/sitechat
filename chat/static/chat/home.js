// Demo page helpers: starter questions, and the "what the business sees" panel.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };

  function whenReady(fn) {
    if (window.SiteChat) return fn();
    var tries = 0;
    var timer = setInterval(function () {
      if (window.SiteChat || ++tries > 50) { clearInterval(timer); if (window.SiteChat) fn(); }
    }, 100);
  }

  function refresh() {
    var id = window.SiteChat && window.SiteChat.conversation();
    if (!id) {
      $("lead-status").textContent = "No conversation yet";
      $("lead-status").className = "";
      ["lead-name", "lead-email", "lead-note"].forEach(function (key) { $(key).textContent = "-"; });
      return;
    }
    fetch("/api/conversations/" + id)
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (conv) {
        if (!conv) return;
        $("lead-status").textContent = conv.status_label;
        $("lead-status").className = conv.status === "needs_human" ? "hot" : "";
        $("lead-name").textContent = conv.lead.name || "-";
        $("lead-email").textContent = conv.lead.email || "-";
        $("lead-note").textContent = conv.lead.note || "-";
      })
      .catch(function () {});
  }

  // The widget lives in a shadow root, so the demo fills its box through the public API surface:
  // open the panel, then type into the widget's own textarea and submit its form.
  function ask(text) {
    whenReady(function () {
      window.SiteChat.open();
      var root = document.querySelector("[data-sitechat]").shadowRoot;
      var input = root.querySelector("textarea");
      input.value = text;
      root.querySelector("form").dispatchEvent(new Event("submit", { cancelable: true }));
    });
  }

  document.querySelectorAll(".ask").forEach(function (btn) {
    btn.addEventListener("click", function () { ask(btn.textContent); });
  });
  $("reset").addEventListener("click", function () { whenReady(function () { window.SiteChat.reset(); refresh(); }); });
  window.addEventListener("sitechat:message", refresh);
  whenReady(refresh);
})();
