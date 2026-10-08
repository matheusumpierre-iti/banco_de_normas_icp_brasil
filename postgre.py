import psycopg
import json
import os
from pathlib import Path
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
    dbname = db,
    port = 5433
)

def teste_conn():
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM instrucoes_normativas;
    """)
        conn.commit()
        print(cursor.fetchall())

def inserir_json():
    with conn:
        cursor = conn.cursor()
        for arquivo in os.listdir('testes/batch/json'):
            if arquivo.endswith('.json'):
                with open(f'testes/batch/json/{arquivo}', encoding='utf8') as file:
                    arquivo_json = file.read()
                
                    cursor.execute("""
                    INSERT INTO instrucoes_normativas (dados) VALUES (%s);
                                    """, (arquivo_json,))
        conn.commit()

inserir_json()