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
from spacy.tokens import Span, Token, Doc
from pdfplumber.pdf import PDF
from bs4 import BeautifulSoup
import pypandoc
from pypandoc.pandoc_download import download_pandoc

#Extensões de classes
artigo_getter = lambda token: token.text == 'Art.'
paragrafo_getter = lambda token: token.text == '§'

Token.set_extension('is_artigo', getter=artigo_getter)
Token.set_extension('is_paragrafo', getter=paragrafo_getter)

#Constantes
MODELO_NLP = spacy.load('pt_core_news_lg')

TIPO_ATO_NORMATIVO = {
        'instrução normativa':'Instrução Normativa',
        'instrução':'Instrução Normativa',
        'resolução':'Resolução',
        'portaria' : 'Portaria'
        }

#Classes        
class AtoNormativo:
    def __init__(self, arquivo:str, nlp:bool = False) -> None:
        self.origem = arquivo
        self.url: Optional[str] = None
        self.formatos_suportados = ['.pdf','.md','.txt','.odt','.doc','.docx']
        self.arquivo_salvo: Optional[io.BytesIO] = None
        self.pdf: Optional[PDF] = None
        self.titulo: Optional[str] = None
        self.categoria: Optional[str] = None
        self.dispositivos: Optional[list] = None
        self.texto: str
        self.doc: Any = None
        self.__obter_conteudo()
        if nlp == True:
            self.__processar_nlp()
            self.__classificar_ato_normativo()
        pass

    def __processar_nlp(self):
        self.doc = MODELO_NLP(self.texto)
        return self.doc

    def old__obter_conteudo(self): 
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

    def __obter_conteudo(self): 
        if self.origem.startswith(('http://','https://')):
            if not self.origem.endswith('.pdf'):
                self.url = self.origem
                self.arquivo_salvo = io.BytesIO(requests.get(self.url).content)
                self.texto = BeautifulSoup(self.arquivo_salvo, 'lxml').text
            else:
                self.url = self.origem
                self.__processar_pdf(de_url = True)
        elif self.origem.endswith('.pdf'):
            self.__processar_pdf()
        elif self.origem.endswith(tuple(self.formatos_suportados)):
            self.__processar_texto_doc()
        else:
            if not self.origem.endswith(tuple(self.formatos_suportados)):
                print('Formato não suportado')

    def __processar_pdf(self, de_url:bool = False):
        if de_url == False:
            self.pdf = pdfplumber.open(self.origem)
        else:
            self.pdf = pdfplumber.open(io.BytesIO(requests.get(self.url).content))
        self.texto = ''
        for page in self.pdf.pages[0:(len(self.pdf.pages)+1)]:
                texto_pagina = page.extract_text()
                self.texto += texto_pagina
        return self.texto

    def __processar_texto_doc(self):
        html_doc = pypandoc.convert_file(rf'{self.origem}', to='html')
        self.texto = BeautifulSoup(html_doc, 'lxml').text
        return self.texto
    
    def __classificar_ato_normativo(self):
        for token in self.doc[0:10]:
            if token.text.lower() in TIPO_ATO_NORMATIVO.keys():
                self.categoria = TIPO_ATO_NORMATIVO[token.text.lower()]
                break
            else:
                self.categoria = 'Desconhecida'
        return self.categoria 
    
    def __classificar_dispositivos(self):
        DispositivoNormativo(self.origem)
        pass

@dataclass
class DispositivoNormativo(AtoNormativo):
    arquivo_origem: str
    id_dispositivo: Optional[str] = None
    tipo: Optional[str] = None
    prefixo_urn: str = 'lex:br:instituto.federal.tecnologia.informacao:icp.brasil:'
    urn: Optional[str] = None

    def definir_urn(self):
        for token in doc:
            if token._.is_artigo:
                self.urn = 'lex:br:instituto.federal.tecnologia.informacao:icp.brasil:' + 'art:' + f'artigo_{token.nbor(1).text[0]}'
        return self.urn


#testes
d = AtoNormativo(r'https://www.gov.br/iti/pt-br/assuntos/legislacao/documentos-principais/resolucao180_doc-icp-17_compilada.pdf', nlp=True)
doc = d.doc


for token in doc:
    if token.pos_ == 'VERB':
        print(token.sent)
        break