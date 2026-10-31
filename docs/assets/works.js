/*
 * 作業清單：入口網頁與每份作業頁面的「上一份／下一份」都從這裡讀資料。
 *
 * 新增作業：照時間順序（舊的在前、新的在後）加一筆即可。
 *   id       資料夾名稱，也是網址的一部分（docs/<id>/index.html）
 *   label    顯示在標題上方的短名稱，例如 HW5、Week8
 *   title    作業名稱
 *   summary  一兩句話說明這份作業在做什麼
 *   tags     技術關鍵字，會用「、」連起來顯示
 *   lane     1–6，決定這份作業的代表色（超過 6 會輪流使用）
 *   path     作業頁面的相對路徑
 *   source   GitHub 上的原始碼位置
 *   external 作業日後獨立成自己的專案與網頁時，填入新網址；入口頁就會改跳到那裡。沒有就留 null。
 */
window.SITE = {
  repo: "https://github.com/smashcldew/_se",
  repoName: "smashcldew/_se"
};

window.WORKS = [
  {
    id: "hw1",
    label: "HW1",
    title: "MiniCurl",
    summary: "用 Go 寫的迷你 curl：可指定請求方法、標頭、Cookie 與 Basic Auth，也能同時請求多個網址。",
    tags: ["Go", "命令列", "HTTP", "goroutine"],
    lane: 1,
    path: "hw1/",
    source: "https://github.com/smashcldew/_se/tree/main/HW1",
    external: null
  },
  {
    id: "hw2",
    label: "HW2",
    title: "校務系統",
    summary: "管理員、行政、學生、老師四種角色登入，處理選課、請假與點名；37 項測試全數通過。",
    tags: ["Python", "SQLite", "HTML／CSS／JavaScript", "REST API"],
    lane: 2,
    path: "hw2/",
    source: "https://github.com/smashcldew/_se/tree/main/HW2",
    external: null
  },
  {
    id: "hw3",
    label: "HW3",
    title: "StockFollower",
    summary: "台股研究桌面程式：查個股、看 K 線與 KDJ，並列出成交量與漲跌幅排行。",
    tags: ["Python", "Tkinter", "SQLite", "證交所與櫃買中心資料"],
    lane: 3,
    path: "hw3/",
    source: "https://github.com/smashcldew/_se/tree/main/HW3",
    external: null
  },
  {
    id: "hw4",
    label: "HW4",
    title: "Git Flow 與 GitHub Flow",
    summary: "建立 dev 分支、合併回 main，再練習 fork 別人的倉庫並送出 pull request 的操作筆記。",
    tags: ["Git", "GitHub", "分支", "pull request"],
    lane: 4,
    path: "hw4/",
    source: "https://github.com/smashcldew/_se/tree/main/HW4",
    external: null
  },
  {
    id: "week6",
    label: "Week6",
    title: "Docker 微服務",
    summary: "用 Docker Compose 啟動 Nginx、Node.js、Python、Rust 與 PostgreSQL，網頁即時顯示各服務狀態。",
    tags: ["Docker", "Compose", "Nginx", "PostgreSQL"],
    lane: 5,
    path: "week6/",
    source: "https://github.com/smashcldew/_se/tree/main/Week6",
    external: null
  },
  {
    id: "week7",
    label: "Week7",
    title: "HW2 測試指南",
    summary: "替校務系統寫的單元、系統與瀏覽器端對端測試，共 37 項。",
    tags: ["unittest", "Playwright", "E2E", "Python"],
    lane: 6,
    path: "week7/",
    source: "https://github.com/smashcldew/_se/tree/main/Week7",
    external: null
  }
];
