(function () {
  var items = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    items.forEach(function (el) { el.classList.add("in"); });
    return;
  }
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
        observer.unobserve(entry.target);
      }
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
  items.forEach(function (el) { observer.observe(el); });

  document.querySelectorAll(".nav-menu a").forEach(function (link) {
    link.addEventListener("click", function () { link.closest("details").removeAttribute("open"); });
  });
})();

(function () {
  var root = document.documentElement;
  var key = "arcfin-theme";
  var colors = { light: "#F2F2F7", dark: "#0A0A0F" };
  var metas = document.querySelectorAll('meta[name="theme-color"]');
  var defaults = Array.prototype.map.call(metas, function (m) { return m.getAttribute("content"); });

  function apply(choice) {
    if (choice === "light" || choice === "dark") {
      root.dataset.theme = choice;
    } else {
      delete root.dataset.theme;
      choice = "system";
    }
    metas.forEach(function (m, i) { m.setAttribute("content", colors[root.dataset.theme] || defaults[i]); });
    document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
      button.setAttribute("aria-checked", String(button.dataset.themeChoice === choice));
    });
  }

  apply(root.dataset.theme);

  document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
    button.addEventListener("click", function () {
      var choice = button.dataset.themeChoice;
      apply(choice);
      try {
        if (choice === "system") localStorage.removeItem(key); else localStorage.setItem(key, choice);
      } catch (e) {}
      button.closest("details").removeAttribute("open");
    });
  });

  document.addEventListener("click", function (event) {
    document.querySelectorAll(".theme-menu[open], .nav-menu[open]").forEach(function (menu) {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".theme-menu[open], .nav-menu[open]").forEach(function (menu) {
      menu.removeAttribute("open");
      menu.querySelector("summary").focus();
    });
  });
})();

(function () {
  var notice = document.querySelector(".cookie-notice");
  var key = "arcfin-cookies";
  var seen = false;
  try { seen = localStorage.getItem(key) === "ok"; } catch (e) {}
  if (!notice || seen) return;
  notice.hidden = false;
  notice.querySelector("[data-cookie-ok]").addEventListener("click", function () {
    try { localStorage.setItem(key, "ok"); } catch (e) {}
    notice.hidden = true;
    document.dispatchEvent(new Event("arcfin:notice-closed"));
  });
})();

(function () {
  var root = document.documentElement;
  var key = "arcfin-lang";
  var languages = {
    "en": ["", "This site is also available in English.", "View in English", "Close"],
    "de": ["de", "Diese Website gibt es auch auf Deutsch.", "Auf Deutsch ansehen", "Schließen"],
    "es": ["es", "Este sitio también está disponible en español.", "Ver en español", "Cerrar"],
    "fr": ["fr", "Ce site est aussi disponible en français.", "Voir en français", "Fermer"],
    "it": ["it", "Questo sito è disponibile anche in italiano.", "Vedi in italiano", "Chiudi"],
    "nl": ["nl", "Deze website is ook beschikbaar in het Nederlands.", "Bekijk in het Nederlands", "Sluiten"],
    "pt-BR": ["pt-br", "Este site também está disponível em português.", "Ver em português", "Fechar"],
    "ru": ["ru", "Этот сайт также доступен на русском.", "Открыть на русском", "Закрыть"],
    "ja": ["ja", "このサイトは日本語でもご覧いただけます。", "日本語で見る", "閉じる"],
    "ko": ["ko", "이 사이트는 한국어로도 볼 수 있습니다.", "한국어로 보기", "닫기"],
    "zh-Hans": ["zh-hans", "本网站也提供简体中文版本。", "查看简体中文版", "关闭"]
  };
  var translated = ["", "roadmap", "support", "contribute", "changelog"];
  var current;

  function remember(code) { try { localStorage.setItem(key, code); } catch (e) {} }
  function stored() { try { return localStorage.getItem(key); } catch (e) { return null; } }

  function match(tag) {
    tag = String(tag || "").toLowerCase();
    if (/^zh-(hans|cn|sg)|^zh$/.test(tag)) return "zh-Hans";
    if (/^pt/.test(tag)) return "pt-BR";
    var base = tag.split("-")[0];
    return languages[base] && base !== "zh" ? base : null;
  }

  function pathFor(code) {
    var parts = location.pathname.split("/").filter(Boolean);
    var folders = Object.keys(languages).map(function (c) { return languages[c][0]; });
    if (parts.length && folders.indexOf(parts[0]) > 0) parts.shift();
    var slug = parts.join("/");
    if (translated.indexOf(slug) < 0) slug = "";
    var folder = languages[code][0];
    return "/" + [folder, slug].filter(Boolean).join("/") + (folder || slug ? "/" : "") + location.hash;
  }

  current = match(root.lang) || "en";

  document.querySelectorAll(".lang-sheet a[data-lang]").forEach(function (link) {
    link.addEventListener("click", function () { remember(link.dataset.lang); });
  });

  if (current !== "en") {
    var formats = {
      day: new Intl.DateTimeFormat(root.lang, { dateStyle: "long", timeZone: "UTC" }),
      month: new Intl.DateTimeFormat(root.lang, { year: "numeric", month: "long", timeZone: "UTC" })
    };
    document.querySelectorAll("main time[datetime]").forEach(function (time) {
      var value = time.getAttribute("datetime");
      var kind = time.dataset.date || (value.length > 7 ? "day" : "month");
      var date = new Date((value.length > 7 ? value : value + "-01") + "T12:00:00Z");
      if (!isNaN(date)) time.textContent = formats[kind].format(date);
    });
  }

  var preferred = stored();
  if (!preferred) {
    var wanted = navigator.languages || [navigator.language];
    for (var i = 0; i < wanted.length && !preferred; i++) preferred = match(wanted[i]);
  }
  if (!preferred || preferred === current || !languages[preferred]) return;

  var info = languages[preferred];
  var banner = document.createElement("div");
  banner.className = "lang-banner";
  banner.setAttribute("role", "region");
  banner.setAttribute("lang", preferred);
  banner.setAttribute("aria-label", info[2]);
  var text = document.createElement("span");
  text.textContent = info[1];
  var go = document.createElement("a");
  go.className = "btn btn-primary";
  go.href = pathFor(preferred);
  go.textContent = info[2];
  go.addEventListener("click", function () { remember(preferred); });
  var close = document.createElement("button");
  close.type = "button";
  close.className = "close";
  close.setAttribute("aria-label", info[3]);
  close.textContent = "×";
  close.addEventListener("click", function () { remember(current); banner.remove(); });
  banner.append(text, go, close);
  if (document.querySelector(".cookie-notice:not([hidden])")) {
    document.addEventListener("arcfin:notice-closed", function () { document.body.appendChild(banner); }, { once: true });
  } else {
    document.body.appendChild(banner);
  }
})();

