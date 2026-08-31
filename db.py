
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
            file.write('\nDB_USER=\n')
            file.write('\nDB_PASSWORD=\n')
    else:
        with open('.env', 'a+') as file:
            file.seek(0)
            if 'DB_USER' in file.read():
                pass
            else:
                file.seek(0)
                file.write('\nDB_USER=\n')

        with open('.env', 'a+') as file:
            file.seek(0)
            if 'DB_PASSWORD' in file.read():
                pass
            else:
                file.seek(0)
                file.write('\nDB_PASSWORD=\n')
    env = Path('.env')
    return env

def configurar_login():
    env = configurar_ambiente()
    db_user = dotenv_values(env)['DB_USER']
    db_pass = dotenv_values(env)['DB_PASSWORD']

    if len(db_user) < 3:
            db_user = input('Nome de usuário do banco de dados:').strip()
            set_key(env,'DB_USER',db_user)
    
    if len(db_pass) < 3:
            db_pass = input('Senha do banco de dados:').strip()
            set_key(env,'DB_PASSWORD', db_pass)
    
    return db_user, db_pass

def acessar_banco(db_user, db_pass):
    env = configurar_ambiente()
    db_user, db_pass = configurar_login()

    uri = f"mongodb+srv://{db_user}:{db_pass}@clusterlexicp.ng8flgg.mongodb.net/?appName=ClusterLexICP"

    client = MongoClient(uri, server_api=ServerApi('1'))

    try:
        with MongoClient(uri, server_api=ServerApi('1')) as client:
            client.admin.command('ping')
        client = MongoClient(uri, server_api=ServerApi('1'))
        return client
    except:
        set_key(env, 'DB_USER', '')
        set_key(env, 'DB_PASSWORD', '')
        raise ConfigurationError('Usuário ou senha inválidos. Tente novamente.')
        return client
        


    # Create a new client and connect to the server

# Send a ping to confirm a successful connection
if __name__ == '__main__':
    configurar_ambiente()
    db_user, db_pass = configurar_login()
    with acessar_banco(db_user, db_pass) as client:
        print(client.list_database_names())