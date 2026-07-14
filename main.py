import pandas as pd
import sqlite3
import pdfplumber
import webbrowser
import requests
import io
import spacy
from spacy.lang.pt.examples import sentences
from html.parser import HTMLParser
from bs4 import BeautifulSoup
import pypandoc
from pypandoc.pandoc_download import download_pandoc
from thinc.layers.dish import init


class ModeloNLP():
    def __init__(self) -> None:
        self.nlp = spacy.load("pt_core_news_lg")
        pass

class BancoDeDados():
    def __init__(self, arquivo:str) -> None:
        self.arquivo = arquivo
        self.db = sqlite3.connect(self.arquivo)
        pass 

class ConversorHTML:
    '''Converte um arquivo de texto em um objeto HTML estruturado'''

    def __init__(self, filepath:str) -> None:
        self.arquivo = filepath
        self.parser = HTMLParser
        self.html_doc = self.doc_to_html()
        self.convertido = self.parse_html()
        self.formatado = self.convertido.prettify()
        self.paragrafos = [p.get_text() for p in self.convertido.find_all('p')]
        pass

    def __str__(self):
        return f'Arquivo localizado em f{self.arquivo}'    

    def doc_to_html(self) -> str:
        html_doc = pypandoc.convert_file(rf'{self.arquivo}', to='html')
        return html_doc

    def parse_html(self):
        soup = BeautifulSoup(self.html_doc, 'html.parser')
        return soup
    
    def localizar_artigos(self):
        artigos = []
        for paragrafo in self.paragrafos:
            if paragrafo.lower().startswith('art.'):
                artigos.append(paragrafo)
        return artigos

class IdentificadorAto(ConversorHTML):
    '''Usa regras definidas para identificar o tipo de ato normativo (DOC-ICP, Resolução, Instrução Normativa)'''
    
    def __init__(self, filepath: str) -> None:
        super().__init__(filepath)
            
        self.regras = {
        'instrução normativa':'Instrução Normativa',
        'resolução':'Resolução'
        }

        self.rotulo = self.rotular_documento()
    
    def rotular_documento(self):
        
        for key, value in self.regras.items():
            if self.paragrafos[0].lower().startswith(key):
                rotulo = value
            else:
                rotulo = 'Desconhecido'
        return rotulo   
        

#testes
nlp = ModeloNLP().nlp
html = requests.get('https://www.gov.br/iti/pt-br/assuntos/legislacao/portarias/Portaria_35_2025.pdf')
arquivo = io.BytesIO(html.content)
texto_pdf = pdfplumber.open(arquivo).pages[0].extract_text()

doc = nlp(texto_pdf)

for token in doc:
    if token.lemma_ == 'instituir':
        print(token.sent)