(function () {
  document.querySelectorAll(".doc-toc").forEach(function (toc) {
    var doc = toc.closest(".doc");
    var headings = Array.prototype.slice.call(doc.querySelectorAll("h2"));
    if (!headings.length) return;
    var list = document.createElement("ul");
    var links = headings.map(function (heading, index) {
      var target = heading.id ? heading : (heading.closest("section[id]") || heading);
      if (!target.id) target.id = "section-" + (index + 1);
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = "#" + target.id;
      link.textContent = heading.textContent.trim();
      item.appendChild(link);
      list.appendChild(item);
      return { link: link, heading: heading };
    });
    toc.appendChild(list);

    var ticking = false;
    function update() {
      ticking = false;
      var current = links[0];
      links.forEach(function (entry) {
        if (entry.heading.getBoundingClientRect().top < 140) current = entry;
      });
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) current = links[links.length - 1];
      links.forEach(function (entry) { entry.link.setAttribute("aria-current", String(entry === current)); });
    }
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    update();
  });
})();

(function () {
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll("[data-device-toggle]").forEach(function (toggle) {
    var switcher = toggle.querySelector(".device-switch");
    var buttons = Array.prototype.slice.call(switcher.querySelectorAll("button"));
    var panels = toggle.querySelectorAll(".device-panel");
    var current = 0;
    var chosen = false;
    var visible = false;
    var held = false;

    function show(index) {
      current = index;
      var device = buttons[index].dataset.device;
      panels.forEach(function (panel) {
        var on = panel.dataset.device === device;
        panel.hidden = !on;
        panel.setAttribute("aria-hidden", String(!on));
      });
      buttons.forEach(function (button, i) { button.setAttribute("aria-pressed", String(i === index)); });
    }

    buttons.forEach(function (button, i) {
      button.addEventListener("click", function () { chosen = true; show(i); });
    });
    toggle.addEventListener("mouseenter", function () { held = true; });
    toggle.addEventListener("mouseleave", function () { held = false; });
    toggle.addEventListener("focusin", function () { held = true; });
    toggle.addEventListener("focusout", function () { held = false; });

    switcher.hidden = false;
    toggle.classList.add("ready");
    show(0);

    // Steps through the devices while the feature is on screen, until someone picks one.
    if (still || buttons.length < 2) return;
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
      }, { threshold: 0.4 }).observe(toggle);
    } else {
      visible = true;
    }
    setInterval(function () {
      if (!chosen && visible && !held && !document.hidden) show((current + 1) % buttons.length);
    }, 4000);
  });
})();
