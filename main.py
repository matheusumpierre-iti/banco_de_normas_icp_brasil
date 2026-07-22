from typing import Any
from dataclasses import dataclass, field
import pandas as pd
import sqlite3
import pdfplumber
import html5lib
import requests
from typing import Optional, Union
import io
import lxml
import spacy
from spacy.tokens import Token
from spacy.tokens import Doc
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

PREFIXO_URN = 'lex:br:instituto.federal.tecnologia.informacao:icp.brasil:'

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
                return self.texto
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
        
        pass


class DispositivoNormativo():
    def __init__(self, arquivo_origem:Doc, id_dispositivo:str, tipo:str, sufixo_urn:str) -> None:
        self.arquivo_origem:Doc = arquivo_origem
        self.id_dispositivo:str = id_dispositivo
        self.tipo:str = tipo
        self.prefixo_urn: str = PREFIXO_URN
        self.sufixo_urn: str = sufixo_urn
        self.urn: str = self.__definir_urn()
        pass

    def __str__(self) -> str:
        return f'{self.urn}'

    def __definir_urn(self) -> str:
        self.urn = self.prefixo_urn + self.sufixo_urn
        return self.urn

    


#testes
d = AtoNormativo(r'https://repositorio.iti.gov.br/resolucoes/Resolucao219_altera_endereco.htm', nlp=True)
doc = d.doc

def identificar_artigos(doc: Doc, incluir_paragrafos:bool = False):

    lista_artigos = []
    artigos_paragrafos = {}

    for token in doc:
        if token.text == 'Art.':
            inicio = token.i
            for i in range(inicio, len(doc), 1):
                if doc[i].text == '.':
                    final = doc[i+1].i
                    break
            texto_artigo = doc[inicio: final]
            indice_artigo = texto_artigo[0:2]
            urn_artigo = f'{indice_artigo.text.lower()[0:3]}' + '_' + f'{indice_artigo.text[5]}'
            artigo = DispositivoNormativo(doc[0:5].as_doc(), indice_artigo.text, 'Artigo',f'{urn_artigo}')
            lista_artigos.append(artigo)
            artigos_paragrafos[texto_artigo] = []

            if incluir_paragrafos == True:
                for artigo in lista_artigos:
                    for token in artigo:
                        if token.text.startswith('§') or token.text == 'Parágrafo':
                            inicio_paragrafo = token.i
                            for i in range(inicio_paragrafo, len(doc), 1):
                                if doc[i].text == '.':
                                    final_paragrafo = doc[i+1].i
                                    break
                            paragrafo = doc[inicio_paragrafo:final_paragrafo]
                            artigos_paragrafos[artigo] = paragrafo

    return lista_artigos

#soup = BeautifulSoup(requests.get('https://repositorio.iti.gov.br/resolucoes/Resolucao202_revogacao_estado_emergencia.htm').content, 'html5lib')
#print(soup.find(lambda x: x.has_attr('class') and 't m0 x0' in x['class']))

for artigo in identificar_artigos(doc):
    print(artigo)

