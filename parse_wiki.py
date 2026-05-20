import gensim.corpora
from gensim.corpora.wikicorpus import extract_pages, tokenize
import time
import bz2

# 下載的維基百科檔案路徑 (不需要解壓縮)
WIKI_DUMP_FILE = 'arwiki-latest-pages-articles-multistream.xml'
# 處理後輸出的純文字檔案
OUTPUT_FILE = 'wiki_arabic_text.txt'

def process_wiki_dump():
    """
    使用 gensim 將維基百科的 dump 檔案轉換為純文字檔。
    """
    print(f"開始處理維基百科檔案: {WIKI_DUMP_FILE}...")
    
    start_time = time.time()
    article_count = 0
    
    try:
        # Determine if the file is compressed with BZ2
        with open(WIKI_DUMP_FILE, 'rb') as f:
            header = f.read(3)
        
        if header == b'BZh':
            input_f = bz2.BZ2File(WIKI_DUMP_FILE)
            print("檢測到 BZ2 壓縮格式...")
        else:
            input_f = open(WIKI_DUMP_FILE, 'rb')
            print("檢測到純 XML 格式...")

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as output_f:
            # 迭代處理每一篇文章
            for title, text, pageid in extract_pages(input_f):
                # tokenize the text using gensim's utility
                tokens = tokenize(text)
                # 將文章中的單字用空格連接成一個字串，並在結尾加上換行符
                output_f.write(' '.join(tokens) + '\n')
                article_count += 1
                if article_count % 10000 == 0:
                    elapsed = time.time() - start_time
                    print(f"已處理 {article_count} 篇文章 (耗時: {elapsed:.1f} 秒)...")
        
        input_f.close()
    except Exception as e:
        print(f"處理過程中發生錯誤: {e}")
        return

    print(f"處理完成！總共處理了 {article_count} 篇文章。")
    print(f"純文字已儲存至: {OUTPUT_FILE}")

# --- 主程式執行區 ---
if __name__ == "__main__":
    start_time = time.time()
    process_wiki_dump()
    end_time = time.time()
    print(f"總共耗時: {end_time - start_time:.2f} 秒")