import json
import os
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

_norms_raw = None
_norms_composite = None


def _load_raw():
    global _norms_raw
    if _norms_raw is None:
        path = os.path.join(DATA_DIR, 'norms_raw_scaled.json')
        with open(path, 'r', encoding='utf-8') as f:
            _norms_raw = json.load(f)
    return _norms_raw


def _load_composite():
    global _norms_composite
    if _norms_composite is None:
        path = os.path.join(DATA_DIR, 'norms_sum_composite.json')
        with open(path, 'r', encoding='utf-8') as f:
            _norms_composite = json.load(f)
    return _norms_composite


INDEX_SUBTESTS = {
    'VCI':  ['SI', 'VC', 'CO'],
    'PRI':  ['BD', 'PCn', 'MR'],
    'WMI':  ['DS', 'LN'],
    'PSI':  ['CD', 'SS'],
    'FSIQ': ['BD', 'SI', 'DS', 'PCn', 'CD', 'VC', 'LN', 'MR', 'CO', 'SS'],
}

SUBTEST_NAMES = {
    'BD':  'בניין קוביות',
    'SI':  'דמיון',
    'DS':  'ספרות',
    'PCn': 'מושגים בתמונות',
    'CD':  'קידוד',
    'VC':  'אוצר מילים',
    'LN':  'אותיות וספרות',
    'MR':  'מטריצות',
    'CO':  'הבנה',
    'SS':  'חיפוש סמלים',
    'PCm': 'השלמת תמונות',
    'CA':  'ביטול',
    'IN':  'ידיעות',
    'AR':  'חשבון',
    'WR':  'הסקה מילולית',
}

INDEX_NAMES = {
    'VCI':  'הבנה מילולית',
    'PRI':  'הסקה תפיסתית',
    'WMI':  'זיכרון עבודה',
    'PSI':  'מהירות עיבוד',
    'FSIQ': 'מנת משכל כוללת',
}

CORE_SUBTESTS = ['BD', 'SI', 'DS', 'PCn', 'CD', 'VC', 'LN', 'MR', 'CO', 'SS']
SUPPLEMENTAL_SUBTESTS = ['PCm', 'CA', 'IN', 'AR', 'WR']
ALL_SUBTESTS = CORE_SUBTESTS + SUPPLEMENTAL_SUBTESTS

# Subtests that have two scoreable sub-components
SUB_SCORE_META = {
    'DS': {
        'key_a': 'forward',   'key_b': 'backward',
        'label_a': 'קדמי',    'label_b': 'אחורי',
    },
    'CA': {
        'key_a': 'random',    'key_b': 'structured',
        'label_a': 'אקראי',   'label_b': 'מובנה',
    },
}


# ── age helpers ──────────────────────────────────────────────────────────────

def get_age(dob_str: str, exam_date_str: str) -> tuple:
    dob  = date.fromisoformat(dob_str)
    exam = date.fromisoformat(exam_date_str)
    years  = exam.year  - dob.year
    months = exam.month - dob.month
    if exam.day < dob.day:
        months -= 1
    if months < 0:
        months += 12
        years  -= 1
    return years, months


