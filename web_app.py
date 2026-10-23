"""Browser based Arabic vocabulary quiz."""

import csv
from collections import Counter
from contextlib import contextmanager
import os
import random
import re
import sqlite3
import statistics
import time
import unicodedata
import uuid
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

import requests
from flask import Flask, flash, redirect, render_template, request, session, url_for
import fsrs45

app = Flask(__name__)
APP_ENV = os.environ.get("APP_ENV", "development").lower()
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
if not SECRET_KEY:
    if APP_ENV == "production":
        raise RuntimeError("FLASK_SECRET_KEY must be set in production.")
    SECRET_KEY = "local-development-only-change-before-deployment"
if APP_ENV == "production" and len(SECRET_KEY) < 32:
    raise RuntimeError("FLASK_SECRET_KEY must contain at least 32 characters in production.")
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.environ.get("SESSION_COOKIE_SAMESITE", "Lax"),
    SESSION_COOKIE_SECURE=APP_ENV == "production",
)
app.permanent_session_lifetime = timedelta(days=int(os.environ.get("SESSION_LIFETIME_DAYS", "365")))

MASTER_DB_FILE = os.environ.get("MASTER_DB_FILE", "voc_database.csv")
USER_LIST_FILE = os.environ.get("USER_LIST_FILE", "exam_list.csv")
DATABASE_PATH = os.environ.get("DATABASE_PATH", "quiz_progress.sqlite3")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:cloud")
OLLAMA_API_ENDPOINT = os.environ.get("OLLAMA_API_ENDPOINT", "http://host.docker.internal:11434/api/chat")
if APP_ENV == "production" and (
    not OLLAMA_API_ENDPOINT or "host.docker.internal" in OLLAMA_API_ENDPOINT
):
    raise RuntimeError("Set OLLAMA_API_ENDPOINT to an Ollama URL reachable from the cloud app.")
OLLAMA_CONNECT_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_CONNECT_TIMEOUT_SECONDS", "10"))
OLLAMA_READ_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_READ_TIMEOUT_SECONDS", "600"))
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")
FSRS_DESIRED_RETENTION = float(os.environ.get("FSRS_DESIRED_RETENTION", "0.9"))
FSRS_MAXIMUM_INTERVAL_DAYS = int(os.environ.get("FSRS_MAXIMUM_INTERVAL_DAYS", "36500"))
if not 0 < FSRS_DESIRED_RETENTION < 1:
    raise RuntimeError("FSRS_DESIRED_RETENTION must be between 0 and 1.")
if FSRS_MAXIMUM_INTERVAL_DAYS < 1:
    raise RuntimeError("FSRS_MAXIMUM_INTERVAL_DAYS must be at least 1.")
MODEL_LIST_CACHE_SECONDS = 15
MODEL_LIST_TIMEOUT_SECONDS = (1, 2)
_model_list_cache = None
_model_list_cache_at = 0.0


