import requests
import json

OLLAMA_MODEL = "gemma3:4b"
OLLAMA_API_ENDPOINT = "http://localhost:11434/api/generate"

def debug_grading(question_word, correct_answer, user_answer):
    prompt = f"""你是一位嚴謹但開明的語言老師。
現在學生正在進行「阿拉伯文到中文」的翻譯練習。
題目："{question_word}"
正確答案："{correct_answer}"
學生回答："{user_answer}"

請判斷學生的回答是否為正確翻譯、語意相近的同義詞（例如「汽車」與「車子」），或在中文語境下可被接受的正確答案。
請只回覆一個單詞："Correct" 或 "Incorrect"。
"""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    
    print(f"\n--- 偵錯開始: {question_word} -> {user_answer} ---")
    try:
        response = requests.post(OLLAMA_API_ENDPOINT, json=payload)
        response.encoding = 'utf-8'
        result_json = response.json()
        raw_response = result_json.get("response", "")
        print(f"原始 AI 回覆: |{raw_response}|")
        
        llm_decision = raw_response.strip().replace(".", "").replace("!", "")
        print(f"處理後判定: {llm_decision}")
        
        if "correct" in llm_decision.lower() and "incorrect" not in llm_decision.lower():
            print("結果: ✅ Correct")
        else:
            print("結果: ❌ Incorrect")
            
    except Exception as e:
        print(f"發生錯誤: {e}")

if __name__ == "__main__":
    # 測試使用者回報的案例
    debug_grading("كتاب", "書本", "書")
    debug_grading("كتاب", "書本", "書籍")
    # 測試先前的汽車案例
    debug_grading("سيارة", "汽車", "車子")
