# Arabic Sprint （Vocabulary Speedrunner）

Arabic Sprint 是一個以 Docker 執行的阿拉伯文詞彙 speedrun 練習工具：畫面提供中文意思，使用者輸入阿拉伯文。它結合 Wiki 詞頻新字抽選、短期重練與 FSRS-4.5 長期複習，並使用 Ollama 本機或 Cloud 模型判斷非完全相同的答案。

For ([English Instructions](https://github.com/Leonard-9140/vocabulary-speedrunner/blob/main/README.en.md))

## 功能與頁面布局

- **中文提示、阿拉伯文作答**：輸入框和答案採 RTL 排版。
- **Ollama 模型選單**：保留 `gemma4:cloud`，並列出目前連線的 Ollama 服務已下載模型。模型清單約每 15 秒更新一次。
- **FSRS-4.5 排程**：根據記憶難度、穩定度、作答結果與距離上次複習時間安排長期複習。
- **speedrun 短期重練**：Again 題目會在完成其他三題後優先重現；沒有其他題目可作答時會提早重練。
- **速度評分**：正確答案依個人平均作答時間與標準差分類為 Easy、Good 或 Hard。
- **SQLite 持久化**：保存單字進度、FSRS 狀態與每次有效判分的作答時間。
- **Docker Compose 部署**：SQLite 放在具名 volume，容器提供 `/healthz` 健康檢查端點。

測驗開始後，桌面版頁面分為三欄：左欄上方顯示平均作答時間和標準差，下方顯示已作答單字最近一次 FSRS 評分的圓餅圖；中欄上方顯示題庫中已作答／未作答單字比例，作答卡片置中；右欄顯示本次測驗的 Ollama Cloud 請求數與 token 用量。窄螢幕會改為單欄排列。完成測驗時統計圖表仍會顯示。

平均時間和標準差使用速度評分的有效樣本，不含 Again 後的短期重練；FSRS 圓餅圖則以每個已作答單字的**最近一次評分**計數，每個單字只算一次。

> 用量表只統計本次 GUI 測驗由 `gemma4:cloud` 回報的請求和 token，不代表 Ollama 帳戶方案、帳戶總用量或剩餘額度。精確答案會在本機比對，不呼叫模型。使用 Cloud 判斷答案時，題目中文、標準阿拉伯文與使用者答案會送至 Ollama Cloud 處理。

## 初次啟動

### 1. 準備 Ollama

在執行 Docker 的電腦安裝並啟動 Ollama。使用 Cloud 模型時，先登入 Ollama；使用本機模型時，先下載模型，例如：

```bash
ollama signin
ollama pull gemma4:e4b
ollama pull gemma4:cloud
```

預設模型是 `gemma4:cloud`。測驗頁右上角可以切換到 Ollama 服務中已下載的本機模型。Docker 容器會透過 `OLLAMA_API_ENDPOINT` 連線到該 Ollama 服務。

### 2. 啟動 Docker Compose

在專案目錄執行：

```bash
docker compose up -d --build
```

瀏覽器開啟 <http://localhost:5000>，按「開始測驗」即可使用專案內附題庫。查看容器輸出：

```bash
docker compose logs -f
```

停止服務：

```bash
docker compose down
```

若修改程式、樣式、頁面或 CSV，重新建置並啟動：

```bash
docker compose up -d --build
```

本專案以 Docker 作為使用與部署方式；Docker 映像不包含 Ollama 模型或 Ollama 服務本身。

## 題庫與詞頻資料

第一次使用不需要自行下載語料或執行資料清洗。Docker 映像已包含：

- `exam_list.csv`：預設 234 個練習單字。
- `voc_database.csv`：預先整理的阿拉伯語詞頻資料，目前約 2,552 筆。

自訂題庫時，編輯專案根目錄的 `exam_list.csv`，使用 UTF-8 編碼並保留以下欄位，再重建容器：

```csv
arabic_word,translation
كتاب,書本
سيارة,汽車
بيت,房子
```

新字抽選時，程式只用題庫中**有詞頻資料的單字**計算百分位權重，範圍為 `0.5` 至 `1.5`。未收錄詞不會被視為最低頻詞，而是使用中間權重 `1.0`；頁面會標示「詞頻未知」。單字開始作答後，後續複習由 FSRS 安排，詞頻不會更改 FSRS 間隔。

## 判分與複習方式

### 答案判定

1. 答案與標準答案完全相同時直接判為正確，不呼叫模型。
2. 答案不一致時，程式忽略阿拉伯文附加符號，計算兩答案共有的阿拉伯字母數；重複字母按出現次數計。共有至少三個字母時，模型會先判斷是否為同一詞的單複數變化。確認後視為正確。
3. 其他答案由模型依詞意遠近分類：意思接近但不符合標準答案為 `Hard (2)`；意思不相關或錯誤為 `Again (1)`。近義詞或相關詞不會自動視為正確。

### Easy、Good、Hard 的速度評分

每題從顯示到送出答案都會記錄作答秒數。只有正確答案會依個人速度分類：

- 低於平均作答時間一個標準差以上：`Easy (4)`。
- 位於平均值正負一個標準差內：`Good (3)`。
- 高於平均作答時間一個標準差以上：`Hard (2)`。

平均值和樣本標準差使用該使用者先前的有效作答時間；至少要有兩筆資料才啟用速度分類。資料不足時正確答案記為 Good。模型判定的語意 Hard 不會被速度覆寫。短期重練仍記錄時間，但不納入速度基準，也不會因為剛看過答案而判為 Easy。

### 短期重練與 FSRS-4.5

Again 題目會進入持久化短期重練列，完成其他三題後優先重現；再次答錯會重新排入。沒有其他可答題時會提早重練，避免小題庫卡住。短期重練答對後移出重練列，再依 FSRS 長期間隔複習。FSRS 主排程最短間隔仍是一整天；短期重練列是 speedrun 使用的額外流程。

長期排程依照指定版本的 [FSRS-4.5 演算法](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm/bc401d9ed5093c66358738f4b8834f8d24ab211b)，計算記憶難度 `D`、穩定度 `S` 和可回憶率 `R`。程式使用該頁列出的 FSRS-4 預設權重與 FSRS-4.5 遺忘曲線：

```text
R(t,S) = (1 + 19/81 × t/S)^(-0.5)
```

FSRS 評分為 `Again (1)`、`Hard (2)`、`Good (3)`、`Easy (4)`。排程先出已到期短期重練，再出 FSRS 到期複習；沒有到期卡片時才抽新字。到期複習依預測可回憶率由低至高挑選。間隔以天計算、四捨五入為整天，預設最短一天、最長 36,500 天，不加隨機間隔擾動。

測驗中的「暫停測驗」會凍結目前題目計時；恢復後從暫停前的累計時間繼續。模型批改等待時間不計入作答時間。

## 資料保存與重設

每個瀏覽器首次使用會取得匿名學習識別碼，放在簽章 Cookie 中；Cookie 預設有效一年。不同瀏覽器或清除 Cookie 後會建立新的學習檔案，沒有帳號或跨裝置同步功能。

SQLite 會保存：

- 每個單字的答對／答錯次數、最近作答時間、FSRS 難度與穩定度、下次到期時間和目前評分。
- 每次有效判分的評分、作答秒數及時間統計是否採用。
- Again 短期重練的進度。

Docker Compose 將資料庫放在 `quiz_progress_data` 具名 volume。`docker compose down` 不會刪除學習資料；**不要執行 `docker compose down -v`，除非要刪除該 volume 和所有學習紀錄**。頁面上的「清除學習紀錄」會刪除目前瀏覽器識別碼對應的進度與作答時間歷史。SQLite 檔案和暫存檔已排除於 Git 與 Docker build context。

SQLite 設定適合單機、單一應用實例。既有資料庫會在應用啟動時自動增加所需欄位；舊紀錄沒有作答時間，因此無法還原舊的速度基準。若移除 Cookie，舊識別碼的資料仍留在 volume 中，但頁面無法自動找回該識別碼。

## 設定

Compose 會讀取專案根目錄 `.env`。一般本機開發可不建立 `.env`，直接使用 `compose.yaml` 的開發預設。部署環境可複製範本：

```bash
cp .env.example .env
```

範本使用 `APP_ENV=production`；啟動前必須設定至少 32 字元的 `FLASK_SECRET_KEY`，並將 `OLLAMA_API_ENDPOINT` 設為容器可連線的 Ollama `/api/chat` 位址。不要在雲端部署設定中使用 `host.docker.internal`。

| 變數 | 預設值 | 說明 |
|---|---|---|
| `OLLAMA_MODEL` | `gemma4:cloud` | 預設批改模型；頁面可以切換模型。 |
| `OLLAMA_API_ENDPOINT` | `http://host.docker.internal:11434/api/chat` | 容器連線到的 Ollama API 位址。 |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `10` | 建立 Ollama 連線的等待秒數。 |
| `OLLAMA_READ_TIMEOUT_SECONDS` | `600` | 等待模型回應的秒數；慢速模型可調高。 |
| `OLLAMA_KEEP_ALIVE` | `30m` | Ollama 保留已載入模型的時間。 |
| `FSRS_DESIRED_RETENTION` | `0.9` | FSRS 目標保留率，必須大於 0 且小於 1。 |
| `FSRS_MAXIMUM_INTERVAL_DAYS` | `36500` | FSRS 長期複習間隔上限（天）。 |
| `DATABASE_PATH` | `/data/quiz_progress.sqlite3`（Compose） | SQLite 學習紀錄資料庫位置。 |
| `SESSION_LIFETIME_DAYS` | `365` | 匿名學習識別 Cookie 的有效天數。 |
| `APP_ENV` | `development`（Compose） | 生產環境設為 `production`。 |
| `FLASK_SECRET_KEY` | 空白 | 生產環境必填，至少 32 字元。 |

使用 Docker 產生密鑰：

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"
```

修改 `.env` 後重建容器：

```bash
docker compose up -d --build
```

## 常見問題

- **頁面無法連到 Ollama**：確認 Ollama 正在執行，且 `OLLAMA_API_ENDPOINT` 是從容器內可連線的位址。雲端部署不能使用 `host.docker.internal`。
- **模型回應超時**：預設等待 600 秒，可在 `.env` 調高 `OLLAMA_READ_TIMEOUT_SECONDS`，然後重建容器。
- **模型選單沒有列出本機模型**：清單來自 `OLLAMA_API_ENDPOINT` 對應服務的 `/api/tags`。先確認該 Ollama 主機已下載模型，並等待最多約 15 秒讓清單快取更新。
- **舊版 `docker-compose` 重建容器出現錯誤**：建議安裝並使用 Docker Compose v2 的 `docker compose` 指令。
- **確認網頁服務狀態**：執行 `docker compose ps`；容器健康檢查路徑為 `/healthz`。查看詳細錯誤可用 `docker compose logs -f`。

## 專案檔案

| 檔案 | 用途 |
|---|---|
| `web_app.py` | Flask 頁面、抽題、評分、計時、統計與 SQLite 資料存取。 |
| `fsrs45.py` | FSRS-4.5 記憶狀態、遺忘曲線和間隔公式。 |
| `templates/index.html` | 測驗頁面與三欄儀表板結構。 |
| `static/style.css` | RTL 介面、桌面三欄布局和窄螢幕樣式。 |
| `static/app.js` | 作答送出時的批改等待提示。 |
| `exam_list.csv` | 預設中文提示與阿拉伯文答案。 |
| `voc_database.csv` | 新單字抽選用的已整理詞頻資料。 |
| `Dockerfile`, `compose.yaml` | Docker 映像、服務與持久化 volume 設定。 |
| `.env.example` | 生產部署環境變數範本。 |

## 參考資料

- Open Spaced Repetition. *The Algorithm: FSRS-4.5*（指定固定版本，含公式與預設權重）. [GitHub Wiki](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm/bc401d9ed5093c66358738f4b8834f8d24ab211b)
- Ye, J., Su, J., & Cao, Y. (2022). *A Stochastic Shortest Path Algorithm for Optimizing Spaced Repetition Scheduling*. KDD 2022. [DOI: 10.1145/3534678.3539081](https://doi.org/10.1145/3534678.3539081)
- Su, J., Ye, J., Nie, L., Cao, Y., & Chen, Y. (2023). *Optimizing Spaced Repetition Schedule by Capturing the Dynamics of Memory*. IEEE Transactions on Knowledge and Data Engineering, 35(10), 10085–10097. [DOI: 10.1109/TKDE.2023.3251721](https://doi.org/10.1109/TKDE.2023.3251721)
- 阿拉伯語詞頻原始資料： [Wikimedia Arabic Wikipedia dumps](https://dumps.wikimedia.org/arwiki/)。本專案附上已整理的 `voc_database.csv`，一般使用者無須下載 dump 或自行分析。
