# Arabic Sprint (Vocabulary Speedrunner)

Arabic Sprint is an Arabic vocabulary speedrun practice tool that runs in Docker. The screen shows a Chinese meaning, and the user types the Arabic word. It combines new-word selection based on Wikipedia word frequency, short-term re-practice, and long-term FSRS-4.5 review, and it uses a local or cloud Ollama model to judge answers that are not an exact match.

For ([Chinese(Traditional) instructions](https://github.com/Leonard-9140/vocabulary-speedrunner/tree/main))

## Features and Page Layout

- **Chinese prompt, Arabic answer**: The input box and the answer use RTL layout.
- **Ollama model selector**: Keeps `gemma4:cloud` and lists the models already downloaded on the currently connected Ollama service. The model list refreshes about every 15 seconds.
- **FSRS-4.5 scheduling**: Schedules long-term review based on memory difficulty, stability, answer results, and the time since the last review.
- **Speedrun short-term re-practice**: Words rated Again reappear with priority after three other questions have been answered; if there are no other questions available, they are re-practiced early.
- **Speed-based rating**: Correct answers are classified as Easy, Good, or Hard according to the user's own average response time and standard deviation.
- **SQLite persistence**: Stores per-word progress, FSRS state, and the response time of every valid grading.
- **Docker Compose deployment**: SQLite lives in a named volume, and the container provides a `/healthz` health-check endpoint.

Once a quiz starts, the desktop page is divided into three columns. The left column shows the average response time and standard deviation at the top, and below it a pie chart of the most recent FSRS rating for each word answered so far. The middle column shows the ratio of answered to unanswered words in the question bank at the top, with the answer card centered below it. The right column shows the number of Ollama Cloud requests and the token usage for the current quiz. On narrow screens the layout switches to a single column. The statistics charts are still displayed when the quiz is finished.

The average time and standard deviation use the valid samples from speed-based rating and exclude short-term re-practice after an Again. The FSRS pie chart counts each answered word by its **most recent rating**, so each word is counted only once.

> The usage panel only counts the requests and tokens reported by `gemma4:cloud` during the current GUI quiz. It does not represent your Ollama account plan, total account usage, or remaining quota. Exact-match answers are compared locally without calling the model. When Cloud is used to judge an answer, the Chinese prompt, the standard Arabic word, and the user's answer are sent to Ollama Cloud for processing.

## First-Time Setup

### 1. Prepare Ollama

Install and start Ollama on the machine that runs Docker. To use a Cloud model, sign in to Ollama first; to use a local model, pull it first, for example:

```bash
ollama signin
ollama pull gemma4:e4b
ollama pull gemma4:cloud
```

The default model is `gemma4:cloud`. In the upper-right corner of the quiz page you can switch to any local model already downloaded in the Ollama service. The Docker container connects to that Ollama service through `OLLAMA_API_ENDPOINT`.

### 2. Start Docker Compose

Run the following in the project directory:

```bash
docker compose up -d --build
```

Open <http://localhost:5000> in your browser and click "Start Quiz" to use the bundled question bank. To view the container output:

```bash
docker compose logs -f
```

To stop the service:

```bash
docker compose down
```

If you modify the code, styles, pages, or CSV files, rebuild and start again:

```bash
docker compose up -d --build
```

This project uses Docker as its method of use and deployment. The Docker image does not include Ollama models or the Ollama service itself.

## Question Bank and Word-Frequency Data

On first use you do not need to download any corpus or run any data cleaning. The Docker image already includes:

- `exam_list.csv`: 234 default practice words.
- `voc_database.csv`: Pre-processed Arabic word-frequency data, currently about 2,552 entries.

To customize the question bank, edit `exam_list.csv` in the project root, using UTF-8 encoding and keeping the following columns, then rebuild the container:

```csv
arabic_word,translation
كتاب,書本
سيارة,汽車
بيت,房子
```

When selecting new words, the program calculates percentile weights using only the words in the question bank that **have word-frequency data**, in the range `0.5` to `1.5`. Words not included in the frequency data are not treated as the lowest-frequency words; instead they receive the middle weight of `1.0`, and the page marks them as "frequency unknown". Once a word has been attempted, its subsequent review is scheduled by FSRS, and word frequency does not change the FSRS interval.

## Grading and Review

### Answer Judgment

1. If the answer is exactly identical to the standard answer, it is judged correct directly, without calling the model.
2. If the answer differs, the program ignores Arabic diacritics and counts the Arabic letters the two answers share; repeated letters are counted by number of occurrences. If they share at least three letters, the model first judges whether the answer is a singular/plural variation of the same word. Once confirmed, it is treated as correct.
3. All other answers are classified by the model according to how close their meaning is: an answer whose meaning is close but does not match the standard answer is `Hard (2)`; an answer whose meaning is unrelated or wrong is `Again (1)`. Synonyms or related words are not automatically treated as correct.

### Speed-Based Easy, Good, and Hard Ratings

For each question, the response time is recorded in seconds from the moment it is displayed until the answer is submitted. Only correct answers are classified by the user's personal speed:

- More than one standard deviation below the average response time: `Easy (4)`.
- Within plus or minus one standard deviation of the average: `Good (3)`.
- More than one standard deviation above the average response time: `Hard (2)`.

The average and sample standard deviation use the user's earlier valid response times; speed classification is enabled only when there are at least two data points. When data is insufficient, correct answers are recorded as Good. A semantic Hard determined by the model is not overridden by speed. Short-term re-practice still records the time, but it is not included in the speed baseline, and it will not be judged Easy just because the answer was recently seen.

### Short-Term Re-Practice and FSRS-4.5

Words rated Again enter a persisted short-term re-practice queue and reappear with priority after three other questions have been completed; answering wrong again puts them back in the queue. When there are no other answerable questions, they are re-practiced early so that a small question bank does not get stuck. After a correct answer in short-term re-practice, the word leaves the queue and is then reviewed at FSRS long-term intervals. The minimum interval of the main FSRS schedule is still one full day; the short-term re-practice queue is an additional flow used by the speedrun.

Long-term scheduling follows the pinned version of the [FSRS-4.5 algorithm](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm/bc401d9ed5093c66358738f4b8834f8d24ab211b) and computes memory difficulty `D`, stability `S`, and retrievability `R`. The program uses the FSRS-4 default weights listed on that page and the FSRS-4.5 forgetting curve:

```text
R(t,S) = (1 + 19/81 × t/S)^(-0.5)
```

FSRS ratings are `Again (1)`, `Hard (2)`, `Good (3)`, and `Easy (4)`. The scheduler serves due short-term re-practice first, then FSRS due reviews; new words are drawn only when no cards are due. Due reviews are picked in order of predicted retrievability, from lowest to highest. Intervals are computed in days and rounded to whole days, with a default minimum of one day and a maximum of 36,500 days, and no random interval fuzz is applied.

Using "Pause Quiz" during a quiz freezes the timer of the current question; after resuming, timing continues from the accumulated time before the pause. The time spent waiting for the model to grade is not counted toward response time.

## Data Storage and Reset

Each browser receives an anonymous learner ID on first use, stored in a signed cookie; the cookie is valid for one year by default. Different browsers, or clearing cookies, create a new learning profile; there are no accounts and no cross-device sync.

SQLite stores:

- For each word: the number of correct/incorrect answers, the most recent answer time, FSRS difficulty and stability, the next due time, and the current rating.
- For each valid grading: the rating, the response time in seconds, and whether it was used in the time statistics.
- The progress of Again short-term re-practice.

Docker Compose places the database in the `quiz_progress_data` named volume. `docker compose down` does not delete learning data; **do not run `docker compose down -v` unless you want to delete that volume and all learning records**. The "Clear Learning Records" button on the page deletes the progress and response-time history corresponding to the current browser's identifier. SQLite files and temporary files are excluded from Git and the Docker build context.

The SQLite configuration is suited to a single machine and a single application instance. Existing databases automatically gain the required columns when the application starts; because old records have no response times, the old speed baseline cannot be restored. If the cookie is removed, the data for the old identifier remains in the volume, but the page cannot automatically recover that identifier.

## Configuration

Compose reads the `.env` file in the project root. For ordinary local development you can skip creating `.env` and use the development defaults in `compose.yaml`. For deployment environments, copy the template:

```bash
cp .env.example .env
```

The template uses `APP_ENV=production`; before starting, you must set `FLASK_SECRET_KEY` to at least 32 characters, and set `OLLAMA_API_ENDPOINT` to an Ollama `/api/chat` address that the container can reach. Do not use `host.docker.internal` in cloud deployment settings.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `gemma4:cloud` | Default grading model; the model can be switched on the page. |
| `OLLAMA_API_ENDPOINT` | `http://host.docker.internal:11434/api/chat` | Ollama API address the container connects to. |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `10` | Seconds to wait when establishing the Ollama connection. |
| `OLLAMA_READ_TIMEOUT_SECONDS` | `600` | Seconds to wait for the model's response; increase for slow models. |
| `OLLAMA_KEEP_ALIVE` | `30m` | How long Ollama keeps the loaded model in memory. |
| `FSRS_DESIRED_RETENTION` | `0.9` | FSRS target retention; must be greater than 0 and less than 1. |
| `FSRS_MAXIMUM_INTERVAL_DAYS` | `36500` | Upper limit (in days) of the FSRS long-term review interval. |
| `DATABASE_PATH` | `/data/quiz_progress.sqlite3` (Compose) | Location of the SQLite learning-record database. |
| `SESSION_LIFETIME_DAYS` | `365` | Validity period (in days) of the anonymous learner-ID cookie. |
| `APP_ENV` | `development` (Compose) | Set to `production` in production environments. |
| `FLASK_SECRET_KEY` | empty | Required in production; at least 32 characters. |

Generate a secret key with Docker:

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"
```

After modifying `.env`, rebuild the container:

```bash
docker compose up -d --build
```

## FAQ

- **The page cannot connect to Ollama**: Confirm that Ollama is running and that `OLLAMA_API_ENDPOINT` is an address reachable from inside the container. Cloud deployments cannot use `host.docker.internal`.
- **The model response times out**: The default wait is 600 seconds. You can increase `OLLAMA_READ_TIMEOUT_SECONDS` in `.env` and then rebuild the container.
- **The model selector does not list local models**: The list comes from the `/api/tags` endpoint of the service at `OLLAMA_API_ENDPOINT`. First confirm that the Ollama host has downloaded models, and wait up to about 15 seconds for the list cache to refresh.
- **Errors when rebuilding with the old `docker-compose`**: We recommend installing and using the Docker Compose v2 `docker compose` command.
- **Checking the web service status**: Run `docker compose ps`; the container health-check path is `/healthz`. To see detailed errors, use `docker compose logs -f`.

## Project Files

| File | Purpose |
|---|---|
| `web_app.py` | Flask pages, question selection, grading, timing, statistics, and SQLite data access. |
| `fsrs45.py` | FSRS-4.5 memory state, forgetting curve, and interval formulas. |
| `templates/index.html` | Quiz page and three-column dashboard structure. |
| `static/style.css` | RTL interface, desktop three-column layout, and narrow-screen styles. |
| `static/app.js` | Grading wait indicator shown when an answer is submitted. |
| `exam_list.csv` | Default Chinese prompts and Arabic answers. |
| `voc_database.csv` | Pre-processed word-frequency data used for new-word selection. |
| `Dockerfile`, `compose.yaml` | Docker image, service, and persistent volume configuration. |
| `.env.example` | Environment variable template for production deployment. |

## References

- Open Spaced Repetition. *The Algorithm: FSRS-4.5* (pinned version, including formulas and default weights). [GitHub Wiki](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm/bc401d9ed5093c66358738f4b8834f8d24ab211b)
- Ye, J., Su, J., & Cao, Y. (2022). *A Stochastic Shortest Path Algorithm for Optimizing Spaced Repetition Scheduling*. KDD 2022. [DOI: 10.1145/3534678.3539081](https://doi.org/10.1145/3534678.3539081)
- Su, J., Ye, J., Nie, L., Cao, Y., & Chen, Y. (2023). *Optimizing Spaced Repetition Schedule by Capturing the Dynamics of Memory*. IEEE Transactions on Knowledge and Data Engineering, 35(10), 10085–10097. [DOI: 10.1109/TKDE.2023.3251721](https://doi.org/10.1109/TKDE.2023.3251721)
- Raw Arabic word-frequency data: [Wikimedia Arabic Wikipedia dumps](https://dumps.wikimedia.org/arwiki/). This project ships the processed `voc_database.csv`, so ordinary users do not need to download the dump or analyze it themselves.
