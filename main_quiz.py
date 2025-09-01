import pandas as pd
import random
import os
import requests # 引入我們的通訊工具
import json     # 用於解析 AI 的回覆

# --- 設定 ---
MASTER_DB_FILE = "voc_database.csv"  # 我們的通用詞頻資料庫
USER_LIST_FILE = "exam_list.csv"     # 使用者提供的考試單字表
WIN_CONDITION = 5                    # 每個單字需要答對幾次才算完成
OLLAMA_MODEL = "gemma:2b"            # 指定使用輕量級的 gemma:2b 模型
OLLAMA_API_ENDPOINT = "http://localhost:11434/api/generate"

def clear_screen():
    """清除終端機畫面，讓介面更清爽"""
    os.system('cls' if os.name == 'nt' else 'clear')

def grade_answer_with_llm(question_word, correct_answer, user_answer):
    """
    【新功能】使用本地運行的 LLM 來判斷使用者答案是否正確。
    """
    # --- 關鍵：設計給 LLM 的指令 (Prompt) ---
    # 這個指令告訴 AI 它的角色、上下文、以及我們希望它回覆的格式
    prompt = f"""You are a strict but fair language tutor. 
A user was shown the Arabic word "{question_word}". 
The correct translation is "{correct_answer}". 
The user answered with "{user_answer}". 
Is the user's answer a correct translation, a valid synonym, or semantically close enough to be considered correct? 
Please respond with only a single word: "Correct" or "Incorrect".
"""
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False # 我們需要一次性收到完整回覆
    }

    try:
        # 發送請求給本地的 Ollama API
        response = requests.post(OLLAMA_API_ENDPOINT, json=payload)
        response.raise_for_status() # 如果請求失敗會拋出異常
        
        # 解析 LLM 的 JSON 格式回覆
        response_text = response.text
        llm_decision = json.loads(response_text).get("response", "").strip()

        print(f"🤖 AI 老師判定: {llm_decision}")
        
        # 根據 AI 的回覆（不區分大小寫）來判斷對錯
        if "correct" in llm_decision.lower():
            return True
        else:
            return False

    except requests.exceptions.RequestException:
        # 如果無法連接 AI (例如 Ollama 沒開)，則退回到手動模式
        print(f"\n錯誤：無法連接到 Ollama API。請確認 Ollama 服務正在運行。")
        feedback = input("請手動判斷是否正確 (y/n): ").lower()
        return feedback == 'y'

def initialize_quiz_data():
    """
    載入主詞頻資料庫和使用者單字表，合併並初始化權重。
    (此函式保持不變)
    """
    try:
        df_master = pd.read_csv(MASTER_DB_FILE)
        df_user = pd.read_csv(USER_LIST_FILE)
    except FileNotFoundError as e:
        print(f"錯誤：找不到檔案 {e.filename}。請確保檔案存在於同一個資料夾中。")
        return None

    df_quiz = pd.merge(df_user, df_master[['arabic_word', 'frequency']], on='arabic_word', how='left')
    df_quiz['frequency'] = df_quiz['frequency'].fillna(1)
    df_quiz['current_weight'] = df_quiz['frequency']
    df_quiz['correct_count'] = 0
    df_quiz['is_mastered'] = False
    print("單字表初始化完成！")
    return df_quiz

def run_quiz(df_quiz):
    """
    執行主抽考循環 (已升級為 AI 批改)。
    """
    while not df_quiz['is_mastered'].all():
        clear_screen()
        
        active_words = df_quiz[df_quiz['is_mastered'] == False]
        chosen_word = active_words.sample(n=1, weights='current_weight').iloc[0]
        index = chosen_word.name

        mastered_count = df_quiz['is_mastered'].sum()
        total_count = len(df_quiz)
        print(f"進度: {mastered_count} / {total_count} 個單字已精通\n")
        
        print(f"阿拉伯文: {chosen_word['arabic_word']}")
        print("---")
        
        # 【修改點 1】讓使用者直接輸入答案
        user_answer = input("請輸入您的翻譯: ")
        
        # 【修改點 2】呼叫新的 AI 批改函式，取代手動 y/n
        is_correct = grade_answer_with_llm(
            question_word=chosen_word['arabic_word'],
            correct_answer=chosen_word['translation'],
            user_answer=user_answer
        )

        # --- 更新權重和計數器 (邏輯與之前相同) ---
        if is_correct:
            df_quiz.at[index, 'correct_count'] += 1
            df_quiz.at[index, 'current_weight'] = max(1, df_quiz.at[index, 'current_weight'] / 5)
            print(f"太棒了！'{chosen_word['arabic_word']}' 已答對 {df_quiz.at[index, 'correct_count']} 次。")
        else:
            df_quiz.at[index, 'current_weight'] *= 2
            print(f"別灰心，參考答案是 '{chosen_word['translation']}'。多練習幾次！")

        if df_quiz.at[index, 'correct_count'] >= WIN_CONDITION:
            df_quiz.at[index, 'is_mastered'] = True
            print(f"恭喜！'{chosen_word['arabic_word']}' 已精通！")
        
        input("\n--- 按 Enter 繼續下一個單字 ---")

    print("\n🎉🎉🎉 恭喜您！已完成本次所有的單字學習！🎉🎉🎉")

# --- 主程式執行區 ---
if __name__ == "__main__":
    quiz_data = initialize_quiz_data()
    if quiz_data is not None:
        run_quiz(quiz_data)