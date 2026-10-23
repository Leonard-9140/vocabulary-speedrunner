# Arabic Sprint（原Vocabulary Speedrunner）

以「以中文語意聯想阿拉伯文詞彙」為方向的單字練習工具。網頁GUI支援阿拉伯文由右至左顯示、Ollama本機或Cloud模型批改，可在隱私與速度間靈活切換，並以詞頻權重和答題表現安排複習。

## 功能

- **中文提示、阿拉伯文作答**：輸入框和答案使用RTL排版，適合阿拉伯文閱讀與輸入。
- **自動列出可用模型**：模型選單保留 `gemma4:cloud`，並自動列出目前連線的 Ollama 服務已下載模型；新增或移除模型後，等待最多約 15 秒再重新整理即可更新。
- **依答題表現抽題**：答錯的單字提高再次出現機率；每個單字答對達指定次數後即視為精通。
- **Cloud token 用量表**：測驗中顯示本次測驗由此GUI發出的Cloud請求數，以及Ollama回報的輸入、輸出和合計tokens。
- **Docker 部署**：提供 Dockerfile、Compose 設定與健康檢查端點 `/healthz`。

> 用量表只統計本次 GUI 測驗的 Cloud 請求，不代表 Ollama 帳戶方案、帳戶總用量或剩餘額度。Ollama 的回應用量指標是單次請求的 token 數；本專案不會讀取或推算帳戶餘額。精確答案比對會在本機直接判定，不呼叫模型，也不計入 Cloud 用量。

## 專案檔案

| 檔案 | 用途 |
|---|---|
| `web_app.py` | Flask 網頁程式、題目流程、Ollama 批改及 token 用量累計。 |
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

## 啟動方式

### 1. 準備 Ollama

安裝並啟動 Ollama。登入帳號以使用 Cloud 模型；若要使用本機模型，先用 `ollama pull` 下載，之後 GUI 會自動將它列入選單：

```bash
ollama signin
ollama pull gemma4:e4b
```

`gemma4:e4b` 是本機模型範例，可換成其他 Ollama 支援的模型名稱。Cloud 模型需登入 Ollama 帳號；本機模型需要足夠的本機運算資源。

GUI 會向 `OLLAMA_API_ENDPOINT` 所指向的 Ollama 服務查詢已下載模型清單（`/api/tags`），約每 15 秒更新一次快取。Docker 部署時，清單來自容器連線到的 Ollama 主機；請在那台主機下載所需模型。選單也會保留 `gemma4:cloud` 和環境設定的預設模型；若 Ollama 無法連線，則無法列出其他已下載模型。

### 2-1. 使用Docker Compose（較為簡易，建議使用本方法。不限平台）

在專案目錄執行：

```bash
docker compose up -d --build
```

瀏覽器開啟 <http://localhost:5000>。Compose 會將容器連到主機的 Ollama 服務（預設 `host.docker.internal:11434`）。若系統使用舊版 Compose，也可用 `docker-compose up -d --build`；遇到舊版 Compose 重建容器錯誤時，請改用 Docker Compose v2 的 `docker compose` 指令。

停止服務：

```bash
docker compose down
```

### 2-2. 不使用Docker啟動網頁GUI（與2-1擇一使用，與Windows系統相容性未知，建議使用Linux/MacOS）

這是 Docker Compose 以外的啟動方式：以下指令會在本機啟動網頁服務，之後仍然透過瀏覽器使用 GUI；它不是終端機測驗模式。一般使用已部署的網站或 Docker 版時，不需要執行本節。

需要 Python 3.10 以上版本。建立虛擬環境並安裝依賴：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

在 Linux/macOS 上，設定 Ollama 位址並啟動：

```bash
export OLLAMA_API_ENDPOINT=http://localhost:11434/api/chat
python web_app.py
```

瀏覽器開啟 <http://localhost:5000>。Windows PowerShell 可用 `$env:OLLAMA_API_ENDPOINT="http://localhost:11434/api/chat"` 設定該變數。

## 使用頁面

1. 按「開始測驗」。
2. 根據中文提示輸入阿拉伯文。
3. 頁面會先直接比對答案；需要語意判斷時才呼叫目前選用的 Ollama 模型。
4. 查看批改結果和 Cloud token 用量。若選用本機 E4B，Cloud 用量表不會因本機請求增加。
5. 按「下一題」繼續；可在右上角切換模型，或重新開始本次測驗。

測驗進度使用瀏覽器簽章 Cookie 保存，不需要額外資料庫。Cloud 模型會收到題目中文、目標阿拉伯文與使用者答案；使用 Cloud 即表示這些內容會送至 Ollama Cloud 處理。

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

將映像部署到可執行容器的平台，將 HTTP 流量導向容器的 `5000` 連接埠，並設定 `APP_ENV=production`、`FLASK_SECRET_KEY` 與可連線的 `OLLAMA_API_ENDPOINT`。健康檢查路徑為 `/healthz`。映像不包含 Ollama 模型，也不提供 Ollama 服務；部署環境必須能連到已登入且可用的 Ollama Cloud 或自行管理的 Ollama 主機。避免將未受保護的 Ollama API 暴露至公網。
