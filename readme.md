# Arabic Sprint（Vocabulary Speedrunner）

以「看中文寫阿拉伯文」為方向的單字練習工具。網頁 GUI 支援阿拉伯文由右至左顯示、Ollama 本機或 Cloud 模型批改，並以詞頻權重和答題表現安排複習。

## 功能

- **中文提示、阿拉伯文作答**：輸入框和答案使用 RTL 排版，適合阿拉伯文閱讀與輸入。
- **切換批改模型**：頁面右上方可選 `gemma4:cloud` 或 `gemma4:e4b`。預設為 Cloud；切換模型不會重設當前測驗。
- **依答題表現抽題**：答錯的單字提高再次出現機率；每個單字答對達指定次數後即視為精通。
- **Cloud token 用量表**：測驗中顯示本次測驗由此 GUI 發出的 Cloud 請求數，以及 Ollama 回報的輸入、輸出和合計 tokens。若部分回應沒有 token 指標，頁面會標示統計不完整。
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
| `main_quiz.py` | 命令列版練習程式。 |

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

安裝並啟動 Ollama。登入帳號以使用 Cloud 模型；若要使用本機模型，請下載 E4B：

```bash
ollama signin
ollama run gemma4:cloud
ollama pull gemma4:e4b
```

只需準備 GUI 選用的模型。Cloud 模型需要可用的 Ollama 帳號；本機模型需要足夠的本機運算資源。

### 2. 使用 Docker Compose（建議）

在專案目錄執行：

```bash
docker compose up -d --build
```

瀏覽器開啟 <http://localhost:5000>。Compose 會將容器連到主機的 Ollama 服務（預設 `host.docker.internal:11434`）。若系統使用舊版 Compose，也可用 `docker-compose up -d --build`；遇到舊版 Compose 重建容器錯誤時，請改用 Docker Compose v2 的 `docker compose` 指令。

停止服務：

```bash
docker compose down
```

### 3. 本機 Python 開發

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

請勿將 `.env` 或真實密鑰提交到版本控制。生產環境也必須將 `OLLAMA_API_ENDPOINT` 設為部署服務可連線的 Ollama 位址；`host.docker.internal` 僅適用於本機 Docker 開發。

## 部署注意事項

建置映像：

```bash
docker build -t vocabulary-speedrunner:latest .
```

將映像部署到可執行容器的平台，將 HTTP 流量導向容器的 `5000` 連接埠，並設定 `APP_ENV=production`、`FLASK_SECRET_KEY` 與可連線的 `OLLAMA_API_ENDPOINT`。健康檢查路徑為 `/healthz`。映像不包含 Ollama 模型，也不提供 Ollama 服務；部署環境必須能連到已登入且可用的 Ollama Cloud 或自行管理的 Ollama 主機。避免將未受保護的 Ollama API 暴露至公網。

## 命令列版

`main_quiz.py` 是獨立的終端機練習程式。網頁 GUI 與 Docker 使用 `web_app.py`；命令列版目前使用程式內設定的 Ollama 位址和模型。
