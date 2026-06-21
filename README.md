# 每日時事統整網頁

每天台灣時間 **08:30** 自動更新的時事儀表板，聚焦 **金融 / AI科技 / 投資**，並分 **國際 / 台灣**。每則新聞附**原文來源連結**、由 **Gemini** 生成的繁中摘要與一句**洞察 (insight)**，並可用**收藏**功能標記有興趣的時事（存在瀏覽器本機）。

零後端、零維運成本：靜態前端放 GitHub Pages，更新由 GitHub Actions cron 自動跑。

## 功能

- 分類（金融／AI科技／投資）＋ 地區（國際／台灣）下拉篩選
- 每則附具公信力來源連結（Reuters/CNBC、中央社、鉅亨網、iThome、TechCrunch…）
- Gemini 自動生成摘要 + 洞察
- ★ 收藏功能（localStorage，免登入；新聞輪替後收藏仍保留）
- 每日 08:30（台灣）自動更新

## 專案結構

```
├─ index.html              # 主頁面
├─ assets/app.js · style.css
├─ data/latest.json        # 前端讀取的最新資料（+ 每日歸檔）
├─ scripts/
│   ├─ update_news.py      # 抓 RSS → Gemini → 輸出 JSON
│   ├─ sources.py          # RSS 來源清單
│   └─ requirements.txt
└─ .github/workflows/update.yml   # 每日 cron + 自動 commit
```

## 部署步驟（一次性設定）

1. **建立 public GitHub repo**（公開 repo 才能免費用 Pages），把本專案推上去。
2. **取得 Gemini API key**：到 [Google AI Studio](https://aistudio.google.com/app/apikey) 申請。
3. **設定 Secret**：Repo → Settings → Secrets and variables → Actions → New repository secret，
   名稱 `GEMINI_API_KEY`，值貼上你的 key。
4. **啟用 Pages**：Repo → Settings → Pages → Source 選 `Deploy from a branch`，
   分支選預設分支（如 `main`）、資料夾選 `/ (root)`。
5. **驗證**：Repo → Actions → `Daily News Update` → `Run workflow` 手動觸發一次，
   綠燈後開啟 Pages 網址確認內容。之後每天 08:30（台灣）自動更新。

> 注意：GitHub cron 以 UTC 計時（已設 `30 0 * * *` = 台灣 08:30），尖峰時段可能延遲數分鐘，屬正常現象。

## 本機開發 / 測試

預覽前端（需放一份 `data/latest.json`，repo 內已附示範資料）：

```bash
python -m http.server 8000
# 開 http://localhost:8000
```

本機跑更新腳本（Windows PowerShell）：

```powershell
pip install -r scripts/requirements.txt
$env:GEMINI_API_KEY = "你的key"
python scripts/update_news.py
```

完成後檢查 `data/latest.json` 是否每則都有 `summary` 與 `insight`。

## 自訂

- **新增/替換新聞來源**：編輯 [`scripts/sources.py`](scripts/sources.py)，每筆標註 `category` 與 `region`。RSS 失效時直接換 `url`。
- **每桶新聞數量**：調整 `sources.py` 的 `MAX_PER_BUCKET`。
- **Gemini 模型**：預設 `gemini-2.5-flash`，可用環境變數 `GEMINI_MODEL` 覆寫。

## 成本

Gemini `gemini-2.5-flash` 每天數十則摘要，用量極小、通常落在免費額度內。
