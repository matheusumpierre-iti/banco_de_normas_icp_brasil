
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import json

uri = "mongodb+srv://matheusumpierre_db_user:ofgNm4vnfQHJNRNt@clusterlexicp.ng8flgg.mongodb.net/?appName=ClusterLexICP"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection

if __name__ == '__main__':
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

    database = client['atos_normativos']
    collection = database['urn:icp.brasil:doc.icp.03.01:22.10.2020']
    with database.list_collections() as cursor:
        for collection in cursor:
            print(collection['name'])
            
    client.close()
    print('Client closed!')

