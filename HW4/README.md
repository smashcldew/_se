# 第四週： git flow , github flow 的用法
母專案 https://github.com/smashcldew/_se/tree/main
母專案分支 https://github.com/smashcldew/_se/tree/dev
子專案 

1.
先在母專案資料夾(_se)使用 git bash here
指令 git checkout -b dev 建立分支
並切換至"dev"的分支
接著
git add -A
git commit "dev branch"
git push origin dev
把新增/修改的檔案推到dev這個分支
git checkout main
切回主分支,並且
2.
git merge dev
將主分支與dev分支合併

3.
fork需要在github上向別人的倉庫執行fork
複製一個到自己的倉庫

4.
pull request
需要在fork出去的專案執行:
git add -A
git commit "..."
git push
最後,在github上發出"compare&pull request"