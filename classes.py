import io
import pdfplumber
import requests
import pandas as pd
import json
from docx import Document
import re

from main import inicializar_nlp
from pathlib import Path
from functools import lru_cache
from typing import Any
from parser_lei import parse_lei
from parser_tabelas import parse_tabelas_pdf
from parser_topicos import parse_topicos
from parser_texto_completo import parser_texto_bruto
from detectar_ementa import detectar_ementa
from typing import Optional
from main import definir_constantes
from spacy.tokens import Token, Doc
from pdfplumber.pdf import PDF
from bs4 import BeautifulSoup

modelo_nlp, tipo_ato_normativo, prefixo_urn, prefixo_dispositivo, hierarquia_dispositivos, data = definir_constantes()

if __name__ =='__main__':
    nlp = inicializar_nlp()

#Classes  
class AtoNormativo:
    @lru_cache(maxsize=None)
    def __init__(self, arquivo:str = None, nlp:bool = False, arquivo_upload: io.BytesIO = None, url: str = None) -> None:
        if arquivo: 
            self.origem = arquivo
        elif arquivo_upload:
             self.origem = arquivo_upload
        elif url: 
             self.origem = url
        else:
             raise TypeError('Insira caminho ou url do documento.')
        self.url: Optional[str] = None
        self.formatos_suportados = ['.pdf','.md','.txt','.odt','.doc','.docx']
        self.titulo: str = ''
        self.categoria: Optional[str] = None
        self.texto_completo: str
        self.doc: Any = None
        if arquivo or url:
            self.__obter_conteudo()
        elif arquivo_upload:
             self.texto_completo = Document(self.origem)
             

        if nlp == True:
            self.modelo_nlp = modelo_nlp
            self.__processar_nlp(self.texto_completo)
            self.__obter_titulo(self.texto_completo)
            self.__processar_tabelas(self.texto_completo)
            self.__obter_versao(self.texto_completo)
            self.__obter_data(self.texto_completo)
            self.urn = f'{PREFIXO_URN}:{self.titulo}:{self.data}'
            self.doc = None

    def to_dict(self) -> dict:
         dicionario = {
              'titulo':self.titulo,
              'texto_completo':self.texto,
              'tabelas':self.tabelas,
              'categoria':self.categoria if self.categoria else 'Desconhecida',
              'versao':self.versao,
              'data':self.data,
              'ementa':'N.A.',
              'urn':self.urn
         }
         return dicionario

    def __obter_conteudo_upload(self):
         pass

    def __obter_data(self):
        for token in self.doc:
            if token.text.lower() in DATA.keys():
                span = self.doc[token.i-2:token.i+3].text.replace(r'\n', ' ')
        m = re.match(r"(\d{1,2}) de (\w+) de (\d{4})", span.strip().replace(r'\n', ''), re.IGNORECASE)
        if not m:
            return('Data não identificada')
        dia, mes_nome, ano = m.groups()
        mes = DATA.get(mes_nome.lower())
        if mes is None:
            return 'Data não identificada'
        self.data = f"{int(dia):02d}.{mes}.{ano}"
        return self.data
    
    def __processar_nlp(self):
        self.doc = modelo_nlp(self.texto_completo)
        return self.doc

    def __obter_titulo(self):
        for token in self.doc[0:50]:
            if token.text.lower().startswith('doc-icp'):
                prefixo_titulo = 'doc.icp'
                span = self.doc[token.i:token.i+3]
                sufixo_titulo = ''
                for i in range(0, len(span.text)):
                                    if span.text[i].isdigit():
                                        sufixo_titulo += span.text[i]
                                        self.titulo = prefixo_titulo +'.' + sufixo_titulo[:2] + '.' + sufixo_titulo[2:]
                break
            elif token.text.lower() in TIPO_ATO_NORMATIVO.keys():
                prefixo_titulo = TIPO_ATO_NORMATIVO[token.text.lower()]
                sufixo_titulo = ''
                span = self.doc[token.i:token.i+6]
                for i in range(0, len(span.text)):
                    if span.text[i].isdigit():
                        sufixo_titulo += span.text[i]
                self.titulo = prefixo_titulo +'.'+sufixo_titulo
                break
            else:
                self.titulo = 'Desconhecido'
        return self.titulo

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
        elif self.origem.isinstance(io.BytesIO):
             self.__processar_texto_doc()
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
        doc = Path(self.origem)
        self.texto = parser_texto_bruto(doc)['texto_completo']
        return self.texto

    def __processar_tabelas(self):
        doc = Path(self.origem)
        self.tabelas = parser_texto_bruto(doc)['tabelas']
        return self.tabelas

    def __obter_versao(self):
        """Busca número de versão do documento"""
        for token in self.doc[0:50]:
            if token.text.lower().startswith('versão'):
                versao = ''
                for char in self.doc[token.i:token.i+2].text:
                    if char.isdigit():
                        versao += char
                    elif char == '.':
                        versao += char
                self.versao = versao
                break
            else:
                self.versao = 'n.a.'
        return self.versao

if __name__ == '__main__':
     ato = AtoNormativo(r'https://repositorio.iti.gov.br/instrucoes-normativas/IN2026_37_altera_DOC-ICP-05.03.htm', True)
     dicionario = json.dumps(ato.to_dict(), ensure_ascii=False)
     print(dicionario)
