# Arabic Sprint（原Vocabulary Speedrunner）

以「以中文語意聯想阿拉伯文詞彙」為方向的單字練習工具。網頁GUI支援阿拉伯文由右至左顯示、Ollama本機或Cloud模型批改，可在隱私與速度間靈活切換，並以詞頻權重和答題表現安排複習。

## 功能

- **中文提示、阿拉伯文作答**：輸入框和答案使用RTL排版，適合阿拉伯文閱讀與輸入。
- **自動列出可用模型**：模型選單保留 `gemma4:cloud`，並自動列出目前連線的 Ollama 服務已下載模型；新增或移除模型後，等待最多約 15 秒再重新整理即可更新。
- **FSRS-4.5 間隔複習**：根據難度、記憶穩定度、距離上次作答時間和答題結果計算下次複習日。
- **Cloud token 用量表**：測驗中顯示本次測驗由此GUI發出的Cloud請求數，以及Ollama回報的輸入、輸出和合計tokens。
- **Docker 部署**：提供 Dockerfile、Compose 設定與健康檢查端點 `/healthz`。

> 用量表只統計本次 GUI 測驗的 Cloud 請求，不代表 Ollama 帳戶方案、帳戶總用量或剩餘額度。Ollama 的回應用量指標是單次請求的 token 數；本專案不會讀取或推算帳戶餘額。精確答案比對會在本機直接判定，不呼叫模型，也不計入 Cloud 用量。

## 專案檔案

| 檔案 | 用途 |
|---|---|
| `web_app.py` | Flask 網頁程式、題目流程、Ollama 批改及 token 用量累計。 |
| `fsrs45.py` | FSRS-4.5 記憶狀態、遺忘曲線和複習間隔計算。 |
| `templates/index.html` | 測驗頁面、模型選單和用量表。 |
| `static/` | GUI 樣式與瀏覽器端互動程式。 |
| `exam_list.csv` | 本次練習的阿拉伯文與中文對照表。 |
| `voc_database.csv` | 單字抽題使用的詞頻資料。 |
| `Dockerfile`, `compose.yaml` | 建置及執行容器。 |
| `.env.example` | Docker Compose 與部署環境變數範本。 |

## 初次使用

第一次使用不需要自行下載詞頻資料、執行分析或清洗腳本。專案已附上預先整理好的 `voc_database.csv`（目前 2,552 筆詞頻資料）和預設練習題庫 `exam_list.csv`（目前 234 個單字）。Docker映像已包含這兩個CSV檔案，使用者不須自行清洗資料。

首次啟動只需準備 Ollama，接著用Docker Compose建置並啟動網頁。瀏覽器進入 <http://localhost:5000> 後，按「開始測驗」即可使用內附題庫。

若要使用自己的單字表，請以 UTF-8 編碼編輯專案根目錄的 `exam_list.csv`，保留 `arabic_word,translation` 欄位，再執行 `docker compose up -d --build` 重新建置。單字頻率會從內附的 `voc_database.csv` 查找；新單字若不在其中，仍會以預設權重出題，不需要自行執行分析腳本。

## 單字表格式

`exam_list.csv` 使用 UTF-8 編碼，第一列為欄位名稱：

```csv
arabic_word,translation
كتاب,書本
سيارة,汽車
بيت,房子
```

`voc_database.csv` 提供詞頻權重。若題庫中的單字不在詞頻資料庫，程式會以預設權重納入練習。

## FSRS-4.5 複習排程

排程依照 [FSRS-4.5 演算法](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm/bc401d9ed5093c66358738f4b8834f8d24ab211b)計算記憶難度 `D`、穩定度 `S` 和可回憶率 `R`。程式使用該頁列出的 FSRS-4 權重組及 FSRS-4.5 遺忘曲線：`R(t,S) = (1 + 19/81 × t/S)^(-0.5)`，並反解目標保留率以決定下次間隔。

答案與標準答案完全相同時直接判定正確。不一致時，程式先忽略阿拉伯文附加符號並計算兩答案共有的阿拉伯字母數（重複字母按出現次數計）；共有至少三個字母時，才請模型判斷是否為同一詞的單複數變化，確認後視為正確。若不是可接受答案，模型再按詞意遠近分為 `Hard (2)`（意思接近但答案不合）或 `Again (1)`（詞意不相關或錯誤）。這是對答題結果的操作性分類，近義或相關詞不會自動當成正確答案。

