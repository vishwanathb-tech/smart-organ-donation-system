# ai_matcher.py
import os, joblib
BASE = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE, 'model.pkl')

def calculate_distance(city1, city2):
    distances = {('Mumbai','Pune'):150, ('Pune','Mumbai'):150, ('Delhi','Noida'):25, ('Chennai','Bangalore'):350}
    return distances.get((city1, city2), 500)

def rule_based_score(donor, recipient):
    score = 0
    if donor.get('organ') == recipient.get('organ_needed'):
        score += 50
    if donor.get('blood_group') == recipient.get('blood_group'):
        score += 40
    distance = calculate_distance(donor.get('city'), recipient.get('city'))
    if distance < 200:
        score += 20
    elif distance < 400:
        score += 10
    return score

_model = None
if os.path.exists(MODEL_PATH):
    try:
        _model = joblib.load(MODEL_PATH)
    except Exception as e:
        print('Model load error:', e)
        _model = None

def ml_score(donor, recipient):
    if not _model:
        return None
    try:
        le1 = _model['le1']; le2 = _model['le2']; model = _model['model']
        d_org = donor.get('organ') or 'Kidney'
        r_org = recipient.get('organ_needed') or 'Kidney'
        donor_enc = le1.transform([d_org])[0] if d_org in le1.classes_ else 0
        recipient_enc = le2.transform([r_org])[0] if r_org in le2.classes_ else 0
        blood_match = 1 if donor.get('blood_group') == recipient.get('blood_group') else 0
        distance = calculate_distance(donor.get('city'), recipient.get('city'))
        age_diff = abs(int(donor.get('age',30)) - int(recipient.get('age',30)))
        X = [[donor_enc, recipient_enc, blood_match, distance, age_diff]]
        proba = model.predict_proba(X)[0][1]
        return int(proba * 100)
    except Exception as e:
        print('ML score error:', e)
        return None

def match_score(donor, recipient):
    s = ml_score(donor, recipient)
    if s is not None:
        return s
    return rule_based_score(donor, recipient)
