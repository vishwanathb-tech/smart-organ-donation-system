import os, joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

BASE = os.path.dirname(__file__)
DATA = os.path.join(BASE, 'data')
os.makedirs(DATA, exist_ok=True)
CSV = os.path.join(DATA, 'sample_matches.csv')
MODEL = os.path.join(BASE, 'model.pkl')

def generate():
    import random
    organs=['Kidney','Liver','Heart','Lung']
    rows=[]
    for _ in range(500):
        d=random.choice(organs); r=random.choice(organs)
        blood=1 if random.random()<0.5 else 0
        dist=random.choice([10,50,100,200,400,800])
        age_diff=abs(random.randint(18,65)-random.randint(18,65))
        label=1 if (d==r and blood==1 and dist<200) else 0
        rows.append([d,r,blood,dist,age_diff,label])
    df=pd.DataFrame(rows,columns=['donor_organ','recipient_organ','blood_match','distance','age_diff','match'])
    df.to_csv(CSV,index=False)
    le1=LabelEncoder(); le2=LabelEncoder()
    df['d_enc']=le1.fit_transform(df['donor_organ'])
    df['r_enc']=le2.fit_transform(df['recipient_organ'])
    X=df[['d_enc','r_enc','blood_match','distance','age_diff']]
    y=df['match']
    clf=RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X,y)
    joblib.dump({'model':clf,'le1':le1,'le2':le2}, MODEL)
    print('Saved model to', MODEL)

if __name__=='__main__':
    generate()
