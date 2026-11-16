// The Apple TV's Quick Connect QR code links here with the code and the server in the
// fragment, which the browser keeps to itself. Shows the code and links to the server's own
// Quick Connect page.
(function () {
  var params = new URLSearchParams(location.hash.slice(1));
  var code = (params.get("code") || "").replace(/\D/g, "");
  if (code) {
    var el = document.getElementById("qc-code");
    el.textContent = code.length === 6 ? code.slice(0, 3) + " " + code.slice(3) : code;
    el.hidden = false;
  }
  var server;
  try { server = new URL(params.get("server") || ""); } catch (e) { server = null; }
  if (server && (server.protocol === "https:" || server.protocol === "http:")) {
    var link = document.getElementById("qc-server");
    link.href = server.href.replace(/\/+$/, "") + "/web/#/quickconnect";
    link.hidden = false;
  }
})();
