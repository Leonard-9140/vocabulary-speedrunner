"""Browser based Arabic vocabulary quiz."""

import csv
import os
import random
import re
import unicodedata

import requests
from flask import Flask, flash, redirect, render_template, request, session, url_for

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

MASTER_DB_FILE = os.environ.get("MASTER_DB_FILE", "voc_database.csv")
USER_LIST_FILE = os.environ.get("USER_LIST_FILE", "exam_list.csv")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:cloud")
MODEL_CHOICES = {
    "gemma4:cloud": "Gemma 4 Cloud",
    "gemma4:e4b": "Gemma 4 E4B（本機）",
}
if OLLAMA_MODEL not in MODEL_CHOICES:
    MODEL_CHOICES[OLLAMA_MODEL] = f"{OLLAMA_MODEL}（環境設定）"
OLLAMA_API_ENDPOINT = os.environ.get("OLLAMA_API_ENDPOINT", "http://host.docker.internal:11434/api/chat")
if APP_ENV == "production" and (
    not OLLAMA_API_ENDPOINT or "host.docker.internal" in OLLAMA_API_ENDPOINT
):
    raise RuntimeError("Set OLLAMA_API_ENDPOINT to an Ollama URL reachable from the cloud app.")
OLLAMA_CONNECT_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_CONNECT_TIMEOUT_SECONDS", "10"))
OLLAMA_READ_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_READ_TIMEOUT_SECONDS", "600"))
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")
WIN_CONDITION = int(os.environ.get("WIN_CONDITION", "5"))


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
    return words


def normalize_arabic(value):
    value = unicodedata.normalize("NFC", value).strip()
    return re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)


def grade_answer(target, meaning, answer, all_words, model):
    """Fast exact check followed by the selected Ollama model."""
    if normalize_arabic(answer) == normalize_arabic(target):
        return True, "完全正確！", {"called": False}
    if answer.strip() in all_words and answer.strip() != target:
        return False, "這是清單中的另一個單字。", {"called": False}

    prompt = f"""你是專業阿拉伯語教師。學生根據中文意思寫阿拉伯文。
中文意思：{meaning}
預期答案：{target}
學生答案：{answer}
只在答案確實是同一個詞、可接受的詞形或輕微拼寫錯誤時判為 Correct；其他情況判為 Incorrect。
只回覆 Correct 或 Incorrect。"""
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
        correct = "correct" in result and "incorrect" not in result
        return correct, "AI 判定正確。" if correct else "答案不正確。", usage
    except requests.exceptions.Timeout:
        return None, (f"Ollama 正在運算，但超過 {int(OLLAMA_READ_TIMEOUT_SECONDS)} 秒仍未完成。"
                      "請稍候再試，或提高 OLLAMA_READ_TIMEOUT_SECONDS。"), None
    except requests.RequestException:
        return None, "無法連線到 Ollama，請確認服務位址及網路設定後重試。", None


def new_quiz_state():
    words = load_words()
    return {
        "version": 2,
        "correct": [0] * len(words),
        "wrong": [0] * len(words),
        "cloud_input_tokens": 0,
        "cloud_output_tokens": 0,
        "cloud_calls": 0,
        "cloud_usage_complete": True,
        "current": None,
        "feedback": None,
        "feedback_correct": False,
        "answered": False,
    }


def choose_question(state):
    words = load_words()
    active = [i for i, count in enumerate(state["correct"]) if count < WIN_CONDITION]
    if not active:
        state["current"] = None
        session["quiz"] = state
        return
    weights = [max(1, words[i]["frequency"] * (2 ** state["wrong"][i]) /
                   (5 ** state["correct"][i])) for i in active]
    index = random.choices(active, weights=weights, k=1)[0]
    state["current"] = index
    state["answered"] = False
    state["feedback"] = None
    session["quiz"] = state


