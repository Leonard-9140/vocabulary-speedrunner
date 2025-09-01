import gensim.corpora
import time

# 下載的維基百科檔案路徑 (不需要解壓縮)
WIKI_DUMP_FILE = 'arwiki-latest-pages-articles.xml.bz2'
# 處理後輸出的純文字檔案
OUTPUT_FILE = 'wiki_arabic_text.txt'

def process_wiki_dump():
    """
    使用 gensim 將維基百科的 dump 檔案轉換為純文字檔。
    """
    print(f"開始處理維基百科檔案: {WIKI_DUMP_FILE}...")
    
    # gensim 的 WikiCorpus 物件，用於解析維基百科 dump
    # lemmatize=False 表示不做詞形還原，我們先取得原始詞彙
    wiki = gensim.corpora.WikiCorpus(WIKI_DUMP_FILE, dictionary={})
    
    article_count = 0
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as output_f:
        # 迭代處理每一篇文章
        for text in wiki.get_texts():
            # 將文章中的單字用空格連接成一個字串，並在結尾加上換行符
            output_f.write(' '.join(text) + '\n')
            article_count += 1
            if article_count % 10000 == 0:
                print(f"已處理 {article_count} 篇文章...")

    print(f"處理完成！總共處理了 {article_count} 篇文章。")
    print(f"純文字已儲存至: {OUTPUT_FILE}")

# --- 主程式執行區 ---
if __name__ == "__main__":
    start_time = time.time()
    process_wiki_dump()
    end_time = time.time()
    print(f"總共耗時: {end_time - start_time:.2f} 秒")