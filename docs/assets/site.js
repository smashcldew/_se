/* 共用腳本：畫入口頁的作業清單、作業頁的上一份／下一份、程式碼複製按鈕。
   作業資料全部來自 works.js。 */
(function () {
  "use strict";

  var works = window.WORKS || [];
  var site = window.SITE || {};
  var base = document.body.getAttribute("data-base") || "";

  function hrefOf(w) {
    return w.external || base + w.path;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  /* 入口頁：新的作業排在上面，像 git log 一樣 */
  var rail = document.getElementById("rail");
  if (rail) {
    var head = el("li", "stop head");
    head.appendChild(el("span", "dot"));
    var repoLink = el("a", "repo-link", site.repoName || "母專案");
    repoLink.href = site.repo || "#";
    var headLine = el("p");
    headLine.appendChild(repoLink);
    head.appendChild(headLine);
    head.appendChild(el("p", "", "母專案。下面每一條分支，都是一份作業的獨立頁面。"));
    rail.appendChild(head);

    works.slice().reverse().forEach(function (w) {
      var li = el("li", "stop lane-" + (((w.lane - 1) % 6) + 1));
      li.appendChild(el("span", "dot"));
      li.appendChild(el("p", "label", w.label));

      var h2 = el("h2");
      var a = el("a", "", w.title);
      a.href = hrefOf(w);
      h2.appendChild(a);
      li.appendChild(h2);

      li.appendChild(el("p", "summary", w.summary));
      li.appendChild(el("p", "tags", (w.tags || []).join("、")));

      var links = el("p", "links");
      var src = el("a", "", "原始碼");
      src.href = w.source;
      links.appendChild(src);
      li.appendChild(links);

      rail.appendChild(li);
    });
  }

  /* 作業頁：上一份與下一份 */
  var nav = document.getElementById("work-nav");
  var current = document.body.getAttribute("data-work");
  if (nav && current) {
    var i = works.findIndex(function (w) { return w.id === current; });
    if (i > 0) {
      var prev = el("a", "prev");
      prev.href = hrefOf(works[i - 1]);
      prev.appendChild(el("small", "", "上一份"));
      prev.appendChild(el("span", "", works[i - 1].label + " " + works[i - 1].title));
      nav.appendChild(prev);
    }
    if (i >= 0 && i < works.length - 1) {
      var next = el("a", "next");
      next.href = hrefOf(works[i + 1]);
      next.appendChild(el("small", "", "下一份"));
      next.appendChild(el("span", "", works[i + 1].label + " " + works[i + 1].title));
      nav.appendChild(next);
    }
  }

  /* 程式碼區塊：複製按鈕 */
  document.querySelectorAll(".code").forEach(function (box) {
    var pre = box.querySelector("pre");
    if (!pre || !navigator.clipboard) return;
    var btn = el("button", "copy", "複製");
    btn.type = "button";
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(pre.innerText.replace(/\n$/, "")).then(function () {
        btn.textContent = "已複製";
        setTimeout(function () { btn.textContent = "複製"; }, 1600);
      }, function () {
        btn.textContent = "複製失敗";
        setTimeout(function () { btn.textContent = "複製"; }, 1600);
      });
    });
    box.appendChild(btn);
  });
})();
