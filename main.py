import pandas as pd
import sqlite3
import pdfplumber
import requests
import io
import spacy
from spacy.lang.pt.examples import sentences
from html.parser import HTMLParser
from bs4 import BeautifulSoup
import pypandoc
from pypandoc.pandoc_download import download_pandoc


class ModeloNLP:
    def __init__(self) -> None:
        self.nlp = spacy.load("pt_core_news_lg")
        pass

class DocumentoHospedado:
    '''Lida com documentos .pdf hospedados em URL'''
    def __init__(self, url: str) -> None:
        self.html = requests.get(url)
        self.arquivo = io.BytesIO(self.html.content)
        self.texto_pdf = pdfplumber.open(self.arquivo)    
        self.texto_extraido = self.extrair_texto()
    
    def extrair_texto(self, pagina_inicial: int = 0, pagina_final: int = 1):
        self.texto = str()
        for page in self.texto_pdf.pages[pagina_inicial:pagina_final]:
            texto_pagina = page.extract_text()
            self.texto += texto_pagina
        return self.texto    
        

class BancoDeDados:
    def __init__(self, arquivo:str) -> None:
        self.arquivo = arquivo
        self.db = sqlite3.connect(self.arquivo)
        pass 

class ConversorHTML(ModeloNLP):
    '''Converte um arquivo de texto em um objeto HTML estruturado'''

    def __init__(self, filepath:str) -> None:
        self.arquivo = filepath
        self.parser = HTMLParser
        self.html_doc = self.doc_to_html()
        self.convertido = self.parse_html()
        self.doc = self.nlp(self.convertido.text)
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

class ConversorDoc(ModeloNLP, DocumentoHospedado):
    '''Converte diversos formatos para documento NLP'''
    def __init__(self, url:str) -> None:
        super().__init__()
        DocumentoHospedado.__init__(self, url)
        self.doc = self.converter_url()
        pass

    #if url: converter_url else converter_arquivo

    def converter_url(self):
        self.doc = self.nlp(self.texto_extraido)
        return self.doc

   


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
    
    def rotular_documento_hospedado(self):
        for key, value in self.regras.items():
            if self.paragrafos[0].lower().startswith(key):
                rotulo = value
            else:
                rotulo = 'Desconhecido'
            return rotulo
        

#testes
nlp = ModeloNLP().nlp
#texto_pdf = pdfplumber.open(arquivo).pages[0].extract_text()

print(ConversorDoc('https://www.gov.br/iti/pt-br/assuntos/legislacao/portarias/Portaria_35_2025.pdf'))