@app.get("/")
def home():
    state = session.get("quiz")
    if not state:
        return render_template("index.html", state=None, question=None, total=0, mastered=0,
                               win_condition=WIN_CONDITION,
                               model_choices=MODEL_CHOICES,
                               selected_model=session.get("ollama_model", OLLAMA_MODEL))
    try:
        words = load_words()
    except (OSError, ValueError, csv.Error):
        session.pop("quiz", None)
        flash("無法載入單字資料，請檢查 CSV 檔案。", "error")
        return redirect(url_for("home"))
    if state.get("version") != 2 or len(state.get("correct", [])) != len(words):
        session.pop("quiz", None)
        flash("測驗資料已更新，請重新開始。", "success")
        return redirect(url_for("home"))
    # Keep sessions created before the usage panel was added readable.
    state.setdefault("cloud_input_tokens", 0)
    state.setdefault("cloud_output_tokens", 0)
    state.setdefault("cloud_calls", 0)
    state.setdefault("cloud_usage_complete", True)
    index = state["current"]
    question = words[index] if index is not None and 0 <= index < len(words) else None
    return render_template("index.html", state=state, question=question,
                           total=len(words), mastered=sum(count >= WIN_CONDITION for count in state["correct"]),
                           win_condition=WIN_CONDITION,
                           model_choices=MODEL_CHOICES,
                           selected_model=session.get("ollama_model", OLLAMA_MODEL))


@app.post("/start")
def start():
    try:
        state = new_quiz_state()
        choose_question(state)
        flash(f"已載入 {len(state['correct'])} 個單字，開始練習吧！", "success")
    except (OSError, ValueError, csv.Error) as error:
        session.pop("quiz", None)
        flash(f"無法載入單字資料：{error}", "error")
    return redirect(url_for("home"))


@app.post("/model")
def change_model():
    selected_model = request.form.get("model", "")
    if selected_model not in MODEL_CHOICES:
        flash("無效的模型選擇。", "error")
    else:
        session["ollama_model"] = selected_model
        flash(f"批改模型已切換為 {MODEL_CHOICES[selected_model]}。", "success")
    return redirect(url_for("home"))


@app.post("/answer")
def answer():
    state = session.get("quiz")
    if not state or state.get("version") != 2 or state["current"] is None or state["answered"]:
        return redirect(url_for("home"))
    words = load_words()
    answer_text = request.form.get("answer", "").strip()
    index = state["current"]
    if not 0 <= index < len(words) or len(state["correct"]) != len(words):
        session.pop("quiz", None)
        flash("單字清單已變更，請重新開始測驗。", "success")
        return redirect(url_for("home"))
    word = words[index]
    if not answer_text:
        state["feedback"] = "請先輸入阿拉伯文答案。"
        state["feedback_correct"] = False
        session["quiz"] = state
        return redirect(url_for("home"))

    selected_model = session.get("ollama_model", OLLAMA_MODEL)
    correct, message, usage = grade_answer(
        word["arabic_word"], word["translation"], answer_text,
        {item["arabic_word"] for item in words}, selected_model)
    if selected_model == "gemma4:cloud" and usage and usage["called"]:
        state["cloud_calls"] += 1
        if usage["input"] is None or usage["output"] is None:
            state["cloud_usage_complete"] = False
        else:
            state["cloud_input_tokens"] += usage["input"]
            state["cloud_output_tokens"] += usage["output"]
    state["feedback"] = message
    state["feedback_correct"] = correct
    if correct is None:
        state["answered"] = False
        session["quiz"] = state
        return redirect(url_for("home"))
    state["answered"] = True
    if correct:
        state["correct"][index] = min(WIN_CONDITION, state["correct"][index] + 1)
        if state["correct"][index] >= WIN_CONDITION:
            state["feedback"] += " 這個單字已精通！"
    else:
        state["wrong"][index] = min(20, state["wrong"][index] + 1)
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


@app.get("/healthz")
def healthcheck():
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
