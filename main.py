import os
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai  # مكتبة جوجل الرسمية الحديثة للتعامل مع Gemini
from pypdf import PdfReader
from docx import Document
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# الحل هنا: أضف هذا الجزء تماماً كما هو
origins = ["*"] # بيسمح لأي موقع يكلم السيرفر (للتجربة)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# تهيئة عميل جوجل أيه آي (تأكد من وضع المفتاح في Environment Variables)
# يمكنك استخدام Google Gemini API المجاني تماماً عبر Google AI Studio
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def extract_text_from_file(file: UploadFile) -> str:
  filename = file.filename.lower()
  content = ""
  try:
    if filename.endswith(".pdf"):
      reader = PdfReader(file.file)
      for page in reader.pages:
        text = page.extract_text()
        if text:
          content += text + "\n"
    elif filename.endswith(".docx"):
      doc = Document(file.file)
      for para in doc.paragraphs:
        content += para.text + "\n"
    elif filename.endswith(".txt"):
      content = file.file.read().decode("utf-8")
    else:
      raise HTTPException(
          status_code=400, detail="صيغة الملف غير مدعومة. استخدم PDF أو Word."
      )
  except Exception as e:
    raise HTTPException(
        status_code=400, detail=f"فشل قراءة الملف: str(e)"
    )
  return content


@app.post("/api/analyze")
async def analyze_cv(
    job_title: str = Form(...),
    job_details: str = Form(None),
    file: UploadFile = File(None),
    gdrive_link: str = Form(None),
):
  cv_text = ""

  if file:
    cv_text = extract_text_from_file(file)
  elif gdrive_link:
    # ملاحظة: روابط غوغل درايف تتطلب صلاحيات عامة أو تحويلها لرابط تحميل مباشر
    cv_text = f"محتوى تم جلبه من رابط غوغل درايف: {gdrive_link}"
  else:
    raise HTTPException(
        status_code=400,
        detail="الرجاء رفع ملف السيرة الذاتية أو إدخال رابط غوغل درايف.",
    )

  # ضبط الـ Prompt لمنع الهلوسة وإجبار النتيجة بصيغة منظمة
  prompt = f"""
    أنت نظام ذكي ومحترف لفلترة وتوظيف السير الذاتية (ATS).
    قم بتحليل السيرة الذاتية التالية مقارنة بالوظيفة المطلوبة بدقة شديدة وموضوعية تامة.
    لا تخترع أو تهلوس أي معلومات غير موجودة في النص. إذا لم تتوفر معلومة اذكر ذلك.

    اسم الوظيفة: {job_title}
    تفاصيل وملاحظات الوظيفة: {job_details if job_details else "لا توجد تفاصيل إضافية"}

    نص السيرة الذاتية:
    {cv_text[:4000]}  # أخذ جزء مناسب من النص لضمان الكفاءة

    قم بإرجاع النتيجة حصراً بصيغة JSON صحيحة تحتوي على الحقول التالية:
    - match_score: (رقم صحيح من 0 إلى 100 يعبر عن نسبة التوافق)
    - verdict: ("مقبول مبدئياً" أو "تحت المراجعة" أو "غير مناسب")
    - strengths: (قائمة تحتوي على نقاط القوة البارزة للمرشح)
    - gaps: (قائمة تحتوي على المهارات أو النقاط الناقصة مقارنة بالوظيفة)
    - summary: (ملخص احترافي لتقييم المتقدم في حدود سطرين أو ثلاثة)
    """

  try:
    # استدعاء نموذج Gemini للتحليل
    response = client.models.generate_content(
        model="gemini-3.6-flash",  # أو gemini-1.5-flash حسب المتاح لديك
        contents=prompt,
    )

    # تنظيف مخرجات الـ AI واستخراج الـ JSON
    import json
    import re

    raw_text = response.text
    # استخراج الـ JSON من الرد في حال وُجدت نصوص إضافية
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if json_match:
      result_json = json.loads(json_match.group(0))
    else:
      # فالباك في حال أخطأ النموذج التنسيق
      result_json = {
          "match_score": 50,
          "verdict": "تحت المراجعة",
          "strengths": ["تعذر تحليل النقاط بدقة"],
          "gaps": ["يرجى إعادة المحاولة"],
          "summary": raw_text,
      }

    return {"success": True, "data": result_json}

  except Exception as e:
    raise HTTPException(
        status_code=500, detail=f"حدث خطأ أثناء معالجة الذكاء الاصطناعي: {str(e)}"
    )


import os
import uvicorn

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 8000))
  uvicorn.run("main:app", host="0.0.0.0", port=port)