def get_model_choices():
    """Return Cloud plus models installed on the configured Ollama service."""
    global _model_list_cache, _model_list_cache_at
    now = time.monotonic()
    if _model_list_cache is not None and now - _model_list_cache_at < MODEL_LIST_CACHE_SECONDS:
        return _model_list_cache.copy()

    choices = {"gemma4:cloud": "Gemma 4 Cloud（雲端）"}
    if OLLAMA_MODEL != "gemma4:cloud":
        choices[OLLAMA_MODEL] = f"{OLLAMA_MODEL}（環境預設）"

    endpoint = urlsplit(OLLAMA_API_ENDPOINT)
    path = endpoint.path.rstrip("/")
    if path.endswith("/api/chat"):
        path = path[:-len("/api/chat")] + "/api/tags"
    else:
        path = path + "/api/tags"
    tags_endpoint = urlunsplit((endpoint.scheme, endpoint.netloc, path, "", ""))

    try:
        response = requests.get(tags_endpoint, timeout=MODEL_LIST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        for model in models:
            if not isinstance(model, dict):
                continue
            raw_name = model.get("name") or model.get("model") or ""
            name = raw_name.strip() if isinstance(raw_name, str) else ""
            if name:
                if name != "gemma4:cloud":
                    choices[name] = name
        _model_list_cache = choices.copy()
        _model_list_cache_at = now
    except (requests.RequestException, ValueError, TypeError):
        if _model_list_cache is not None:
            _model_list_cache_at = now
            return _model_list_cache.copy()
    return choices


def get_page_model_choices():
    choices = get_model_choices()
    selected = session.get("ollama_model", OLLAMA_MODEL)
    if selected not in choices:
        choices[selected] = f"{selected}（目前未列於 Ollama 模型清單）"
    return choices


def open_database():
    database_dir = os.path.dirname(os.path.abspath(DATABASE_PATH))
    os.makedirs(database_dir, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


@contextmanager
def database_connection():
    connection = open_database()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    with database_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS learner_word_progress (
                learner_id TEXT NOT NULL,
                word TEXT NOT NULL,
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                last_selected_at REAL,
                last_reviewed_at REAL,
                last_result INTEGER,
                fsrs_stability REAL,
                fsrs_difficulty REAL,
                due_at REAL,
                review_count INTEGER NOT NULL DEFAULT 0,
                lapse_count INTEGER NOT NULL DEFAULT 0,
                card_state TEXT NOT NULL DEFAULT 'new',
                last_grade INTEGER,
                PRIMARY KEY (learner_id, word)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS learner_answer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                learner_id TEXT NOT NULL,
                word TEXT NOT NULL,
                grade INTEGER NOT NULL,
                answer_correct INTEGER NOT NULL,
                response_seconds REAL NOT NULL,
                answered_at REAL NOT NULL
            )
        """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS learner_answer_history_by_learner
            ON learner_answer_history (learner_id, answered_at)
        """)
        existing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(learner_word_progress)")
        }
        migrations = {
            "fsrs_stability": "REAL",
            "fsrs_difficulty": "REAL",
            "due_at": "REAL",
            "review_count": "INTEGER NOT NULL DEFAULT 0",
            "lapse_count": "INTEGER NOT NULL DEFAULT 0",
            "card_state": "TEXT NOT NULL DEFAULT 'new'",
            "last_grade": "INTEGER",
        }
        for column, definition in migrations.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE learner_word_progress ADD COLUMN {column} {definition}"
                )

        # Seed one FSRS state from the most recent binary answer in old databases.
        legacy_rows = connection.execute("""
            SELECT learner_id, word, last_reviewed_at, last_result
            FROM learner_word_progress
            WHERE fsrs_stability IS NULL AND last_reviewed_at IS NOT NULL
              AND last_result IS NOT NULL
        """).fetchall()
        for row in legacy_rows:
            grade = 3 if row["last_result"] else 1
            stability, difficulty = fsrs45.initial_memory_state(grade)
            interval = fsrs45.interval_days(
                stability, FSRS_DESIRED_RETENTION, FSRS_MAXIMUM_INTERVAL_DAYS
            )
            connection.execute("""
                UPDATE learner_word_progress
                SET fsrs_stability = ?, fsrs_difficulty = ?, due_at = ?,
                    review_count = MAX(review_count, 1),
                    lapse_count = MAX(lapse_count, ?), card_state = 'review', last_grade = ?
                WHERE learner_id = ? AND word = ?
            """, (stability, difficulty, row["last_reviewed_at"] + interval * 86400,
                  int(grade == 1), grade, row["learner_id"], row["word"]))


initialize_database()


def get_learner_id():
    """Return a stable anonymous profile id stored in the signed browser cookie."""
    session.permanent = True
    learner_id = session.get("learner_id")
    if not learner_id:
        learner_id = str(uuid.uuid4())
        session["learner_id"] = learner_id
    return learner_id


