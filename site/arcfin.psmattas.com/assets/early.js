(function (d) {
  d.classList.add("js");
  try {
    var t = localStorage.getItem("arcfin-theme");
    if (t === "light" || t === "dark") d.dataset.theme = t;
  } catch (e) {}
})(document.documentElement);
