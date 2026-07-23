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
        self.dispositivos: dict = {'Conteúdo':'Tipo'}
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
        prefixos = {
            'Art.':'Artigo'
        }

        dispositivos_encontrados = {}

        for token in self.doc:
            if token.text in prefixos.keys():
                span = self.doc[token.text.i : token.text.i + 5]
                dispositivos_encontrados[span] = prefixos[span[0].text]
        return dispositivos_encontrados

    def 


class DispositivoNormativo():
    def __init__(self, texto:str, arquivo_origem:Doc, id_dispositivo:str, tipo:str, sufixo_urn:str) -> None:
        self.arquivo_origem:Doc = arquivo_origem
        self.nlp: Doc = MODELO_NLP('NLP não processado')
        self.texto = texto
        self.id_dispositivo:str = id_dispositivo
        self.tipo:str = tipo
        self.prefixo_urn: str = PREFIXO_URN
        self.sufixo_urn: str = sufixo_urn
        self.urn: str = self.__definir_urn()
        self.paragrafos: Optional[list] = []

        if self.tipo == 'Artigo':
            self.__nlp_dispositivo()
            self.__enumerar_artigo()
            self.__identificar_paragrafos()
        pass

    def __str__(self) -> str:
        return f'{self.urn}'

    def __nlp_dispositivo(self) -> Doc:
        nlp = MODELO_NLP(self.texto)
        return nlp

    def __definir_urn(self) -> str:
        self.urn = self.prefixo_urn + self.sufixo_urn
        return self.urn

    def __enumerar_artigo(self) -> str:
        numero_artigo: str = ''
        limitador = 0
        for token in self.nlp:
            limitador += 1
            if token.is_digit:
                numero_artigo = token.text
                break
            elif limitador > 10:
                numero_artigo = 'sem_numero'
        return numero_artigo

    def __identificar_paragrafos(self) -> list:
        paragrafos = []
        for token in self.nlp:
            if token.text.startswith('§') or token.text == 'Parágrafo':
                inicio_paragrafo = token.i
                limitador = 0
                for i in range(inicio_paragrafo, len(doc), 1):
                    limitador += 1
                    if doc[i].text in ['Art.', '§', 'Parágrafo', '.']:
                        final_paragrafo = doc[i].i
                        break
                    elif limitador > 100:
                        final_paragrafo = doc[limitador].i
                        break
            texto_paragrafo = doc[inicio_paragrafo : final_paragrafo]
            paragrafos.append(texto_paragrafo)
        return paragrafos


    


#testes
d = AtoNormativo(r'https://repositorio.iti.gov.br/resolucoes/Resolucao219_altera_endereco.htm', nlp=True)
doc = d.doc

def classificar_dispositivos(origem: Doc):
        prefixos = {
            'Art.':'Artigo'
        }

        dispositivos = {}

        for token in origem:
            if token.text in prefixos.keys():
                span = origem[token.i : token.i + 5]
                dispositivos[span] = prefixos[span[0].text]
        return dispositivos

teste = classificar_dispositivos(MODELO_NLP('Art. 1º diz a coisa x e Art. 2º diz a coisa y'))

print(teste)