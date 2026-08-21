from typing import Any
import re
from db import client
from db import atos_normativos
from db import database
import roman
import hashlib
from classes import ExemploAtoNormativo
from dataclasses import dataclass, field
import pandas as pd
import pdfplumber
import html5lib
import requests
from typing import Optional, Union
import io
import lxml
import spacy
from spacy.tokens import Token
from spacy.tokens import Doc
from spacy.matcher import Matcher
from spacy.matcher import PhraseMatcher
from spacy.training import Example
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
        'instrução normativa':'instrucao.normativa',
        'instrução':'instrucao.normativa',
        'resolução':'resolucao',
        'portaria' : 'portaria',
        'ofício' : 'portaria'
        }

PREFIXO_URN = 'urn:lex:icp.brasil:'

PREFIXO_DISPOSITIVO = {'Art.':'artigo',
                       '§':'paragrafo',
                       'Parágrafo':'paragrafo',
                       'I' : 'inciso',
                       'a)':'item'}

HIERARQUIA_DISPOSITIVOS = {'artigo':'paragrafo',
                           'paragrafo':'inciso',
                           'inciso':'item',
                           'item': None}

#Classes        
class AtoNormativo:
    def __init__(self, arquivo:str, nlp:bool = False) -> None:
        self.origem = arquivo
        self.url: Optional[str] = None
        self.hash: Optional[str] = None
        self.formatos_suportados = ['.pdf','.md','.txt','.odt','.doc','.docx']
        self.arquivo_salvo: Optional[io.BytesIO] = None
        self.pdf: Optional[PDF] = None
        self.titulo: str = ''
        self.categoria: Optional[str] = None
        self.dispositivos: list = []
        self.texto: str
        self.doc: Any = None
        self.__obter_conteudo()
        if nlp == True:
            self.__processar_nlp()
            self.__obter_titulo()
            self.__obter_hash()
            self.__classificar_ato_normativo()
            self.dispositivos = self.__classificar_dispositivos()

    def __processar_nlp(self):
        self.doc = MODELO_NLP(self.texto)
        return self.doc


    def __obter_titulo(self):
        for token in self.doc:
            if token.text.lower() in TIPO_ATO_NORMATIVO.keys():
                prefixo_titulo = TIPO_ATO_NORMATIVO[token.text.lower()]
                sufixo_titulo = ''
                span = self.doc[token.i:token.i+5]
                for i in range(0, len(span.text)):
                    if span.text[i].isdigit():
                        sufixo_titulo += span.text[i]
                self.titulo = prefixo_titulo +'.'+sufixo_titulo
                break
            else:
                self.titulo = 'Desconhecido'
        return self.titulo


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
            if not self.origem.endswith('pdf'):
                print('Obtendo conteúdo de página web;')
                self.url = self.origem
                self.arquivo_salvo = io.BytesIO(requests.get(self.url).content)
                self.texto = BeautifulSoup(self.arquivo_salvo, 'lxml').text
                return self.texto
            else:
                print('Obtendo conteúdo de pdf hospedado na web.')
                self.url = self.origem
                self.__processar_pdf(de_url = True)
        elif self.origem.endswith('pdf'):
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
    
    def __is_romano(self, token: Token) -> bool:
        try:
            roman.fromRoman(token.text, special_case=False)
            if token.text == token.text.upper() and token.is_alpha:
                return True
            else:
                return False
        except:
            return False

    def __obter_hash(self):
        hash = hashlib.sha1(self.texto.encode('utf-8'))
        self.hash = hash.hexdigest()
        return self.hash

    def __classificar_dispositivos(self):
        prefixos = PREFIXO_DISPOSITIVO.copy()

        dispositivos_encontrados = {}

        dispositivos_classificados = []

        for token in self.doc:
            if self.__is_romano(token):
                prefixos[token.text] = 'inciso'
            if token.text in prefixos.keys():
                span = self.doc[token.i : token.i + 15]
                indice_doc = token.i
                indice_texto = '.'
                for i in range(0, len(span[1].text)):
                    if span[1].text[i].isdigit():
                        indice_texto += span[1].text[i]
                    elif self.__is_romano(span[0]):
                        indice_texto = '.' + str(roman.fromRoman(span[0].text))
                    elif 'único' in span.text:
                        indice_texto = 'unico'
                dispositivos_encontrados[span.text] = prefixos[span[0].text]
                dispositivo = DispositivoNormativo(texto=span.text, origem=self, tipo=prefixos[span[0].text], indice_texto=indice_texto, indice_doc=indice_doc)
                dispositivos_classificados.append(dispositivo)
        self.dispositivos = dispositivos_classificados
        return self.dispositivos

