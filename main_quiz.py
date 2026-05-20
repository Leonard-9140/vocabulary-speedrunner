import pandas as pd
import random
import os
import requests # 引入我們的通訊工具
import json     # 用於解析 AI 的回覆

# --- 設定 ---
MASTER_DB_FILE = "voc_database.csv"  # 我們的通用詞頻資料庫
USER_LIST_FILE = "exam_list.csv"     # 使用者提供的考試單字表
WIN_CONDITION = 5                    # 每個單字需要答對幾次才算完成
OLLAMA_MODEL = "gemma3:4b"            # 指定使用 gemma3:4b 模型，以確保穩定的語義辨識能力
OLLAMA_API_ENDPOINT = "http://localhost:11434/api/generate"

def clear_screen():
    """清除終端機畫面，讓介面更清爽"""
    os.system('cls' if os.name == 'nt' else 'clear')

def grade_answer_with_llm(target_arabic, chinese_meaning, user_arabic, all_arabic_words):
    """
    反向批改：檢查使用者的阿拉伯語拼寫是否正確。
    """
    # --- 1. 交叉比對 (Cross-Check) ---
    # 如果使用者回答的是清單中「其他單字」的阿拉伯文，直接判定為錯誤
    if user_arabic in all_arabic_words and user_arabic != target_arabic:
        print(f"🎯 偵測到交叉錯誤：你輸入的是清單中另一個單字的阿拉伯文。")
        return False

    # --- 2. 設計給 LLM 的指令 (專注於阿拉伯語拼寫與語義) ---
    prompt = f"""你是一位專業的阿拉伯語導師。
目前的測驗目標是根據中文意思寫出正確的阿拉伯單字。

中文意思："{chinese_meaning}"
預期正確阿拉伯單字："{target_arabic}"
學生輸入的阿拉伯單字："{user_arabic}"

判定標準：
1. 如果學生輸入的單字與預期單字完全相同（包含或不包含發音符號），判定為 "Correct"。
2. 如果學生輸入的單字有輕微的拼寫錯誤（例如：漏掉一個字母、字母順序顛倒），但明顯是在寫同一個詞，請判定為 "Correct" 並給出修正建議。
3. 如果輸入的單字是該詞的語義相近詞（例如：語根相同但型態略有不同），也請判定為 "Correct"。
4. 如果單字完全錯誤，判定為 "Incorrect"。

請回覆格式如下：
Decision: [Correct/Incorrect]
Feedback: [簡短的修正建議，若完全正確則寫 None]
"""
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False 
    }

    try:
        response = requests.post(OLLAMA_API_ENDPOINT, json=payload)
        response.encoding = 'utf-8'
        response.raise_for_status() 
        
        result_json = response.json()
        llm_response = result_json.get("response", "").strip()

        # 解析 Decision
        decision_line = [line for line in llm_response.split('\n') if "Decision:" in line]
        llm_decision = decision_line[0].replace("Decision:", "").strip() if decision_line else llm_response

        # 解析 Feedback
        feedback_line = [line for line in llm_response.split('\n') if "Feedback:" in line]
        feedback = feedback_line[0].replace("Feedback:", "").strip() if feedback_line else ""

        print(f"🤖 AI 老師判定: {llm_decision}")
        if feedback and feedback.lower() != "none":
            print(f"📝 老師建議: {feedback}")
        
        if "correct" in llm_decision.lower() and "incorrect" not in llm_decision.lower():
            return True
        else:
            return False

    except Exception as e:
        print(f"\nAI 批改發生錯誤：{e}")
        feedback = input("請手動判斷阿拉伯文是否正確 (y/n): ").lower()
        return feedback == 'y'

def initialize_quiz_data():
    """
    載入主詞頻資料庫和使用者單字表，合併並初始化權重。
    """
    try:
        # 明確指定使用 utf-8 編碼讀取 CSV
        df_master = pd.read_csv(MASTER_DB_FILE, encoding='utf-8')
        df_user = pd.read_csv(USER_LIST_FILE, encoding='utf-8')
    except FileNotFoundError as e:
        print(f"錯誤：找不到檔案 {e.filename}。請確保檔案存在於同一個資料夾中。")
        return None
    except UnicodeDecodeError:
        # 如果 utf-8 失敗，嘗試 utf-8-sig (處理帶 BOM 的檔案)
        try:
            df_master = pd.read_csv(MASTER_DB_FILE, encoding='utf-8-sig')
            df_user = pd.read_csv(USER_LIST_FILE, encoding='utf-8-sig')
        except Exception as e:
            print(f"讀取 CSV 發生編碼錯誤：{e}")
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
    執行主抽考循環 (反向模式：看中文寫阿拉伯文)。
    """
    while not df_quiz['is_mastered'].all():
        clear_screen()
        
        active_words = df_quiz[df_quiz['is_mastered'] == False]
        chosen_word = active_words.sample(n=1, weights='current_weight').iloc[0]
        index = chosen_word.name

        mastered_count = df_quiz['is_mastered'].sum()
        total_count = len(df_quiz)
        print(f"進度: {mastered_count} / {total_count} 個單字已精通\n")
        
        # 顯示中文作為題目
        print(f"中文意思: {chosen_word['translation']}")
        print("---")
        
        # 讓使用者輸入阿拉伯文
        try:
            user_answer = input("請輸入對應的阿拉伯文: ").strip()
        except UnicodeDecodeError:
            print("輸入錯誤，請重試。")
            continue
        
        # 0. 檢查空輸入
        if not user_answer:
            print("⚠️ 您沒有輸入任何內容。")
            is_correct = False
        # 1. 先進行快速判斷 (完全一致時不需要 AI)
        elif user_answer == chosen_word['arabic_word']:
            is_correct = True
            print("✨ 完全正確！")
        else:
            # 2. 準備背景資訊進行交叉比對
            all_arabic_words = df_quiz['arabic_word'].tolist()
            
            # 3. 呼叫 AI 批改 (處理拼寫錯誤或變體)
            is_correct = grade_answer_with_llm(
                target_arabic=chosen_word['arabic_word'],
                chinese_meaning=chosen_word['translation'],
                user_arabic=user_answer,
                all_arabic_words=all_arabic_words
            )

        if is_correct:
            df_quiz.at[index, 'correct_count'] += 1
            df_quiz.at[index, 'current_weight'] = max(1, df_quiz.at[index, 'current_weight'] / 5)
            # 顯示正確答案的 RTL 格式以供參考
            correct_rtl = f"\u202B{chosen_word['arabic_word']}\u202C"
            print(f"✅ 判定正確！目前已答對 {df_quiz.at[index, 'correct_count']} 次。")
            print(f"正確單字：{correct_rtl}")
        else:
            df_quiz.at[index, 'current_weight'] *= 2
            correct_rtl = f"\u202B{chosen_word['arabic_word']}\u202C"
            print(f"❌ 判定錯誤。請參考正確寫法：{correct_rtl}")

        if df_quiz.at[index, 'correct_count'] >= WIN_CONDITION:
            df_quiz.at[index, 'is_mastered'] = True
            print(f"恭喜！單字「{chosen_word['translation']}」已精通！")
        
        input("\n--- 按 Enter 繼續下一個單字 ---")

    print("\n🎉🎉🎉 恭喜您！已完成本次所有的單字學習！🎉🎉🎉")

# --- 主程式執行區 ---
if __name__ == "__main__":
    quiz_data = initialize_quiz_data()
    if quiz_data is not None:
        run_quiz(quiz_data)