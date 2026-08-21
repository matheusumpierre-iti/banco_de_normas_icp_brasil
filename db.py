
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import time

uri = "mongodb+srv://matheusumpierre_db_user:ofgNm4vnfQHJNRNt@clusterlexicp.ng8flgg.mongodb.net/?appName=ClusterLexICP"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)


database = client['lex_icp']
atos_normativos = database['atos_normativos']