class DispositivoNormativo():
    def __init__(self, texto:str, origem: AtoNormativo, tipo:str, indice_texto:str, indice_doc:int, dispositivo_pai: Optional[str] = None) -> None:
        self.origem:AtoNormativo = origem
        self.tipo:str = tipo
        if isinstance(dispositivo_pai, str):
            self.dispositivo_pai = dispositivo_pai
        else:
            self.dispositivo_pai = None
        self.nlp: Doc = MODELO_NLP('NLP não processado')
        self.prefixo_urn: str = PREFIXO_URN
        self.indice:str = indice_texto  
        self.i = indice_doc
        self.texto = texto + '[...]'
        self.sufixo_urn: str = f'{origem.titulo}' + ':' + f'{self.tipo}' + f'{self.indice}'
        self.urn: str = self.__definir_urn()
        self.marcador_sub_dispositivo: dict = {'Art.':['§', 'Parágrafo'], '§':['I', 'II', 'III', 'IV']}
        self.sub_dispositivos = self.__identificar_sub_dispositivos()
     

    def __str__(self) -> str:
        return f'{self.urn}'
    
    def __validar_dispositivo(self, dispositivo:str):
       
       if dispositivo in HIERARQUIA_DISPOSITIVOS.keys():
           return True
       else:
           return False

    def __nlp_dispositivo(self) -> Doc:
        nlp = MODELO_NLP(self.texto)
        return nlp

    def __definir_urn(self) -> str:
        if isinstance(self.dispositivo_pai, str):
            self.urn = self.prefixo_urn + self.dispositivo_pai + ':' + self.sufixo_urn.split(':')[1]
        else:
            self.urn = self.prefixo_urn + self.sufixo_urn
        return self.urn

    def __enumerar_artigo(self) -> str:
        pass

    def __is_romano(self, token: Token) -> bool:
        try:
            roman.fromRoman(token.text)
            if token.text == token.text.upper():
                return True
        except:
            return False
        

    def __identificar_sub_dispositivos(self) -> Any:
        self.sub_dispositivos = []
        dict_dispositivos = PREFIXO_DISPOSITIVO.copy()
        tipo_sub_dispositivo = HIERARQUIA_DISPOSITIVOS[self.tipo]
        if not tipo_sub_dispositivo:
            return self.sub_dispositivos
        doc = self.origem.doc
        span = self.origem.doc[self.i+1:]
        contador = 0
        for token in span:
            if self.__is_romano(token):
                dict_dispositivos[token.text] = 'inciso'
            if token.is_sent_start:
                contador += 1
                if self.__is_romano(token) or token.text in [chave for chave, valor in dict_dispositivos.items() if valor == tipo_sub_dispositivo]:
                    if token.nbor(1).text.lower() == 'único':
                        indice = 'unico'
                    else:
                        indice = ''.join(caractere for caractere in token.nbor().text if caractere.isdigit())
                    self.sub_dispositivos.append(DispositivoNormativo(self.origem.doc[token.i:token.i+10].text,
                                                                    self.origem, tipo_sub_dispositivo,
                                                                    '.'+indice,
                                                                    token.i, self.sufixo_urn))
                elif token.text in [chave for chave, valor in dict_dispositivos.items() if valor == self.tipo]:
                    break
        return self.sub_dispositivos
    
#testes
d = AtoNormativo(r"https://repositorio.iti.gov.br/instrucoes-normativas/IN2026_36_identificacao_requerente.htm", True)
doc = d.doc

df = pd.DataFrame(
    {
    'Dispositivo':[dispositivo.urn for dispositivo in d.dispositivos], 
     'Tipo': [dispositivo.tipo for dispositivo in d.dispositivos],
     'Texto': [dispositivo.texto for dispositivo in d.dispositivos],
     'SubDispositivos': [len(dispositivo.sub_dispositivos) for dispositivo in d.dispositivos]}
)

metadados_ato_normativo = pd.DataFrame(
    {
        'Título':[d.titulo],
        'Categoria':[d.categoria],
        'Texto':[d.texto]
    }
)


for token in doc:
    if token.text.startswith('Art.') and doc[token.i-1].is_alpha:
        print(doc[token.i:token.i+3])


def validar_sequencia(texto: Doc):
    doc = texto
    log_sequencial = {'artigo':1,'paragrafo':1,'inciso':1}
    for token in doc:
        if token.text.startswith('Art.'):
            indice =''.join([digito for digito in token.nbor().text if digito.isdigit()])
            print('indice:'+indice)
            try:
                int_indice = int(indice)
            except:
                try:
                    for tk in doc[token.i:token.i+3]:
                        indice = ''.join(digito for digito in tk.text if digito.isdigit())
                        int_indice = int(indice)
                except:
                    print('digito nao encontrado')
                    continue
            if int_indice == log_sequencial['artigo']:
                log_sequencial['artigo'] += 1
                print(token.text + indice)
            else:
                print(indice)
                continue
 
data = metadados_ato_normativo.to_dict(orient='records')


print(metadados_ato_normativo)

#result = atos_normativos.insert_many(data)
#print(result.acknowledged)

print(d.hash)

client.close()