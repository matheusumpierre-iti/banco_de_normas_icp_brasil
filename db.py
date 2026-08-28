
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, OperationFailure
import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv, set_key
from pymongo.server_api import ServerApi
import time

ENV_PATH = ('.env')

if not Path('.env').is_file():
    print('Env nao encontrado')
    with open('.env','x') as file:
        pass
    with open('.env','a') as file:
        file.write('DB_USER=')
        file.write('DB_PASSWORD=')

with open('.env', 'a+') as file:
    if 'DB_USER=' in file.read():
        pass
    else:
        file.write('DB_USER=\n')

with open('.env', 'a+') as file:
    if 'DB_PASSWORD=' in file.read():
        pass
    else:
        file.seek(0)
        file.write('DB_PASSWORD=\n')

def verificar_credenciais(db_user, db_pass):
    try:
        db_user = dotenv_values()['DB_USER']
        if len(db_user) < 3:
            db_user = input('Nome de usuário do banco de dados:').strip()
            os.environ['DB_USER'] = db_user
            set_key(ENV_PATH,'DB_USER',db_user)
    except:
            db_user = input('Nome de usuário do banco de dados:').strip()
            os.environ['DB_USER'] = db_user
            set_key(ENV_PATH,'DB_USER',db_user)

    try:
        db_pass = dotenv_values()['DB_PASSWORD']
        if len(db_pass) < 3:
            db_pass = input('Senha do banco de dados:').strip()
            os.environ['DB_PASS'] = db_pass
            set_key(ENV_PATH,'DB_PASSWORD', db_pass)
    except:
        db_pass = input('Senha do banco de dados:').strip()
        db_user = os.environ['DB_USER']

    return db_user, db_pass

def acessar_banco(db_user:str = dotenv_values()['DB_USER'], db_pass:str = dotenv_values()['DB_PASSWORD']):

    if len(db_user) < 3:
        db_user = input('Nome de usuário do banco de dados:').strip()
        os.environ['DB_USER'] = db_user
        set_key(ENV_PATH,'DB_USER',db_user)

    if len(db_pass) < 3:
        db_pass = input('Senha do banco de dados:').strip()
        os.environ['DB_PASS'] = db_pass
        set_key(ENV_PATH,'DB_PASSWORD', db_pass)

    uri = f"mongodb+srv://{db_user}:{db_pass}@clusterlexicp.ng8flgg.mongodb.net/?appName=ClusterLexICP"

    client = MongoClient(uri, server_api=ServerApi('1'))

    try:
        with MongoClient(uri, server_api=ServerApi('1')) as client:
            client.admin.command('ping')
            print('ping realizado com sucesso')
        return client
    except:
        print('Usuário ou senha inválidos. Tente novamente.')
        set_key(ENV_PATH, 'DB_USER', '')
        set_key(ENV_PATH, 'DB_PASSWORD', '')
        acessar_banco()


    # Create a new client and connect to the server





'''# Send a ping to confirm a successful connection
if __name__ == '__main__':
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

    database = client['atos_normativos']'''

with acessar_banco() as client:
    print('Teste')