from flask import Flask
from db import client

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/teste")
def get_dados():
    teste = f"<h1>Coleções: {client['atos_normativos'].list_collection_names()}.</h1>"
    
    return teste

client.close()