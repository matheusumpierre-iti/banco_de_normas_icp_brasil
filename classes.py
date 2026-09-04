class old_DocumentoURL:
    '''Lida com documentos hospedados em URL. Tem o arquivo em memória, o texto puro e o doc NLP como propriedades.'''
    def __init__(self, url: str) -> None:
        self.url = url
        self.html = requests.get(url)
        self.arquivo = io.BytesIO(self.html.content)
        self.texto_puro = self.__uniformizar_formato()
        self.doc_nlp = MODELO_NLP(self.texto_puro)

    def __uniformizar_formato(self):
        if self.url.endswith('.pdf'):
            self.pdf = pdfplumber.open(self.arquivo)
            self.numero_paginas = len(self.pdf.pages)
            self.texto_puro = self.__extrair_texto_pdf(0, self.numero_paginas)
        elif self.url.endswith(('.html','.htm')):
            print('Convertendo HTML...')
            self.texto_puro = BeautifulSoup(self.arquivo, 'lxml').text
            #self.texto_puro = pypandoc.convert_file(self.arquivo, format='html', to='plain')
            print('Conversão HTML: Sucesso')
        else:
            try:
                self.texto_puro = BeautifulSoup(self.arquivo, 'html.parser').text
                print('Conversão HTML: Sucesso')
            except:
                self.texto_puro = 'URL não direciona a um elemento .html ou .pdf.'
        return self.texto_puro
    
    def __extrair_texto_pdf(self, pagina_inicial: int = 0, pagina_final: int = 0):
        self.texto = str()
        for page in self.pdf.pages[pagina_inicial:pagina_final]:
            texto_pagina = page.extract_text()
            self.texto += texto_pagina
        return self.texto
    
class BancoDeDados:
    '''Lida com direcionamento para o banco de dados'''
    def __init__(self, arquivo:str) -> None:
        self.arquivo = arquivo
        self.db = sqlite3.connect(self.arquivo)
        pass 

class old_ConversorHTML():
    '''Converte um arquivo de texto em um objeto HTML estruturado. Herda métodos das classes ModeloNLP para a inicialização do modelo, '''

    def __init__(self, filepath:str) -> None:
        self.arquivo = filepath
        self.parser = HTMLParser
        self.html_doc = self.doc_to_html()
        self.convertido = self.parse_html()
        self.doc = MODELO_NLP(self.convertido.text)
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


class old_AtoNormativo():
    '''Usa regras definidas para identificar o tipo de ato normativo (DOC-ICP, Resolução, Instrução Normativa)'''
    
    def __init__(self, url) -> None:
        super().__init__(url)
            
        self.regras = {
        'instrução normativa':'Instrução Normativa',
        'resolução':'Resolução',
        'portaria' : 'Portaria'
        }

        self.rotulo = self.rotular_documento()
    
    def rotular_documento(self):
        for key, value in self.regras.items():
            if self.doc_nlp[0].text.lower().startswith(key):
                rotulo = value
            else:
                rotulo = 'Desconhecido'
            return rotulo

class ExemploAtoNormativo():
    def __init__(self) -> None:
        self.texto_artigo = 'Art. 2º  Fica aprovada a versão 4.0 do Documento Procedimentos para Identificação Biométrica na ICP-Brasil (DOC-ICP-05.03);'
        self.texto_paragrafo = '§1º  Os requisitos e procedimentos deste Regulamento não são exaustivos.'
        self.texto_inciso = 'I -   comparecimento presencial;'
        pass