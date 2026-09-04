
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, OperationFailure
import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv, set_key
from pymongo.server_api import ServerApi

def configurar_ambiente():
    if not Path('.env').is_file():
        with open('.env','x') as file:
            pass
        with open('.env','a') as file:
            file.write('DB_USER=\n')
            file.write('DB_PASSWORD=\n')
            file.write('DB_SUFIXO_URI=\n')
    else:
        with open('.env', 'a+') as file:
            file.seek(0)
            if 'DB_USER' in file.read():
                pass
            else:
                file.seek(0)
                file.write('DB_USER=\n')

        with open('.env', 'a+') as file:
            file.seek(0)
            if 'DB_PASSWORD' in file.read():
                pass
            else:
                file.seek(0)
                file.write('DB_PASSWORD=\n')

        with open('.env', 'a+') as file:
            file.seek(0)
            if 'DB_SUFIXO_URI' in file.read():
                pass
            else:
                file.seek(0)
                file.write('DB_SUFIXO_URI=\n')

    env = Path('.env')
    return env

def configurar_login(env):
    try:
        db_user = dotenv_values(env)['DB_USER']
        db_pass = dotenv_values(env)['DB_PASSWORD']
        sufixo_uri = dotenv_values(env)['DB_SUFIXO_URI']
        if db_user == '' or db_pass == '' or db_user == '':
            sufixo_uri = input('Sufixo da URI do banco de dados (string após o @):').strip()
            db_user = input('Nome de usuário do banco de dados:').strip()
            db_pass = input('Senha do banco de dados:').strip()
            set_key(env, 'DB_SUFIXO_URI', sufixo_uri)
            set_key(env,'DB_USER',db_user)
            set_key(env,'DB_PASSWORD', db_pass)
        else:
            return db_user, db_pass, sufixo_uri
    except:
        sufixo_uri = input('Sufixo da URI do banco de dados (string após o @):').strip()
        db_user = input('Nome de usuário do banco de dados:').strip()
        db_pass = input('Senha do banco de dados:').strip()
        set_key(env, 'DB_SUFIXO_URI', sufixo_uri)
        set_key(env,'DB_USER',db_user)
        set_key(env,'DB_PASSWORD', db_pass)
    return db_user, db_pass, sufixo_uri

def acessar_banco(db_user, db_pass, sufixo_uri):
    env = configurar_ambiente()
    db_user, db_pass, sufixo_uri = configurar_login(env)

    uri = f"mongodb+srv://{db_user}:{db_pass}@{sufixo_uri}"

    try:
        with MongoClient(uri, server_api=ServerApi('1')) as client:
            client.admin.command('ping')
        client = MongoClient(uri, server_api=ServerApi('1'))
        return client
    except:
        set_key(env, 'DB_USER', '')
        set_key(env, 'DB_PASSWORD', '')
        set_key(env, 'DB_SUFIXO_URI', '')
        raise ConfigurationError('Usuário, senha ou endereço do banco de dados inválido. Tente novamente.')
        return client
        

def pipeline_login():
    env = configurar_ambiente()
    db_user, db_pass, sufixo_uri = configurar_login(env)
    client = acessar_banco(db_user, db_pass, sufixo_uri)
    return client

    # Create a new client and connect to the server

def login_streamlit():
    env = configurar_ambiente()
    credenciais = dotenv_values(env)
    if all(credenciais):
        return 'Ok'
    else:
        return 'N'

# Send a ping to confirm a successful connection
if __name__ == '__main__':
    env = configurar_ambiente()
    db_user, db_pass, sufixo_uri = configurar_login(env)
    with acessar_banco(db_user, db_pass, sufixo_uri) as client:
        print(client.list_database_names())
        print(login_streamlit())