import sqlite3

db = 'database.db'
print('DB:', db)
conn = sqlite3.connect(db)
cur = conn.cursor()
# print schema
print('\nSchema for recipient_request:')
for row in cur.execute("PRAGMA table_info('recipient_request')"):
    print(row)

print('\nChecking NULLs in critical columns: patient_name,mobile,organ_needed,password')
for col in ['patient_name', 'mobile', 'organ_needed', 'password']:
    cur.execute(
        f"SELECT COUNT(*) FROM recipient_request WHERE {col} IS NULL OR trim({col})='' ")
    cnt = cur.fetchone()[0]
    print(col, 'NULL/empty count=', cnt)

print('\nShow first 10 rows:')
for r in cur.execute('SELECT id,patient_name,mobile,organ_needed,blood_group,city,password FROM recipient_request LIMIT 10'):
    print(r)
conn.close()
