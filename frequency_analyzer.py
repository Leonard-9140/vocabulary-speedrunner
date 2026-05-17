import re
import csv
from collections import Counter
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import time
import os

# Try to import gensim for direct Wiki analysis
try:
    from gensim.corpora import WikiCorpus
    HAS_GENSIM = True
except ImportError:
    HAS_GENSIM = False

def analyze_large_arabic_text_safely(filepath):
    """
    Analyzes a very large Arabic text file in a memory-efficient way
    by processing it line by line.
    """
    print(f"開始安全地分析大型檔案: {filepath} (逐行處理)...")
    
    frequency_counter = Counter()
    arabic_stopwords = set(stopwords.words('arabic'))
    arabic_pattern = re.compile(r'^[\u0600-\u06FF]+$')
    
    line_count = 0
    start_time = time.time()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                tokens = word_tokenize(line)
                cleaned_tokens = [
                    token for token in tokens 
                    if arabic_pattern.match(token) and token not in arabic_stopwords
                ]
                frequency_counter.update(cleaned_tokens)
                
                line_count += 1
                if line_count % 500000 == 0:
                    print(f"  ...已處理 {line_count:,} 行")

    except FileNotFoundError:
        print(f"錯誤：找不到檔案 '{filepath}'")
        return None
    
    end_time = time.time()
    print(f"檔案讀取與詞頻計算完成！總共處理 {line_count:,} 行，耗時 {end_time - start_time:.2f} 秒。")
    return frequency_counter.most_common()

def analyze_wiki_dump_safely(filepath):
    """
    Directly analyzes a Wikipedia XML dump without creating intermediate files.
    """
    if not HAS_GENSIM:
        print("錯誤：未安裝 gensim，無法直接分析維基百科 XML。請先安裝 gensim。")
        return None

    print(f"開始直接分析維基百科 XML: {filepath}...")
    
    frequency_counter = Counter()
    arabic_stopwords = set(stopwords.words('arabic'))
    arabic_pattern = re.compile(r'^[\u0600-\u06FF]+$')
    
    start_time = time.time()
    article_count = 0

    try:
        # gensim's WikiCorpus automatically handles decompression and XML parsing
        wiki = WikiCorpus(filepath, dictionary={})
        
        for text in wiki.get_texts():
            # text is a list of tokens already processed by gensim
            cleaned_tokens = [
                token for token in text
                if arabic_pattern.match(token) and token not in arabic_stopwords
            ]
            frequency_counter.update(cleaned_tokens)
            
            article_count += 1
            if article_count % 10000 == 0:
                print(f"  ...已處理 {article_count:,} 篇文章")

    except Exception as e:
        print(f"處理過程中發生錯誤: {e}")
        return None
    
    end_time = time.time()
    print(f"維基百科分析完成！總共處理 {article_count:,} 篇文章，耗時 {end_time - start_time:.2f} 秒。")
    return frequency_counter.most_common()

def save_to_csv(word_frequencies, filename="voc_database.csv", limit=5000):
    """
    Saves the top N word frequencies to a CSV file.
    """
    if not word_frequencies:
        print("沒有可儲存的數據。")
        return

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
    # 使用者提供的維基百科 XML 檔案路徑
    wiki_dump_file = 'arwiki-latest-pages-articles-multistream.xml'
    
    if os.path.exists(wiki_dump_file):
        # 優先直接分析 XML (更有效率且省空間)
        word_frequencies = analyze_wiki_dump_safely(wiki_dump_file)
    else:
        # 如果 XML 不存在，退而求其次嘗試分析已轉換的純文字檔
        text_file = 'wiki_arabic_text.txt'
        word_frequencies = analyze_large_arabic_text_safely(text_file)

    if word_frequencies:
        save_to_csv(word_frequencies, limit=5000)