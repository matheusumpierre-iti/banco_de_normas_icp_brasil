from flask import Flask, render_template, request, jsonify
from markupsafe import escape
import sys
import os
from pathlib import Path
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from db import client

parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

project_root = os.path.dirname(__file__)
template_path = os.path.join(project_root, './')

app = Flask(__name__, template_folder=template_path)

@app.route("/")
def index():
    template = render_template(r'index.html')
    
    return template

@app.route("/teste")
def get_dados():
    teste = f"<h1>Coleções: {client['atos_normativos'].list_collection_names()}.</h1>"
    
    return teste

if __name__ == "__main__":
    app.run()