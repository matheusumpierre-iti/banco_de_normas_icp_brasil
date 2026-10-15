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
port = dotenv_values()['PORT_PSQL']

conn = psycopg.connect(
    host=host,
    user=user,
    password=password,
    dbname = db,
    port = port 
)

def teste_conn():
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM instrucoes_normativas;
    """)
        conn.commit()
        print(cursor.fetchall())

def inserir_json(caminho_json, tipo_ato):
    with conn:
        cursor = conn.cursor()
        for arquivo in os.listdir(caminho_json):
            if 'revogado' in arquivo.lower() or 'revogada' in arquivo.lower():
                vigencia = False
            else:
                vigencia = True
            if arquivo.endswith('.json'):
                with open(f'{caminho_json}/{arquivo}', encoding='utf8') as file:
                    arquivo_json = file.read()
                    urn = json.loads(arquivo_json)['urn']
                    titulo = json.loads(arquivo_json)['titulo']
                
                    cursor.execute("""
                    INSERT INTO atos_normativos (urn_ato, tipo_ato, titulo_ato, vigencia_ato, dados) VALUES (%s,%s, %s,%s,%s);
                                    """, (urn, tipo_ato, titulo, vigencia, arquivo_json,))
        conn.commit()

inserir_json(r'upload\Resoluções\json', 'resolucao')
