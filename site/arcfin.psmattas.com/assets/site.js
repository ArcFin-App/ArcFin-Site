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