def get_progress(learner_id, words):
    progress = {
        item["arabic_word"]: {
            "correct_count": 0,
            "wrong_count": 0,
            "last_selected_at": None,
            "last_reviewed_at": None,
            "last_result": None,
            "fsrs_stability": None,
            "fsrs_difficulty": None,
            "due_at": None,
            "review_count": 0,
            "lapse_count": 0,
            "card_state": "new",
            "last_grade": None,
        }
        for item in words
    }
    with database_connection() as connection:
        rows = connection.execute(
            "SELECT word, correct_count, wrong_count, last_selected_at, last_reviewed_at, last_result, "
            "fsrs_stability, fsrs_difficulty, due_at, review_count, lapse_count, card_state, last_grade "
            "FROM learner_word_progress WHERE learner_id = ?", (learner_id,)
        )
        for row in rows:
            if row["word"] in progress:
                progress[row["word"]] = {
                    "correct_count": row["correct_count"],
                    "wrong_count": row["wrong_count"],
                    "last_selected_at": row["last_selected_at"],
                    "last_reviewed_at": row["last_reviewed_at"],
                    "last_result": row["last_result"],
                    "fsrs_stability": row["fsrs_stability"],
                    "fsrs_difficulty": row["fsrs_difficulty"],
                    "due_at": row["due_at"],
                    "review_count": row["review_count"],
                    "lapse_count": row["lapse_count"],
                    "card_state": row["card_state"],
                    "last_grade": row["last_grade"],
                }
    return progress


def has_learning_history(learner_id):
    with database_connection() as connection:
        row = connection.execute(
            "SELECT EXISTS(SELECT 1 FROM learner_word_progress WHERE learner_id = ?)",
            (learner_id,),
        ).fetchone()
    return bool(row[0])


def clear_learning_history(learner_id):
    with database_connection() as connection:
        connection.execute("DELETE FROM learner_answer_history WHERE learner_id = ?", (learner_id,))
        connection.execute("DELETE FROM learner_word_progress WHERE learner_id = ?", (learner_id,))


def record_selection(learner_id, word):
    with database_connection() as connection:
        connection.execute("""
            INSERT INTO learner_word_progress (learner_id, word, last_selected_at)
            VALUES (?, ?, ?)
            ON CONFLICT (learner_id, word) DO UPDATE SET last_selected_at = excluded.last_selected_at
        """, (learner_id, word, time.time()))


def get_answer_time_stats(learner_id):
    with database_connection() as connection:
        rows = connection.execute(
            "SELECT response_seconds FROM learner_answer_history WHERE learner_id = ?",
            (learner_id,),
        ).fetchall()
    durations = [row["response_seconds"] for row in rows]
    if len(durations) < 2:
        return {"count": len(durations), "mean": None, "stdev": None}
    return {
        "count": len(durations),
        "mean": statistics.mean(durations),
        "stdev": statistics.stdev(durations),
    }


def apply_timing_grade(grade, response_seconds, stats):
    """Use prior answer-time mean +/- sample SD to rate correct answers."""
    if grade != 3 or stats["count"] < 2:
        return grade
    mean = stats["mean"]
    stdev = stats["stdev"]
    if response_seconds < mean - stdev:
        return 4
    if response_seconds > mean + stdev:
        return 2
    return 3


