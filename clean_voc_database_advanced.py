import pandas as pd
import qalsadi.lemmatizer
import os
import sys

def clean_database_advanced(input_file="voc_database.csv", output_file="voc_database.csv"):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)
    original_count = len(df)

    print("Initializing Lemmatizer...")
    lemmer = qalsadi.lemmatizer.Lemmatizer()

    # Wikipedia and metadata blacklist (Lemmas)
    blacklist = {
        # Wiki Meta
        'تصنيف', 'ويكيبيديا', 'بذرة', 'تحويلة', 'تحويل', 'قالب', 'كومنز', 'روابط', 'وصلات', 
        'بوابة', 'بوابات', 'توضيح', 'مستخدم', 'المستخدم', 'نقاش', 'يتيمة', 'أعلام', 'مؤرشفة',
        'ويكي', 'بويكي', 'مقالة', 'مقالات', 'اقتباس', 'مرجع', 'مراجع', 'المراجع', 'المصدر',
        'مخفي', 'أيقونة', 'شعار', 'تصغير', 'ملخص', 'تصفح', 'وصلة', 'رد', 'انظر', 'مساهم',
        
        # Template Parameters and metadata
        'مسار', 'أرشيف', 'عنوان', 'العنوان', 'استشهاد', 'الوصول', 'ناشر', 'لغة', 'اللغة',
        'موقع', 'الموقع', 'اسم', 'الاسم', 'بويب', 'الأخير', 'الأول', 'معلومات', 'المعلومات',
        'شريط', 'ملف', 'رمز', 'الرمز', 'صندوق', 'صحيفة', 'المجلد', 'العدد', 'ردمك', 'تاريخ',
        'عام', 'سنة', 'السنة', 'شهور', 'يوم', 'اليوم', 'ساعة', 'دقيقة', 'ثانية', 'وقت', 'الوقت',
        'مواليد', 'وفيات', 'الولادة', 'الوفاة', 'تأسيس', 'التأسيس', 'تأسست', 'تأسيسات',
        'توقيت', 'التوقيت', 'إحداثيات', 'بيانات', 'تحديث', 'الرسمي', 'الرسمية', 'ضبط',
        'استنادي', 'نسخة', 'النسخة', 'طبعة', 'إصدار', 'الإصدار', 'ترخيص', 'حجم', 'بديلة',
        'تلقائيا', 'إنج', 'جغرافيا', 'خريطة', 'الخريطة', 'بدورية', 'المجلد', 'سطر', 'السطر',
        'المعرف', 'معرف', 'معرفات', 'صيغة', 'بطاقة', 'وصف', 'الوصف', 'ملاحظة', 'ملاحظات',
        'إضافة', 'حذف', 'تعديل', 'التعديل', 'تغيير', 'نطاق', 'نص', 'النص', 'نصي', 'أقواس',
        'وسائل', 'إعلام', 'نشر', 'النشر', 'قاعدة', 'بيانات', 'موضوع', 'الموضوع', 'بحث', 'البحث',
        
        # Geographic/Census Meta (often bot-generated)
        'تعداد', 'سكان', 'السكان', 'مديرية', 'عزلة', 'دوار', 'دواوير', 'المندوبية', 'القاطنين',
        'للفرد', 'المساكن', 'سرشماری', 'كثافة', 'الكثافة', 'مساحة', 'المساحة', 'دائرة',
        'تجمعات', 'للسكان', 'متوسط', 'مأهولة', 'الناتج', 'السكاني', 'الريفي', 'محافظة',
        'إقليم', 'منطقة', 'مركز', 'بلدية', 'بلديات', 'قرية', 'القرية', 'محافظات', 'ناحية',
        
        # Technical/Asteroid/Celestial (common in Wiki)
        'كويكب', 'كويكبات', 'الكويكبات', 'جرم', 'أجرام', 'فلكي', 'الفلكي', 'فلكية', 'مدار',
        'مداري', 'الشمسي', 'الكواكب', 'كوكب', 'سطح', 'قطر', 'ارتفاع', 'الارتفاع', 'ميل',
        
        # functional words that might have escaped stopwords
        'تم', 'بلغ', 'بلغت', 'يتم', 'تقع', 'عندما', 'يكون', 'تكون', 'ضمن', 'أنه', 'أنها',
        'وهي', 'وهو', 'آخر', 'أخرى', 'بينما', 'يمكن', 'وقد', 'وفي', 'وهذا', 'عنه', 'بأنه',
        'منهم', 'تشمل', 'عرف', 'إليه', 'ظهر', 'ظهرت', 'توجد', 'تبلغ', 'يعيش', 'عبارة',
        'تحتوي', 'يظهر', 'ويمكن', 'ينتمي', 'يعمل', 'يعتبر', 'تعتبر', 'يلي', 'بشأن', 'صدر',
        'إليها', 'وضح', 'وجه', 'أعلنت', 'لهذه', 'لهذا', 'ظل', 'يحدث', 'يعد', 'تعد', 'فقد',
        'حوالي', 'أصبح', 'أصبحت', 'خلال', 'بسبب', 'أيضا', 'حيث', 'نحو', 'إذ', 'إذا', 'سواء',
        'قبل', 'بعد', 'تحت', 'بين', 'فوق', 'عبر', 'حول', 'ضد', 'منذ', 'لدى', 'لديها', 'لدينا',
    }

    print("Lemmatizing and aggregating frequencies...")
    lemma_data = {}
    
    total = len(df)
    for index, row in df.iterrows():
        word = str(row['arabic_word'])
        freq = row['frequency']
        
        # Get lemma
        lemma = lemmer.lemmatize(word)
        
        # Basic cleanup: remove marks (diacritics are usually handled by lemmatizer but let's be safe)
        if lemma in blacklist:
            continue
            
        if lemma not in lemma_data:
            lemma_data[lemma] = 0
        lemma_data[lemma] += freq
        
        if (index + 1) % 500 == 0:
            print(f"  Processed {index + 1}/{total} words...")

    # Convert aggregated data back to list for DataFrame
    cleaned_rows = []
    for lemma, freq in lemma_data.items():
        # Remove single character lemmas (avoiding punctuation or isolated particles)
        if len(lemma) <= 1:
            continue
        cleaned_rows.append({'arabic_word': lemma, 'frequency': freq})

    df_cleaned = pd.DataFrame(cleaned_rows)
    
    # Sort by frequency and re-assign IDs
    df_cleaned = df_cleaned.sort_values(by='frequency', ascending=False)
    
    # Take top 5000 or all if less
    df_final = df_cleaned.head(5000).copy()
    df_final['id'] = range(1, len(df_final) + 1)
    df_final['english_translation'] = ''
    df_final['chinese_translation'] = ''
    df_final['status'] = 'new'
    
    # Reorder columns
    df_final = df_final[['id', 'arabic_word', 'frequency', 'english_translation', 'chinese_translation', 'status']]

    print(f"Original count: {original_count}")
    print(f"Final count: {len(df_final)}")
    
    df_final.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"Cleaned database saved to {output_file}")

if __name__ == "__main__":
    clean_database_advanced()
