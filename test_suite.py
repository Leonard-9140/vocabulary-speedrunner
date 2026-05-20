import requests
import json
import pandas as pd
import os

# 模擬 main_quiz.py 中的設定
OLLAMA_MODEL = "gemma3:4b"
OLLAMA_API_ENDPOINT = "http://localhost:11434/api/generate"

def test_ollama_connectivity():
    print("--- 測試 1: Ollama API 連線 ---")
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = [m['name'] for m in response.json().get('models', [])]
            print(f"✅ 成功連線到 Ollama。已安裝模型: {models}")
            if OLLAMA_MODEL in models or f"{OLLAMA_MODEL}:latest" in models:
                print(f"✅ 找到目標模型: {OLLAMA_MODEL}")
                return True
            else:
                print(f"❌ 找不到模型 {OLLAMA_MODEL}。請執行 'ollama pull {OLLAMA_MODEL}'")
                return False
        else:
            print(f"❌ Ollama 回傳錯誤碼: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 無法連線到 Ollama: {e}")
        return False

def grade_answer_mock(question_word, correct_answer, user_answer):
    prompt = f"""你是一位嚴謹但開明的語言老師。
現在學生正在進行「阿拉伯文到中文」的翻譯練習。
題目："{question_word}"
正確答案："{correct_answer}"
學生回答："{user_answer}"

請判斷學生的回答是否為正確翻譯、語意相近的同義詞（例如「汽車」與「車子」），或在中文語境下可被接受的正確答案。
請只回覆一個單詞："Correct" 或 "Incorrect"。
"""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    response = requests.post(OLLAMA_API_ENDPOINT, json=payload)
    llm_decision = json.loads(response.text).get("response", "").strip().replace(".", "").replace("!", "")
    return llm_decision

def test_llm_grading():
    print(f"\n--- 測試 2: LLM 批改邏輯 ({OLLAMA_MODEL}) ---")
    test_cases = [
        {"q": "كتاب", "correct": "書本", "user": "書本", "expected": "Correct", "desc": "完全一致"},
        {"q": "سيارة", "correct": "汽車", "user": "車子", "expected": "Correct", "desc": "同義詞"},
        {"q": "بيت", "correct": "房子", "user": "飛機", "expected": "Incorrect", "desc": "錯誤答案"},
    ]

    for i, case in enumerate(test_cases):
        print(f"測試項 {i+1} ({case['desc']}): 題目={case['q']}, 答案={case['correct']}, 輸入={case['user']}")
        result = grade_answer_mock(case['q'], case['correct'], case['user'])
        print(f"   🤖 AI 判定: {result}")
        
        # 修正判斷邏輯：確保 "Correct" 不會誤判為 "Incorrect"
        is_pass = False
        if case['expected'].lower() == "correct":
            # 如果預期是 Correct，則結果必須包含 correct 且不能包含 incorrect
            if "correct" in result.lower() and "incorrect" not in result.lower():
                is_pass = True
        else:
            # 如果預期是 Incorrect，則結果必須包含 incorrect
            if "incorrect" in result.lower():
                is_pass = True

        if is_pass:
            print("   ✅ 通過")
        else:
            print(f"   ⚠️ 判定不符預期 (預期: {case['expected']})")

def test_data_files():
    print("\n--- 測試 3: 資料檔案完整性 ---")
    files = ["voc_database.csv", "exam_list.csv"]
    for f in files:
        if os.path.exists(f):
            try:
                df = pd.read_csv(f)
                print(f"✅ {f} 讀取成功，共 {len(df)} 筆資料。")
            except Exception as e:
                print(f"❌ {f} 讀取失敗: {e}")
        else:
            print(f"❌ 找不到檔案: {f}")

if __name__ == "__main__":
    connectivity = test_ollama_connectivity()
    if connectivity:
        test_llm_grading()
    test_data_files()
