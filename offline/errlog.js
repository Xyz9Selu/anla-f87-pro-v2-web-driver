// 临时诊断: 把前端报错回传到本服务 /__log, 定位用户现场问题用完即删
(function () {
  function send(msg) {
    try {
      var s = typeof msg === "string" ? msg : String(msg && msg.stack || msg);
      s = new Date().toISOString() + " " + s;
      navigator.sendBeacon("/__log", s.slice(0, 2000));
    } catch (e) { /* ignore */ }
  }
  window.addEventListener("error", function (e) {
    send("[error] " + e.message + " @ " + (e.filename || "") + ":" + (e.lineno || 0));
  });
  window.addEventListener("unhandledrejection", function (e) {
    var r = e.reason;
    send("[unhandled] " + (r && (r.stack || r.message) || r));
  });
})();