def get_age_group(years: int, months: int) -> str:
    start = (months // 4) * 4
    return f"{years}:{start}-{years}:{start + 3}"


def age_str_he(years: int, months: int) -> str:
    return f"{years} שנים ו-{months} חודשים"


# ── qualitative descriptors ───────────────────────────────────────────────────

COMPOSITE_LABELS = [
    (130, 'מאוד גבוה'),
    (120, 'גבוה'),
    (110, 'מעל הממוצע'),
    (90,  'ממוצע'),
    (80,  'מתחת לממוצע'),
    (70,  'נמוך'),
    (0,   'מאוד נמוך'),
]

SCALED_LABELS = [
    (17, 'מאוד גבוה'),
    (15, 'גבוה'),
    (13, 'מעל הממוצע'),
    (8,  'ממוצע'),
    (6,  'מתחת לממוצע'),
    (4,  'נמוך'),
    (0,  'מאוד נמוך'),
]


def qualitative_composite(score: int) -> str:
    for threshold, label in COMPOSITE_LABELS:
        if score >= threshold:
            return label
    return 'מאוד נמוך'


def qualitative_scaled(score: int) -> str:
    for threshold, label in SCALED_LABELS:
        if score >= threshold:
            return label
    return 'מאוד נמוך'


# ── norms lookups ─────────────────────────────────────────────────────────────

def raw_to_scaled(subtest: str, raw: int, age_group: str):
    return _load_raw().get(subtest, {}).get(age_group, {}).get(str(raw))


def sum_to_composite(index: str, total: int):
    return _load_composite().get(index, {}).get(str(total))


# ── main calculation ──────────────────────────────────────────────────────────

def calculate_all(data: dict) -> dict:
    child      = data.get('child', {})
    raw_scores = data.get('raw_scores', {})

    dob       = child.get('dob', '')
    exam_date = child.get('exam_date', '')

    years, months = get_age(dob, exam_date)
    age_group     = get_age_group(years, months)
    errors = []

    if not (6 <= years <= 16):
        errors.append(f"גיל {age_str_he(years, months)} מחוץ לטווח המבחן (6–16 שנים)")

    # ── subtests ──
    subtests = {}
    for code in ALL_SUBTESTS:
        val = raw_scores.get(code)
        if val is None:
            continue

        entry = {'code': code, 'name': SUBTEST_NAMES[code]}

        if code in SUB_SCORE_META:
            meta = SUB_SCORE_META[code]
            if isinstance(val, dict):
                sub_a     = val.get(meta['key_a'])
                sub_b     = val.get(meta['key_b'])
                raw_total = val.get('total')
                if raw_total is None and sub_a is not None and sub_b is not None:
                    raw_total = sub_a + sub_b
            else:
                sub_a = sub_b = None
                raw_total = int(val)

            entry['raw']       = raw_total
            entry['sub_a']     = sub_a
            entry['sub_b']     = sub_b
            entry['label_a']   = meta['label_a']
            entry['label_b']   = meta['label_b']
            if sub_a is not None and sub_b is not None:
                entry['sub_diff'] = sub_a - sub_b
        else:
            entry['raw'] = int(val)

        scaled = raw_to_scaled(code, entry['raw'], age_group) if entry['raw'] is not None else None
        entry['scaled'] = scaled
        if scaled is not None:
            entry['qualitative'] = qualitative_scaled(scaled)
        else:
            errors.append(f"{SUBTEST_NAMES[code]}: נורמות חסרות לקבוצת גיל {age_group}")

        subtests[code] = entry

    # ── composites ──
    composites = {}
    for idx, members in INDEX_SUBTESTS.items():
        sum_scaled = 0
        missing    = []
        for m in members:
            s = subtests.get(m, {}).get('scaled')
            if s is not None:
                sum_scaled += s
            else:
                missing.append(SUBTEST_NAMES.get(m, m))

        entry = {'code': idx, 'name': INDEX_NAMES[idx], 'sum': sum_scaled}

        if missing:
            entry['error'] = 'חסרים: ' + ', '.join(missing)
            composites[idx] = entry
            continue

        comp = sum_to_composite(idx, sum_scaled)
        if comp:
            entry.update(comp)
            entry['qualitative'] = qualitative_composite(comp['score'])
        else:
            entry['error'] = f"נורמות חסרות לסכום {sum_scaled}"
            errors.append(f"{INDEX_NAMES[idx]}: {entry['error']}")

        composites[idx] = entry

    discrepancies        = _discrepancies(composites)
    strengths, weaknesses = _sw(subtests)
    interpretation       = _interpret(child, composites, discrepancies, strengths, weaknesses)

    return {
        'child': {
            **child,
            'age_str':   age_str_he(years, months),
            'age_group': age_group,
        },
        'subtests':      subtests,
        'composites':    composites,
        'discrepancies': discrepancies,
        'strengths':     strengths,
        'weaknesses':    weaknesses,
        'interpretation': interpretation,
        'errors':        errors,
    }


# ── discrepancy analysis ──────────────────────────────────────────────────────

_DISC_PAIRS = [
    ('VCI', 'PRI'), ('VCI', 'WMI'), ('VCI', 'PSI'),
    ('PRI', 'WMI'), ('PRI', 'PSI'), ('WMI', 'PSI'),
]


def _discrepancies(composites: dict) -> list:
    result = []
    for a, b in _DISC_PAIRS:
        ca, cb = composites.get(a, {}), composites.get(b, {})
        sa, sb = ca.get('score'), cb.get('score')
        if sa is None or sb is None:
            continue
        diff = sa - sb
        result.append({
            'code_a': a,        'code_b': b,
            'name_a': ca['name'], 'name_b': cb['name'],
            'score_a': sa,      'score_b': sb,
            'diff':     diff,   'abs_diff': abs(diff),
            'significant': abs(diff) >= 15,
        })
    return result


# ── strengths / weaknesses ────────────────────────────────────────────────────

def _sw(subtests: dict):
    strengths, weaknesses = [], []
    for code in CORE_SUBTESTS:
        e = subtests.get(code)
        if not e or e.get('scaled') is None:
            continue
        s = e['scaled']
        if s >= 13:
            strengths.append({'code': code, 'name': e['name'], 'scaled': s})
        elif s <= 7:
            weaknesses.append({'code': code, 'name': e['name'], 'scaled': s})
    return strengths, weaknesses


# ── interpretive text ─────────────────────────────────────────────────────────

def _interpret(child, composites, discrepancies, strengths, weaknesses) -> dict:
    name  = child.get('name', 'הנבדק/ת')
    texts = {}

    fsiq = composites.get('FSIQ', {})
    if fsiq.get('score'):
        texts['fsiq'] = (
            f"{name} השיג/ה מנת משכל כוללת (FSIQ) של {fsiq['score']} "
            f"(אחוזון {fsiq.get('percentile', '—')}), "
            f"המשקפת רמת תפקוד קוגניטיבי {fsiq.get('qualitative', '')} "
            f"ביחס לבני/בנות גילו/ה."
        )

    for code, label in [('VCI', 'הבנה מילולית'), ('PRI', 'הסקה תפיסתית'),
                         ('WMI', 'זיכרון עבודה'),  ('PSI', 'מהירות עיבוד')]:
        c = composites.get(code, {})
        if c.get('score'):
            texts[code.lower()] = (
                f"ב{label} הגיע/ה {name} לציון {c['score']} "
                f"(אחוזון {c.get('percentile', '—')}), "
                f"המשקף ביצועים ב{c.get('qualitative', '')} ביחס לנורמה."
            )

    sig = [d for d in discrepancies if d['significant']]
    if sig:
        parts = [
            f"הפרש של {d['abs_diff']} נקודות בין {d['name_a']} ({d['score_a']}) "
            f"ל{d['name_b']} ({d['score_b']})"
            for d in sig
        ]
        texts['discrepancies'] = (
            "נמצאו הפרשים משמעותיים (15 נקודות ומעלה) בין המדדים: "
            + "; ".join(parts) + "."
        )
    else:
        texts['discrepancies'] = "לא נמצאו הפרשים משמעותיים בין המדדים."

    if strengths:
        texts['strengths'] = (
            "חוזקות יחסיות: " + ", ".join(e['name'] for e in strengths) + "."
        )
    if weaknesses:
        texts['weaknesses'] = (
            "קשיים יחסיים: " + ", ".join(e['name'] for e in weaknesses) + "."
        )

    return texts