def record_answer(learner_id, word, grade, answer_correct, response_seconds):
    now = time.time()
    with database_connection() as connection:
        previous = connection.execute("""
            SELECT fsrs_stability, fsrs_difficulty, last_reviewed_at,
                   review_count, lapse_count, card_state
            FROM learner_word_progress WHERE learner_id = ? AND word = ?
        """, (learner_id, word)).fetchone()

        if previous is not None and previous["fsrs_stability"] is not None:
            elapsed_days = max(0.0, (now - previous["last_reviewed_at"]) / 86400)
            scheduled = fsrs45.next_memory_state(
                previous["fsrs_stability"], previous["fsrs_difficulty"], elapsed_days,
                grade, FSRS_DESIRED_RETENTION, FSRS_MAXIMUM_INTERVAL_DAYS,
            )
            review_count = previous["review_count"] + 1
            lapse_count = previous["lapse_count"] + int(
                grade == 1 and previous["card_state"] == "review"
            )
        else:
            stability, difficulty = fsrs45.initial_memory_state(grade)
            scheduled = {
                "stability": stability,
                "difficulty": difficulty,
                "retrievability": None,
                "interval_days": fsrs45.interval_days(
                    stability, FSRS_DESIRED_RETENTION, FSRS_MAXIMUM_INTERVAL_DAYS
                ),
            }
            review_count = 1
            lapse_count = 0

        scheduled["due_at"] = now + scheduled["interval_days"] * 86400
        connection.execute("""
            INSERT INTO learner_word_progress
                (learner_id, word, correct_count, wrong_count, last_reviewed_at, last_result,
                 fsrs_stability, fsrs_difficulty, due_at, review_count, lapse_count,
                 card_state, last_grade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'review', ?)
            ON CONFLICT (learner_id, word) DO UPDATE SET
                correct_count = learner_word_progress.correct_count + excluded.correct_count,
                wrong_count = learner_word_progress.wrong_count + excluded.wrong_count,
                last_reviewed_at = excluded.last_reviewed_at,
                last_result = excluded.last_result,
                fsrs_stability = excluded.fsrs_stability,
                fsrs_difficulty = excluded.fsrs_difficulty,
                due_at = excluded.due_at,
                review_count = excluded.review_count,
                lapse_count = excluded.lapse_count,
                card_state = excluded.card_state,
                last_grade = excluded.last_grade
        """, (learner_id, word, int(answer_correct), int(not answer_correct), now, int(answer_correct),
              scheduled["stability"], scheduled["difficulty"], scheduled["due_at"],
              review_count, lapse_count, grade))
        connection.execute("""
            INSERT INTO learner_answer_history
                (learner_id, word, grade, answer_correct, response_seconds, answered_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (learner_id, word, grade, int(answer_correct), response_seconds, now))
    return scheduled


def migrate_legacy_quiz_state(state, learner_id, words):
    """Move counters from the old cookie-based quiz format into SQLite once."""
    if state.get("version") != 2:
        return
    correct = state.get("correct", [])
    wrong = state.get("wrong", [])
    if len(correct) != len(words) or len(wrong) != len(words):
        return
    with database_connection() as connection:
        for item, right_count, wrong_count in zip(words, correct, wrong):
            connection.execute("""
                INSERT INTO learner_word_progress (learner_id, word, correct_count, wrong_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (learner_id, word) DO UPDATE SET
                    correct_count = MAX(learner_word_progress.correct_count, excluded.correct_count),
                    wrong_count = MAX(learner_word_progress.wrong_count, excluded.wrong_count)
            """, (learner_id, item["arabic_word"], right_count, wrong_count))
    state.pop("correct", None)
    state.pop("wrong", None)
    state["version"] = 3
    state["word_count"] = len(words)


def load_words():
    """Join the user's list with corpus frequencies, tolerating UTF-8 BOM files."""
    frequencies = {}
    with open(MASTER_DB_FILE, newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            word = (row.get("arabic_word") or "").strip()
            try:
                frequencies[word] = max(1.0, float(row.get("frequency") or 1))
            except ValueError:
                frequencies[word] = 1.0

    words = []
    with open(USER_LIST_FILE, newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            word = (row.get("arabic_word") or "").strip()
            meaning = (row.get("translation") or "").strip()
            if word and meaning:
                words.append({"arabic_word": word, "translation": meaning,
                              "frequency": frequencies.get(word, 1.0)})
    if not words:
        raise ValueError(f"{USER_LIST_FILE} 沒有可用的單字。")
    frequency_levels = sorted({item["frequency"] for item in words})
    frequency_percentiles = {
        value: (rank / (len(frequency_levels) - 1) if len(frequency_levels) > 1 else 0.5)
        for rank, value in enumerate(frequency_levels)
    }
    for item in words:
        # Wiki frequency orders only unseen cards; FSRS schedules reviewed cards.
        item["new_card_weight"] = 0.5 + frequency_percentiles[item["frequency"]]
    return words


def normalize_arabic(value):
    value = unicodedata.normalize("NFC", value).strip()
    return re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)


def shared_arabic_letter_count(left, right):
    """Count shared Arabic letter occurrences, ignoring order and diacritics."""
    left_letters = [char for char in normalize_arabic(left)
                    if "ARABIC" in unicodedata.name(char, "") and char.isalpha()]
    right_letters = [char for char in normalize_arabic(right)
                     if "ARABIC" in unicodedata.name(char, "") and char.isalpha()]
    return sum((Counter(left_letters) & Counter(right_letters)).values())


def grade_answer(target, meaning, answer, model):
    """Fast exact check followed by the selected Ollama model."""
    if normalize_arabic(answer) == normalize_arabic(target):
        return 3, "完全正確！", {"called": False}

    shared_letters = shared_arabic_letter_count(target, answer)
    number_check = (
        "先檢查學生答案是否只是標準答案同一詞彙的單數／複數變化。"
        "只有確定是同一詞的單複數形式才判 Correct；同義詞、派生詞、相關詞或拼寫相似都不能因此判 Correct。"
        if shared_letters >= 3 else
        "兩者相同字母少於三個，不要判為單複數變化，直接依詞意遠近分類。"
    )

    prompt = f"""你是專業阿拉伯語教師。學生根據中文意思寫阿拉伯文。
中文意思：{meaning}
預期答案：{target}
學生答案：{answer}
{number_check}
若確認是同一詞的單數／複數變化，判為 Correct。
否則，若學生答案本身的詞意與中文提示／標準答案接近，雖非可接受的標準答案，判為 Hard（例如相關概念或容易混淆的近義詞）。
若詞意不相關、完全錯誤或無法辨認，判為 Again。
只回覆一個標籤：Correct、Hard 或 Again，不要附加說明。"""
    try:
        response = requests.post(OLLAMA_API_ENDPOINT, json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
        }, timeout=(OLLAMA_CONNECT_TIMEOUT_SECONDS, OLLAMA_READ_TIMEOUT_SECONDS))
        response.raise_for_status()
        payload = response.json()
        result = payload.get("message", {}).get("content", "").strip().lower()
        if "prompt_eval_count" in payload or "eval_count" in payload:
            usage = {
                "called": True,
                "input": int(payload.get("prompt_eval_count") or 0),
                "output": int(payload.get("eval_count") or 0),
            }
        else:
            usage = {"called": True, "input": None, "output": None}
        labels = re.findall(r"\b(correct|hard|again)\b", result)
        if len(labels) != 1:
            return None, "模型未能提供有效的 Correct／Hard／Again 分類，請重試。", usage
        grade = {"again": 1, "hard": 2, "correct": 3}[labels[0]]
        messages = {
            1: "答案不正確，安排重新學習。",
            2: "答案詞意接近，但不是標準答案；記為 Hard。",
            3: "AI 判定為可接受答案（含同一詞的單複數變化）。",
        }
        return grade, messages[grade], usage
    except requests.exceptions.Timeout:
        return None, (f"Ollama 正在運算，但超過 {int(OLLAMA_READ_TIMEOUT_SECONDS)} 秒仍未完成。"
                      "請稍候再試，或提高 OLLAMA_READ_TIMEOUT_SECONDS。"), None
    except requests.RequestException:
        return None, "無法連線到 Ollama，請確認服務位址及網路設定後重試。", None


def new_quiz_state():
    words = load_words()
    return {
        "version": 4,
        "word_count": len(words),
        "cloud_input_tokens": 0,
        "cloud_output_tokens": 0,
        "cloud_calls": 0,
        "cloud_usage_complete": True,
        "current": None,
        "next_due_at": None,
        "last_interval_days": None,
        "feedback": None,
        "feedback_correct": False,
        "feedback_grade": None,
        "feedback_class": "bad",
        "question_started_at": None,
        "pending_answer_seconds": 0.0,
        "paused": False,
        "pause_started_at": None,
        "answered": False,
    }


def choose_question(state):
    words = load_words()
    learner_id = get_learner_id()
    progress = get_progress(learner_id, words)
    now = time.time()
    due_reviews = [
        i for i, item in enumerate(words)
        if progress[item["arabic_word"]]["card_state"] == "review"
        and progress[item["arabic_word"]]["due_at"] is not None
        and progress[item["arabic_word"]]["due_at"] <= now
    ]
    new_cards = [
        i for i, item in enumerate(words)
        if progress[item["arabic_word"]]["card_state"] == "new"
    ]
    if due_reviews:
        def review_priority(index):
            item_progress = progress[words[index]["arabic_word"]]
            elapsed = max(0.0, (now - item_progress["last_reviewed_at"]) / 86400)
            recall = fsrs45.retrievability(elapsed, item_progress["fsrs_stability"])
            return (recall, item_progress["due_at"])
        index = min(due_reviews, key=review_priority)
    elif new_cards:
        index = random.choices(
            new_cards, weights=[words[i]["new_card_weight"] for i in new_cards], k=1
        )[0]
    else:
        state["current"] = None
        future_due_dates = [
            progress[item["arabic_word"]]["due_at"]
            for item in words
            if progress[item["arabic_word"]]["due_at"] is not None
        ]
        state["next_due_at"] = min(future_due_dates) if future_due_dates else None
        session["quiz"] = state
        return
    state["current"] = index
    state["next_due_at"] = None
    state["last_interval_days"] = None
    state["answered"] = False
    state["question_started_at"] = now
    state["pending_answer_seconds"] = 0.0
    state["paused"] = False
    state["pause_started_at"] = None
    state["feedback"] = None
    record_selection(learner_id, words[index]["arabic_word"])
    session["quiz"] = state


@app.get("/")
def home():
    learner_id = get_learner_id()
    state = session.get("quiz")
    if not state:
        return render_template("index.html", state=None, question=None, total=0, mastered=0,
                               reviewed_count=0, due_count=0, next_due_in_days=None,
                               has_history=has_learning_history(learner_id),
                               model_choices=get_page_model_choices(),
                               selected_model=session.get("ollama_model", OLLAMA_MODEL))
    try:
        words = load_words()
    except (OSError, ValueError, csv.Error):
        session.pop("quiz", None)
        flash("無法載入單字資料，請檢查 CSV 檔案。", "error")
        return redirect(url_for("home"))
    migrate_legacy_quiz_state(state, learner_id, words)
    if state.get("version") != 4 or state.get("word_count") != len(words):
        session.pop("quiz", None)
        flash("測驗資料已更新，請重新開始。", "success")
        return redirect(url_for("home"))
    # Keep sessions created before the usage panel was added readable.
    state.setdefault("cloud_input_tokens", 0)
    state.setdefault("cloud_output_tokens", 0)
    state.setdefault("cloud_calls", 0)
    state.setdefault("cloud_usage_complete", True)
    state.setdefault("question_started_at", time.time())
    state.setdefault("pending_answer_seconds", 0.0)
    state.setdefault("paused", False)
    state.setdefault("pause_started_at", None)
    session["quiz"] = state
    progress = get_progress(learner_id, words)
    index = state["current"]
    question = words[index] if index is not None and 0 <= index < len(words) else None
    now = time.time()
    reviewed_count = sum(item["card_state"] == "review" for item in progress.values())
    due_count = sum(item["due_at"] is not None and item["due_at"] <= now
                    for item in progress.values())
    next_due_in_days = None
    if state.get("next_due_at") is not None:
        next_due_in_days = max(0, (state["next_due_at"] - now) / 86400)
    return render_template("index.html", state=state, question=question,
                           progress=progress, total=len(words), reviewed_count=reviewed_count,
                           due_count=due_count, next_due_in_days=next_due_in_days,
                           has_history=has_learning_history(learner_id),
                           model_choices=get_page_model_choices(),
                           selected_model=session.get("ollama_model", OLLAMA_MODEL))


@app.post("/start")
def start():
    try:
        get_learner_id()
        state = new_quiz_state()
        choose_question(state)
        if state["current"] is None:
            flash("目前沒有到期單字；已顯示下一次預定複習時間。", "success")
        else:
            flash(f"已載入 {state['word_count']} 個單字，開始練習吧！", "success")
    except (OSError, ValueError, csv.Error) as error:
        session.pop("quiz", None)
        flash(f"無法載入單字資料：{error}", "error")
    return redirect(url_for("home"))


@app.post("/model")
def change_model():
    selected_model = request.form.get("model", "")
    if selected_model not in get_model_choices():
        flash("無效的模型選擇。", "error")
    else:
        session["ollama_model"] = selected_model
        flash(f"批改模型已切換為 {get_model_choices()[selected_model]}。", "success")
    return redirect(url_for("home"))


@app.post("/answer")
def answer():
    state = session.get("quiz")
    if (not state or state.get("version") != 4 or state["current"] is None
            or state["answered"] or state.get("paused")):
        return redirect(url_for("home"))
    learner_id = get_learner_id()
    words = load_words()
    answer_text = request.form.get("answer", "").strip()
    index = state["current"]
    if not 0 <= index < len(words) or state.get("word_count") != len(words):
        session.pop("quiz", None)
        flash("單字清單已變更，請重新開始測驗。", "success")
        return redirect(url_for("home"))
    word = words[index]
    if not answer_text:
        state["feedback"] = "請先輸入阿拉伯文答案。"
        state["feedback_correct"] = False
        session["quiz"] = state
        return redirect(url_for("home"))

    submitted_at = time.time()
    state["question_started_at"] = state.get("question_started_at") or submitted_at
    state.setdefault("pending_answer_seconds", 0.0)
    response_seconds = state["pending_answer_seconds"] + max(
        0.0, submitted_at - state["question_started_at"]
    )
    selected_model = session.get("ollama_model", OLLAMA_MODEL)
    grade, message, usage = grade_answer(
        word["arabic_word"], word["translation"], answer_text, selected_model)
    if selected_model == "gemma4:cloud" and usage and usage["called"]:
        state["cloud_calls"] += 1
        if usage["input"] is None or usage["output"] is None:
            state["cloud_usage_complete"] = False
        else:
            state["cloud_input_tokens"] += usage["input"]
            state["cloud_output_tokens"] += usage["output"]
    if grade is None:
        state["feedback"] = message
        state["feedback_correct"] = False
        state["feedback_grade"] = None
        state["feedback_class"] = "bad"
        state["pending_answer_seconds"] = response_seconds
        # Model latency occurs after submission and must not count as thinking time.
        state["question_started_at"] = time.time()
        state["answered"] = False
        session["quiz"] = state
        return redirect(url_for("home"))

    answer_correct = grade == 3
    stats = get_answer_time_stats(learner_id)
    grade = apply_timing_grade(grade, response_seconds, stats)
    if answer_correct and grade == 4:
        message = "答對且作答速度快於個人平均一個標準差以上，記為 Easy。"
    elif answer_correct and grade == 2:
        message = "答案正確，但作答時間較長，依個人平均與標準差記為 Hard。"
    elif answer_correct and stats["count"] < 2:
        message = "答案正確；累積足夠作答紀錄後，會開始依速度調整難度。"
    state["feedback"] = message
    state["feedback_correct"] = answer_correct
    state["feedback_grade"] = grade
    state["feedback_class"] = {1: "bad", 2: "hard", 3: "good", 4: "easy"}[grade]
    schedule = record_answer(
        learner_id, word["arabic_word"], grade, answer_correct, response_seconds
    )
    state["last_interval_days"] = schedule["interval_days"]
    state["answered"] = True
    session["quiz"] = state
    return redirect(url_for("home"))


@app.post("/pause")
def toggle_pause():
    state = session.get("quiz")
    if (not state or state.get("version") != 4 or state.get("current") is None
            or state.get("answered")):
        return redirect(url_for("home"))
    now = time.time()
    if state.get("paused"):
        paused_at = state.get("pause_started_at") or now
        started_at = state.get("question_started_at") or now
        state["question_started_at"] = started_at + max(0.0, now - paused_at)
        state["paused"] = False
        state["pause_started_at"] = None
    else:
        state["paused"] = True
        state["pause_started_at"] = now
    session["quiz"] = state
    return redirect(url_for("home"))


@app.post("/next")
def next_question():
    state = session.get("quiz")
    if state and state["answered"]:
        choose_question(state)
    return redirect(url_for("home"))


@app.post("/reset")
def reset():
    session.pop("quiz", None)
    return redirect(url_for("home"))


@app.post("/reset-progress")
def reset_progress():
    learner_id = get_learner_id()
    clear_learning_history(learner_id)
    session.pop("quiz", None)
    state = new_quiz_state()
    choose_question(state)
    flash("已清除此瀏覽器的學習紀錄，開始新一輪練習。", "success")
    return redirect(url_for("home"))


@app.get("/healthz")
def healthcheck():
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
