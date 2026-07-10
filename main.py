import pandas as pd
import json
import spacy
from html.parser import HTMLParser
from bs4 import BeautifulSoup
import pypandoc
from pypandoc.pandoc_download import download_pandoc

 
def doc_to_html(filepath: str) -> str:
    html_doc = pypandoc.convert_file(rf'{filepath}', to='html')
    return html_doc
    
def parse_html(html: str):
    soup = BeautifulSoup(html)
    return soup


for p in soup.find_all('p'):
    if p.text.lower().startswith('art'):
        print(p.text)