每題從顯示到送出答案都會記錄作答秒數。對判定正確的答案，系統會以這位使用者先前已判分題目的平均時間和樣本標準差分類：低於平均值一個標準差以上為 `Easy (4)`；落在平均值正負一個標準差內為 `Good (3)`；高於平均值一個標準差以上為 `Hard (2)`。至少要有兩筆先前作答時間才啟用速度分類，資料不足時正確答案使用 `Good (3)`。語意接近但不符合標準答案的 `Hard (2)` 仍依模型分類，不會因作答快慢改成 Easy 或 Good。速度分類出的 Hard 雖作答較慢仍屬正確，會記入正確次數；模型判定的語意 Hard 會記為非標準答案。

新單字先依它在本次清單中的 Wiki 詞頻百分位排序抽選；開始作答後，排程改由 FSRS 記憶狀態決定，Wiki 詞頻不會改寫 FSRS 間隔。`Hard (2)` 會套用 FSRS 的 Hard 成功回憶公式，不增加遺忘次數；只有 `Again (1)` 才代表忘記。測驗頁面上的「暫停測驗」會凍結目前題目的計時；恢復後從暫停前的累計作答時間繼續。模型判分等待時間不列入作答時間。

如果已有到期複習，頁面優先出題給預測可回憶率最低的到期單字；若沒有到期項目，才抽取新單字。間隔以天計算、四捨五入為整天，最短 1 天，預設最長 36,500 天。這個版本不另加 FSRS 以外的短期學習步驟或隨機間隔擾動。

每次答題會將作答秒數和判定結果新增到 SQLite 作答歷史，並在單字進度中保存 `stability`、`difficulty`、預定到期時間、複習次數、遺忘次數及最近評分。清除學習紀錄時也會刪除該使用者的作答時間歷史。舊資料庫若已有最後作答時間和結果，啟動時會以最近一次二元結果建立初始 FSRS 狀態；舊紀錄沒有作答秒數，無法還原歷史速度。

### 參考資料

