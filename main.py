from typing import Any
from dataclasses import dataclass, field
import pandas as pd
import sqlite3
import pdfplumber
import requests
from typing import Optional, Union
import io
import lxml
import spacy
from spacy.tokens import Span
from pdfplumber.pdf import PDF
from spacy.lang.pt.examples import sentences
from html.parser import HTMLParser
from bs4 import BeautifulSoup
import pypandoc
from pypandoc.pandoc_download import download_pandoc

#Constantes
MODELO_NLP = spacy.load('pt_core_news_lg')

#Classes        
class AtoNormativo:
    def __init__(self, arquivo:str) -> None:
        self.origem = arquivo
        self.url: Optional[str] = None
        self.formatos_suportados = ['.pdf','.md','.txt','.odt','.doc','.docx']
        self.arquivo_salvo: Optional[io.BytesIO] = None
        self.pdf: Optional[PDF] = None
        self.titulo: Optional[str] = None
        self.categoria: Optional[str] = None
        self.dispositivos: Optional[list] = None
        self.texto: str

        self.__obter_conteudo()
        pass

    def processar_nlp(self):
        self.doc = MODELO_NLP(self.texto)
        return self.doc

    def __obter_conteudo(self): 
        if self.origem.startswith(('http://','https://')):
            self.url = self.origem
            self.arquivo_salvo = io.BytesIO(requests.get(self.url).content)
            self.texto = BeautifulSoup(self.arquivo_salvo, 'lxml').text
        elif self.origem.endswith('.pdf'):
            self.__processar_pdf()
        elif self.origem.endswith(tuple(self.formatos_suportados)):
            self.__processar_texto_doc()
        else:
            if not self.origem.endswith(tuple(self.formatos_suportados)):
                print('Formato não suportado')

    def __processar_pdf(self):
        self.pdf = pdfplumber.open(self.origem)
        self.texto = ''
        for page in self.pdf.pages[0:(len(self.pdf.pages)+1)]:
                texto_pagina = page.extract_text()
                self.texto += texto_pagina
        return self.texto

    def __processar_texto_doc(self):
        html_doc = pypandoc.convert_file(rf'{self.origem}', to='html')
        self.texto = BeautifulSoup(html_doc, 'lxml').text
        return self.texto

@dataclass
class DispositivoNormativo:
    tipo: str
    urn: Optional[str]
    prefixo_lex: str = 'lex:br:instituto.federal.tecnologia.informacao:icp.brasil:'
    

d = AtoNormativo(r'C:\Users\matheus.umpierre\Projetos\lexml_icp_brasil\testes\Resolucao152_revogada.odt')

getter_artigo = lambda span: 'Art' in span.text
Span.set_extension('is_artigo', getter=getter_artigo)

print(d.processar_nlp())