import io
import json
import os
import threading
import webbrowser

from flask import Flask, render_template, request, redirect, url_for, send_file

app = Flask(__name__)
app.secret_key = os.urandom(32)

_QUAL_CLASSES = {
    'מאוד גבוה':      'q-very-high',
    'גבוה':           'q-high',
    'מעל הממוצע':     'q-above-avg',
    'ממוצע':          'q-average',
    'מתחת לממוצע':   'q-below-avg',
    'נמוך':           'q-low',
    'מאוד נמוך':      'q-very-low',
}

@app.template_filter('qual_class')
def qual_class(label: str) -> str:
    return _QUAL_CLASSES.get(label, 'q-average')

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(BASE_DIR, 'data')
REPORTS_DIR   = os.path.join(BASE_DIR, 'reports')
RESULTS_FILE  = os.path.join(REPORTS_DIR, '.last_results.json')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

EXTRACTION_PROMPT = """\
אתה עוזר של פסיכולוג/ית קלינית. התמונה המצורפת מציגה כרטיס תשובות של מבחן WISC-IV שמולא עבור נבדק.

חלץ את כל הציונים הגולמיים ופלוט אך ורק את ה-JSON הבא — ללא הסברים נוספים, ללא markdown:

{
  "child": {
    "name": "שם הנבדק",
    "dob": "YYYY-MM-DD",
    "exam_date": "YYYY-MM-DD",
    "examiner": "שם הבוחן",
    "school": "מסגרת חינוכית",
    "grade": "כיתה",
    "reason": "סיבת הפנייה"
  },
  "raw_scores": {
    "BD": null,
    "SI": null,
    "DS": {"forward": null, "backward": null, "total": null},
    "PCn": null,
    "CD": null,
    "VC": null,
    "LN": null,
    "MR": null,
    "CO": null,
    "SS": null,
    "PCm": null,
    "CA": {"random": null, "structured": null, "total": null},
    "IN": null,
    "AR": null,
    "WR": null
  }
}

כללים:
- החלף null בציון הגולמי השלם (מספר שלם) כפי שמופיע בכרטיס
- השאר null עבור כל מבחן שלא נערך
- עבור DS: forward = ספרות קדמי, backward = ספרות אחורי, total = סכום שניהם
- עבור CA: random = ביטול אקראי, structured = ביטול מובנה, total = סכום שניהם
- פורמט תאריכים: YYYY-MM-DD
- פלוט אך ורק JSON תקני, ללא כל טקסט נוסף"""


# ── startup ───────────────────────────────────────────────────────────────────

def _ensure_dirs():
    os.makedirs(DATA_DIR,    exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    raw_path  = os.path.join(DATA_DIR, 'norms_raw_scaled.json')
    comp_path = os.path.join(DATA_DIR, 'norms_sum_composite.json')

    if not os.path.exists(raw_path):
        subtests    = ['BD','SI','DS','PCn','CD','VC','LN','MR','CO','SS',
                       'PCm','CA','IN','AR','WR']
        age_groups  = [f"{y}:{g*4}-{y}:{g*4+3}"
                       for y in range(6, 17) for g in range(3)]
        skeleton    = {st: {ag: {} for ag in age_groups} for st in subtests}
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(skeleton, f, ensure_ascii=False, indent=2)

    if not os.path.exists(comp_path):
        skeleton = {idx: {} for idx in ['VCI', 'PRI', 'WMI', 'PSI', 'FSIQ']}
        with open(comp_path, 'w', encoding='utf-8') as f:
            json.dump(skeleton, f, ensure_ascii=False, indent=2)


def _save(results: dict):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)


def _load() -> dict | None:
    if not os.path.exists(RESULTS_FILE):
        return None
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


# ── routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', prompt=EXTRACTION_PROMPT)


@app.route('/calculate', methods=['POST'])
def calculate():
    raw_json = request.form.get('json_data', '').strip()
    if not raw_json:
        return render_template('index.html', prompt=EXTRACTION_PROMPT,
                               error='אנא הדבק את פלט ה-JSON')
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        return render_template('index.html', prompt=EXTRACTION_PROMPT,
                               error=f'JSON לא תקין: {e}')

    from scoring.calculator import calculate_all
    try:
        results = calculate_all(data)
    except Exception as e:
        return render_template('index.html', prompt=EXTRACTION_PROMPT,
                               error=f'שגיאה בחישוב: {e}')

    _save(results)
    return render_template('results.html', r=results)


@app.route('/export/word')
def export_word():
    results = _load()
    if not results:
        return redirect(url_for('index'))

    from scoring.report import generate_docx
    docx_bytes = generate_docx(results)

    name     = results['child'].get('name', 'נבדק').replace(' ', '_')
    filename = f"WISC4_{name}.docx"
    return send_file(
        io.BytesIO(docx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=filename,
    )


@app.route('/export/pdf')
def export_pdf():
    results = _load()
    if not results:
        return redirect(url_for('index'))

    try:
        from scoring.report import generate_pdf
        pdf_bytes = generate_pdf(results, TEMPLATES_DIR)
    except Exception as e:
        return render_template('results.html', r=results,
                               pdf_error=f'שגיאת PDF: {e}. פתח את קובץ ה-Word ושמור כ-PDF.')

    name     = results['child'].get('name', 'נבדק').replace(' ', '_')
    filename = f"WISC4_{name}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


@app.route('/results')
def show_results():
    results = _load()
    if not results:
        return redirect(url_for('index'))
    return render_template('results.html', r=results)


# ── entry point ───────────────────────────────────────────────────────────────

def _open_browser():
    import time
    time.sleep(1.5)
    webbrowser.open('http://localhost:5000')


if __name__ == '__main__':
    _ensure_dirs()
    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=5000, debug=False)