- Ye, J., Su, J., & Cao, Y. (2022). *A Stochastic Shortest Path Algorithm for Optimizing Spaced Repetition Scheduling*. KDD 2022. [DOI: 10.1145/3534678.3539081](https://doi.org/10.1145/3534678.3539081)
- Su, J., Ye, J., Nie, L., Cao, Y., & Chen, Y. (2023). *Optimizing Spaced Repetition Schedule by Capturing the Dynamics of Memory*. IEEE Transactions on Knowledge and Data Engineering, 35(10), 10085–10097. [DOI: 10.1109/TKDE.2023.3251721](https://doi.org/10.1109/TKDE.2023.3251721)
- Open Spaced Repetition. *The Algorithm: FSRS-4.5* (固定版本，含公式與預設權重). [GitHub Wiki](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm/bc401d9ed5093c66358738f4b8834f8d24ab211b)
- 阿拉伯語詞頻資料來源： [Wikimedia Arabic Wikipedia dumps](https://dumps.wikimedia.org/arwiki/)。本專案提供已整理的 `voc_database.csv`，一般使用者不需下載 dump 或自行分析。

## 啟動方式

### 1. 準備 Ollama

安裝並啟動 Ollama。登入帳號以使用 Cloud 模型；若要使用本機模型，先用 `ollama pull` 下載，之後 GUI 會自動將它列入選單：

```bash
ollama signin
ollama pull gemma4:e4b
```

`gemma4:e4b` 是本機模型範例，可換成其他 Ollama 支援的模型名稱。Cloud 模型需登入 Ollama 帳號；本機模型需要足夠的本機運算資源。

GUI 會向 `OLLAMA_API_ENDPOINT` 所指向的 Ollama 服務查詢已下載模型清單（`/api/tags`），約每 15 秒更新一次快取。Docker 部署時，清單來自容器連線到的 Ollama 主機；請在那台主機下載所需模型。選單也會保留 `gemma4:cloud` 和環境設定的預設模型；若 Ollama 無法連線，則無法列出其他已下載模型。

### 使用 Docker Compose

在專案目錄執行：

```bash
docker compose up -d --build
```

瀏覽器開啟 <http://localhost:5000>。Compose 會將容器連到主機的 Ollama 服務（預設 `host.docker.internal:11434`）。若系統使用舊版 Compose，也可用 `docker-compose up -d --build`；遇到舊版 Compose 重建容器錯誤時，請改用 Docker Compose v2 的 `docker compose` 指令。

停止服務：

```bash
docker compose down
```

## 使用頁面

1. 按「開始測驗」。
2. 根據中文提示輸入阿拉伯文。
3. 頁面會先直接比對答案；需要語意判斷時才呼叫目前選用的 Ollama 模型。
4. 查看批改結果和 Cloud token 用量。若選用本機 E4B，Cloud 用量表不會因本機請求增加。
5. 按「下一題」繼續；若目前沒有到期題目，頁面會顯示預計下一次複習時間。可在右上角切換模型。

答題次數、最後選取時間、最後作答時間、FSRS 記憶狀態及結果會保存到 SQLite。每個瀏覽器首次使用時會建立匿名學習識別碼；同一瀏覽器下次開啟可延續紀錄。清除瀏覽器 Cookie 會建立新的學習檔案，舊資料仍留在資料庫中。測驗畫面的「清除學習紀錄」會刪除此瀏覽器識別碼對應的資料。

Docker Compose 會將 SQLite 檔案存放在名為 `quiz_progress_data` 的具名 volume；一般執行 `docker compose down` 不會刪除它。請勿使用 `docker compose down -v`，除非要連同學習紀錄一起刪除。資料庫與 SQLite 暫存檔已加入 `.gitignore` 和 `.dockerignore`，不會同步到 Git 或打包進映像。部署到雲端時，需為 `/data` 掛載持久化磁碟，並維持 `FLASK_SECRET_KEY` 不變，才能在容器重建後沿用同一個瀏覽器識別碼。

目前 SQLite 適合單一應用實例。若要同時執行多個容器副本，應改用 PostgreSQL 等共用資料庫，而不是讓多個副本共用 SQLite 檔案。Cloud 模型會收到題目中文、目標阿拉伯文與使用者答案；使用 Cloud 即表示這些內容會送至 Ollama Cloud 處理。

## 設定

Compose 可透過專案根目錄的 `.env` 設定下列變數。可先複製範本：

```bash
cp .env.example .env
```

`.env.example` 是生產部署範本，預設 `APP_ENV=production`。啟動前必須填入 `FLASK_SECRET_KEY` 和可從容器連線的 `OLLAMA_API_ENDPOINT`。若只是本機測試，可刪除 `.env` 讓 Compose 使用開發預設，或將 `APP_ENV` 設為 `development` 並使用本機適用的 Ollama 位址。

| 變數 | 預設值 | 說明 |
|---|---|---|
| `OLLAMA_MODEL` | `gemma4:cloud` | 預設模型；頁面仍可切換到另一個已設定選項。 |
| `OLLAMA_API_ENDPOINT` | `http://host.docker.internal:11434/api/chat` | 容器可連線的 Ollama `/api/chat` 位址。 |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `10` | 建立 Ollama 連線的等待秒數。 |
| `OLLAMA_READ_TIMEOUT_SECONDS` | `600` | 等待模型完成回應的秒數。慢速本機模型可適度提高。 |
| `OLLAMA_KEEP_ALIVE` | `30m` | Ollama 保留已載入模型的時間。 |
| `FSRS_DESIRED_RETENTION` | `0.9` | FSRS 目標保留率；必須大於 0 且小於 1。 |
| `FSRS_MAXIMUM_INTERVAL_DAYS` | `36500` | FSRS 單次複習間隔上限（天）。 |
| `DATABASE_PATH` | `quiz_progress.sqlite3`（本機）／`/data/quiz_progress.sqlite3`（Compose） | SQLite 學習紀錄資料庫路徑。 |
| `SESSION_LIFETIME_DAYS` | `365` | 瀏覽器匿名學習識別碼 Cookie 的有效天數。 |
| `APP_ENV` | Compose 為 `development` | 生產環境請設為 `production`。 |
| `FLASK_SECRET_KEY` | 空白 | 生產環境必須設定至少 32 字元的隨機密鑰。 |

設定變更後重建容器：

```bash
docker compose up -d --build
```

產生密鑰：

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```
## 部署注意事項

建置映像：

```bash
docker build -t vocabulary-speedrunner:latest .
```

請將映像部署到可執行容器的平台，將 HTTP 流量導向容器的 `5000` 連接埠，並設定 `APP_ENV=production`、`FLASK_SECRET_KEY` 與可連線的 `OLLAMA_API_ENDPOINT`。健康檢查路徑為 `/healthz`。本映像不包含 Ollama 模型，也不提供 Ollama 服務；部署環境若須使用雲端模型必須自行連接已登入且可用的 Ollama Cloud 或自行管理的 Ollama 主機並且避免將未受保護的 Ollama API 暴露至公網。
