import re
import csv
from collections import Counter
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import time

def analyze_large_arabic_text_safely(filepath):
    """
    Analyzes a very large Arabic text file in a memory-efficient way
    by processing it line by line.

    Args:
        filepath (str): UTF-8 encoded text file path.

    Returns:
        list: A list of (word, count) tuples, sorted by frequency.
    """
    print(f"開始安全地分析大型檔案: {filepath} (逐行處理)...")
    
    # Initialize a Counter object to store frequencies
    frequency_counter = Counter()
    
    # Pre-compile regex and get stopwords for efficiency
    arabic_stopwords = set(stopwords.words('arabic'))
    arabic_pattern = re.compile(r'^[\u0600-\u06FF]+$')
    
    line_count = 0
    start_time = time.time()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Loop through each line in the file
            for line in f:
                # 1. Tokenize the current line
                tokens = word_tokenize(line)
                
                # 2. Clean the tokens from this line
                cleaned_tokens = [
                    token for token in tokens 
                    if arabic_pattern.match(token) and token not in arabic_stopwords
                ]
                
                # 3. Update the master frequency counter with the tokens from this line
                frequency_counter.update(cleaned_tokens)
                
                line_count += 1
                if line_count % 500000 == 0: # Print progress every 500,000 lines
                    print(f"  ...已處理 {line_count:,} 行")

    except FileNotFoundError:
        print(f"錯誤：找不到檔案 '{filepath}'")
        return None
    
    end_time = time.time()
    print(f"檔案讀取與詞頻計算完成！總共處理 {line_count:,} 行，耗時 {end_time - start_time:.2f} 秒。")
    
    # Return the sorted list of most common words
    return frequency_counter.most_common()

def save_to_csv(word_frequencies, filename="voc_database.csv", limit=5000):
    """
    Saves the top N word frequencies to a CSV file.
    """
    print(f"準備將前 {limit} 個單字儲存至 {filename}...")
    headers = ['id', 'arabic_word', 'frequency', 'english_translation', 'chinese_translation', 'status']

    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for i, (word, count) in enumerate(word_frequencies[:limit], 1):
            row = [i, word, count, '', '', 'new']
            writer.writerow(row)
            
    print(f"成功儲存！您的單字資料庫 '{filename}' 已經建立。")

# --- 主程式執行區 ---
if __name__ == "__main__":
    file_to_analyze = 'wiki_arabic_text.txt'
    # Call the new memory-safe function
    word_frequencies = analyze_large_arabic_text_safely(file_to_analyze)

    if word_frequencies:
        save_to_csv(word_frequencies, limit=5000)