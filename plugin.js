/**
 * Email Capture Plugin
 * ====================
 * Drop this ONE line into any page:
 *
 *   <script src="https://yourserver.com/plugin.js"
 *           data-website="mysite"
 *           data-file="report.pdf"
 *           data-title="Get the free report"
 *           data-btn="Send me the file"
 *           data-theme="light"
 *           data-position="inline">
 *   </script>
 *
 * Attributes:
 *   data-website  — required — your website name (saved in DB for tracking)
 *   data-file     — required — exact filename on server (e.g. "ebook.pdf")
 *   data-theme    — "light" | "dark"  (default: "light")
 *   data-title    — heading text
 *   data-subtitle — subheading text
 *   data-btn      — button label
 *   data-position — "inline" | "bottom-right" | "bottom-left" | "center-popup"
 *
 *   -- Optional, shown in the follow-up email only (omit to hide) --
 *   data-doc-link     — URL to technical/product documentation
 *   data-spec-module  — e.g. "VMX Hypervisor"
 *   data-spec-version — e.g. "v10.0-Stable"
 *   data-spec-arch    — e.g. "x86_64 (64-Bit)"
 */
(function () {
  "use strict";

  const SCRIPT    = document.currentScript;
  const SERVER    = SCRIPT.src.replace("/plugin.js", "");
  const WEBSITE   = SCRIPT.getAttribute("data-website")  || "default";
  const FILE      = SCRIPT.getAttribute("data-file")     || "";
  const THEME     = SCRIPT.getAttribute("data-theme")    || "light";
  const TITLE     = SCRIPT.getAttribute("data-title")    || "Get your free file";
  const SUBTITLE  = SCRIPT.getAttribute("data-subtitle") || "Enter your email and we\u2019ll send you the download link instantly.";
  const BTN_LABEL = SCRIPT.getAttribute("data-btn")      || "Send me the link";
  const POSITION  = SCRIPT.getAttribute("data-position") || "inline";

  // Optional — email-only fields. Empty string if not provided, sent as null.
  const DOC_LINK     = SCRIPT.getAttribute("data-doc-link")     || "";
  const SPEC_MODULE  = SCRIPT.getAttribute("data-spec-module")  || "";
  const SPEC_VERSION = SCRIPT.getAttribute("data-spec-version") || "";
  const SPEC_ARCH    = SCRIPT.getAttribute("data-spec-arch")    || "";

  if (!FILE) {
    console.error("[EmailPlugin] data-file attribute is required.");
    return;
  }

  // ── Colors ──────────────────────────────────────────────────────────────────
  const isDark = THEME === "dark";
  const c = isDark
    ? { bg: "#18181b", card: "#27272a", text: "#f4f4f5", sub: "#a1a1aa", border: "#3f3f46", btn: "#2563eb", btnText: "#fff", input: "#3f3f46", inputText: "#f4f4f5" }
    : { bg: "#f8fafc", card: "#ffffff", text: "#1e293b", sub: "#64748b", border: "#e2e8f0", btn: "#2563eb", btnText: "#fff", input: "#f1f5f9", inputText: "#1e293b" };

  // ── Styles ───────────────────────────────────────────────────────────────────
  const css = `
    .ecp-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.55); z-index:99998; align-items:center; justify-content:center; }
    .ecp-overlay.active { display:flex; }
    .ecp-widget { font-family:'Segoe UI',system-ui,sans-serif; background:${c.card}; border:1px solid ${c.border}; border-radius:16px; padding:28px 28px 24px; width:100%; max-width:400px; box-shadow:0 8px 32px rgba(0,0,0,0.15); position:relative; box-sizing:border-box; }
    .ecp-inline { margin:24px auto; }
    .ecp-floating { position:fixed; bottom:24px; z-index:99999; width:360px; max-width:calc(100vw - 32px); box-shadow:0 12px 40px rgba(0,0,0,0.22); }
    .ecp-floating.bottom-right { right:24px; }
    .ecp-floating.bottom-left  { left:24px; }
    .ecp-close { position:absolute; top:12px; right:14px; background:none; border:none; font-size:20px; cursor:pointer; color:${c.sub}; line-height:1; }
    .ecp-close:hover { color:${c.text}; }
    .ecp-icon { font-size:32px; margin-bottom:8px; }
    .ecp-title { margin:0 0 6px; font-size:18px; font-weight:700; color:${c.text}; line-height:1.3; }
    .ecp-sub { margin:0 0 6px; font-size:13.5px; color:${c.sub}; line-height:1.5; }
    .ecp-filename { margin:0 0 18px; font-size:12.5px; color:${c.btn}; font-weight:600; }
    .ecp-form { display:flex; flex-direction:column; gap:10px; }
    .ecp-input { width:100%; padding:11px 14px; border-radius:8px; border:1.5px solid ${c.border}; background:${c.input}; color:${c.inputText}; font-size:14px; outline:none; box-sizing:border-box; transition:border-color 0.2s; }
    .ecp-input:focus { border-color:${c.btn}; }
    .ecp-input::placeholder { color:${c.sub}; }
    .ecp-btn { padding:12px; border-radius:8px; background:${c.btn}; color:${c.btnText}; border:none; font-size:14px; font-weight:600; cursor:pointer; transition:opacity 0.2s,transform 0.1s; }
    .ecp-btn:hover:not(:disabled) { opacity:0.88; transform:translateY(-1px); }
    .ecp-btn:disabled { opacity:0.6; cursor:not-allowed; }
    .ecp-msg { margin-top:10px; padding:10px 14px; border-radius:8px; font-size:13px; text-align:center; display:none; }
    .ecp-msg.success { background:#dcfce7; color:#166534; display:block; }
    .ecp-msg.error   { background:#fee2e2; color:#991b1b; display:block; }
    .ecp-privacy { margin-top:10px; font-size:11.5px; color:${c.sub}; text-align:center; }
    .ecp-trigger-btn { position:fixed; bottom:24px; z-index:99997; background:${c.btn}; color:#fff; border:none; border-radius:50px; padding:13px 22px; font-size:14px; font-weight:600; cursor:pointer; box-shadow:0 4px 16px rgba(37,99,235,0.4); transition:transform 0.2s,box-shadow 0.2s; }
    .ecp-trigger-btn:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(37,99,235,0.45); }
    .ecp-trigger-btn.bottom-right { right:24px; }
    .ecp-trigger-btn.bottom-left  { left:24px; }
  `;

  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  // ── Build Widget ─────────────────────────────────────────────────────────────
  function buildWidget() {
    const div = document.createElement("div");
    div.className = "ecp-widget";
    div.innerHTML = `
      <div class="ecp-icon">&#128196;</div>
      <h3 class="ecp-title">${TITLE}</h3>
      <p  class="ecp-sub">${SUBTITLE}</p>
      <p  class="ecp-filename">&#128206; ${FILE}</p>
      <div class="ecp-form">
        <input class="ecp-input" type="email" placeholder="your@email.com" autocomplete="email" />
        <button class="ecp-btn">${BTN_LABEL}</button>
      </div>
      <div class="ecp-msg"></div>
      <p class="ecp-privacy">&#128274; No spam. Unsubscribe anytime.</p>
    `;
    return div;
  }

  // ── Submit ───────────────────────────────────────────────────────────────────
  function attachSubmit(widget) {
    const input = widget.querySelector(".ecp-input");
    const btn   = widget.querySelector(".ecp-btn");
    const msg   = widget.querySelector(".ecp-msg");

    async function submit() {
      const email = input.value.trim();
      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        msg.className = "ecp-msg error";
        msg.textContent = "Please enter a valid email address.";
        return;
      }

      btn.disabled    = true;
      btn.textContent = "Sending\u2026";
      msg.className   = "ecp-msg";
      msg.textContent = "";

      try {
        const res = await fetch(`${SERVER}/api/subscribe`, {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({
            email,
            website:      WEBSITE,
            file_name:    FILE,
            doc_link:     DOC_LINK     || null,
            spec_module:  SPEC_MODULE  || null,
            spec_version: SPEC_VERSION || null,
            spec_arch:    SPEC_ARCH    || null,
          }),
        });
        const data = await res.json();

        if (res.ok && data.success) {
          msg.className   = "ecp-msg success";
          msg.textContent = "\u2705 " + (data.message || "Check your email!");
          input.value     = "";
          btn.textContent = "Sent!";
        } else {
          throw new Error(data.detail || "Something went wrong.");
        }
      } catch (e) {
        msg.className   = "ecp-msg error";
        msg.textContent = "\u274C " + e.message;
        btn.disabled    = false;
        btn.textContent = BTN_LABEL;
      }
    }

    btn.addEventListener("click", submit);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
  }

  // ── Render ───────────────────────────────────────────────────────────────────
  function render() {
    if (POSITION === "inline") {
      const wrap = document.createElement("div");
      wrap.className = "ecp-inline";
      const w = buildWidget();
      wrap.appendChild(w);
      attachSubmit(w);
      SCRIPT.parentNode.insertBefore(wrap, SCRIPT.nextSibling);

    } else if (POSITION === "bottom-right" || POSITION === "bottom-left") {
      const w = buildWidget();
      w.classList.add("ecp-floating", POSITION);
      w.style.display = "none";

      const closeBtn = document.createElement("button");
      closeBtn.className   = "ecp-close";
      closeBtn.textContent = "\u00D7";
      closeBtn.onclick = () => { w.style.display = "none"; trigBtn.style.display = "flex"; };
      w.appendChild(closeBtn);

      const trigBtn = document.createElement("button");
      trigBtn.className   = `ecp-trigger-btn ${POSITION}`;
      trigBtn.textContent = "\uD83D\uDCC4 " + BTN_LABEL;
      trigBtn.onclick = () => { w.style.display = "block"; trigBtn.style.display = "none"; };

      attachSubmit(w);
      document.body.appendChild(w);
      document.body.appendChild(trigBtn);

    } else if (POSITION === "center-popup") {
      const overlay = document.createElement("div");
      overlay.className = "ecp-overlay";

      const w = buildWidget();
      const closeBtn = document.createElement("button");
      closeBtn.className   = "ecp-close";
      closeBtn.textContent = "\u00D7";
      closeBtn.onclick = () => overlay.classList.remove("active");
      w.appendChild(closeBtn);

      overlay.appendChild(w);
      overlay.onclick = (e) => { if (e.target === overlay) overlay.classList.remove("active"); };
      attachSubmit(w);
      document.body.appendChild(overlay);

      setTimeout(() => overlay.classList.add("active"), 2000);
      window.ECPlugin = { open: () => overlay.classList.add("active") };
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();