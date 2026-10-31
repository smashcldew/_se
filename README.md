# 課程：現代軟體工程 -- 學生作業與專案

欄位 | 內容
-----|--------
學期 | 115 學年上學期
教師 | [陳鍾誠](https://www.nqu.edu.tw/educsie/index.php?act=blog&code=list&ids=4)
學校 | [金門大學資訊工程系](https://www.nqu.edu.tw/educsie/index.php)
學生 | 王柏元
學號 | 62

## 作業入口網頁

所有作業整理在同一個入口網頁，每份作業都有自己的頁面：<https://smashcldew.github.io/_se/>

網頁原始檔放在 `docs/`，用 GitHub Pages 發布（Settings → Pages → Branch 選 `main`、資料夾選 `/docs`）。

新增作業頁面：

1. 複製 `docs/assets/work-page.template.html` 到 `docs/<作業代號>/index.html`，改寫內容。
2. 在 `docs/assets/works.js` 加一筆資料，入口頁與「上一份／下一份」就會自動更新。
3. 作業日後獨立成自己的專案與網頁時，把那一筆的 `external` 改成新網址，入口頁就會改跳到那裡。
