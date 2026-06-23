/* Aurora Ink — 최소 vanilla JS (외부 의존 0)
   1) 다크/라이트 테마 토글 + 기억
   2) (선택) 인덱스 페이지 키워드 필터 — 있으면 동작, 없으면 무시 */
(function () {
  "use strict";
  var KEY = "aipw-theme";
  var root = document.documentElement;

  // 초기 테마 (head 인라인 스니펫이 이미 적용했을 수 있으나 안전망)
  try {
    var saved = localStorage.getItem(KEY);
    if (saved) root.setAttribute("data-theme", saved);
  } catch (e) {}

  function bindToggle() {
    var btn = document.getElementById("themeToggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(KEY, next); } catch (e) {}
    });
  }

  // 인덱스 페이지용 키워드 필터(진보적 향상): 칩 클릭 → 매칭 카드만 표시
  function bindFilter() {
    var bar = document.querySelector("[data-filter-bar]");
    if (!bar) return;
    var cards = Array.prototype.slice.call(document.querySelectorAll("[data-tags]"));
    bar.addEventListener("click", function (ev) {
      var chip = ev.target.closest("[data-tag]");
      if (!chip) return;
      var tag = chip.getAttribute("data-tag");
      var active = chip.classList.toggle("is-active");
      bar.querySelectorAll("[data-tag]").forEach(function (c) {
        if (c !== chip) c.classList.remove("is-active");
      });
      cards.forEach(function (card) {
        if (!active || tag === "*") { card.style.display = ""; return; }
        var tags = (card.getAttribute("data-tags") || "").toLowerCase();
        card.style.display = tags.indexOf(tag.toLowerCase()) !== -1 ? "" : "none";
      });
    });
  }

  if (document.readyState !== "loading") { bindToggle(); bindFilter(); }
  else document.addEventListener("DOMContentLoaded", function () { bindToggle(); bindFilter(); });
})();
