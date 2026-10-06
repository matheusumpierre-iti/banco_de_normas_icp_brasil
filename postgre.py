import psycopg
from psycopg.types.json import Jsonb
from dotenv import dotenv_values

db = dotenv_values()['DB_PSQL']
host = dotenv_values()['HOST_PSQL']
user = dotenv_values()['USER_PSQL']
password = dotenv_values()['PASS_PSQL']

conn = psycopg.connect(
    host=host,
    user=user,
    password=password,
    dbname = db
)
with conn:
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS instrucoes_normativas (
        id SERIAL PRIMARY KEY,
        dados JSONB NOT NULL,
        criado_em TIMESTAMP DEFAULT NOW()
    )
""")
    conn.commit()

with conn:
   pass 