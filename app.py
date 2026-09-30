import json
from datetime import datetime
import pandas as pd
import mammoth

import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId

st.set_page_config(page_title="Banco de Normas", layout='wide')

readme = 'README.md'

st.header('Banco de normas ICP-Brasil')

          

# ==========================================================
# CONEXÃO COM O MONGODB
# ==========================================================

@st.cache_resource
def get_client(uri: str) -> MongoClient:
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


#-------------------------------------
# Inicialização de variáveis da sessão
#-------------------------------------


if 'logado' not in st.session_state:
    st.session_state.logado = False

if 'tabela_docs' not in st.session_state:
    st.session_state.tabela_docs = None

if 'coletaneas' not in st.session_state:
    st.session_state.coletaneas = []

if 'modo' not in st.session_state:
    st.session_state.modo = None

if 'resultado' not in st.session_state:
    st.session_state.resultado = []

if 'ferramenta' not in st.session_state:
    st.session_state.ferramenta = 'inicial'

if 'selecao_colecao' not in st.session_state:
    st.session_state.selecao_colecao = None

if 'termo_busca' not in st.session_state:
    st.session_state.termo_busca = None

if 'db_user' not in st.session_state:
    st.session_state.db_user = None

if 'doc_selecionado' not in st.session_state:
    st.session_state.doc_selecionado = None

def conectar(db_user, db_pass, sufixo_uri):
            st.session_state.uri = f"mongodb+srv://{db_user}:{db_pass}@{sufixo_uri}"
            client = get_client(st.session_state.uri)
            try:
                client.admin.command('ping')
                st.session_state.logado = True
                st.sidebar.success("Conectado com sucesso!")
                st.session_state.db_user = db_user
                st.session_state.db_pass = db_pass
                st.session_state.sufixo_uri = sufixo_uri
                st.rerun()
            except Exception as e:
                st.session_state.logado = False
                st.sidebar.error(f"Erro ao conectar: {e}")
                
                

def login():
    with st.sidebar:
        with st.form('login-form'):
            st.header('Login no banco de dados')
            db_user = st.text_input('Usuário:', max_chars=50, type='default')
            db_pass = st.text_input('Senha:', max_chars=50, type='password')
            sufixo_uri = st.text_input('Sufixo da URI do banco de dados (após o @):', max_chars=200, type='default')
            logar = st.form_submit_button('Logar', width='stretch')
        if logar:
            conectar(db_user=db_user, db_pass=db_pass, sufixo_uri=sufixo_uri)
            st.session_state.logado = True

def desconectar():
    st.session_state.logado = False
    st.session_state.conectado = False
    st.rerun()            


with st.sidebar:
    if st.session_state.logado == False:
        login()
    else:
        st.session_state.conectado = True
        

if "conectado" not in st.session_state:
    st.session_state.conectado = False



if not st.session_state.conectado:
    st.info("Configure a conexão na barra lateral e clique em **Conectar** para começar.")
    st.stop()

#-----------------------
# Seleção de modo 
#-----------------------

with st.sidebar:
    st.write(f'Logado como **{st.session_state.db_user}**')
    st.button('Desconectar', on_click=desconectar)
    modos = {
        'Sobre':'sobre',
        'Busca':'busca',
        'Edição':'edicao',
        'Upload':'upload',
        'Minhas Coletâneas':'minhas_coletaneas'
    }
    selecao_modo = st.selectbox('Selecione o modo:', options=modos)
    st.session_state.modo = modos[selecao_modo]

    debug = st.button('Exibir session_state (debug)')

    if debug:
        debug = st.empty()
        with st.container():
            bloco_debug = st.write(st.session_state)
            fechar_debug = st.button('Fechar bloco debug')
            if fechar_debug:
                bloco_debug = st.empty()
 
# ==========================================================
# HELPERS
# ==========================================================


def serializar(doc: dict) -> dict:
    """Converte campos não-JSON-serializáveis (ObjectId, datetime) para string, só para exibição."""
    out = {}
    for k, v in doc.items():
        if isinstance(v, (ObjectId, datetime)):
            out[k] = str(v)
        else:
            out[k] = v
    return out

def expandir_celula(valor):
    """
    Recebe o conteúdo de uma célula. Se for uma lista de objetos (dicts),
    retorna um novo DataFrame com um objeto por linha.
    Caso contrário, retorna None.
    """
    if 1==1:
        pass
    if isinstance(valor, list) and len(valor) > 0 and isinstance(valor[0], dict):
        return pd.DataFrame(valor)
    return None

def expandir_texto(valor):
    if isinstance(valor, str) and len(valor) > 0:
        pass

def selecionar_celula(tabela, linhas_selecionadas):
    linha_idx, coluna_nome = linhas_selecionadas[0]
    df = pd.DataFrame(tabela)
    valor_celula = df.iloc[linha_idx][coluna_nome]
    df_expandido = expandir_celula(valor_celula)
    tabela_subtopico = st.dataframe(df_expandido, width='stretch', on_select='rerun', selection_mode='single-cell')
    return tabela_subtopico





def limpar_selecao_documento():
    st.session_state.pop('doc_selecionado',None)
    st.session_state.pop('selecao_colecao', None)
    st.session_state.ferramenta = 'inicial'

def selecao_tabela_busca(termo_busca:str):
    pass
    if st.session_state.selecao_colecao:
        st.session_state.doc_selecionado = None 
        collection = client[db_name][st.session_state.selecao_colecao]
        st.subheader(f'{st.session_state.selecao_colecao.replace('_',' ').title()}')
        dados = []
        for doc in collection.find():
            dados_tabela = {
                'Título':f'{doc['titulo'].upper()}',
                'Data de publicação':doc['data_publicacao'],
                'Ementa':doc['ementa'],
                'URN':doc['urn']
            }
            dados.append(dados_tabela)
    
        df = pd.DataFrame(dados)
        evento = st.dataframe(df, on_select='rerun',selection_mode='single-row',hide_index=True)
        linhas = evento.selection.rows
        if linhas:
            linha = df.iloc[linhas[0]]
            urn = linha['URN']
            st.session_state.doc_selecionado = collection.find_one({'urn':urn})
            st.session_state.ferramenta = 'selecao'




#Modo -> Sobre
if st.session_state.modo == 'sobre':
    st.divider(width=600)
    with open('README.md', encoding='utf8') as file:
        st.markdown(file.read())

#Modo -> Buscar
if st.session_state.modo == 'busca':
    if st.session_state.logado:
        client = get_client(st.session_state.uri)
        meta = client['atos_normativos'].get_collection('meta')
        colecoes = [colecao for colecao in meta.distinct('colecoes')]
        st.session_state.colecoes_disponiveis = [colecao['id'] for colecao in colecoes]
        db_name = 'atos_normativos'
        st.divider()

       

        #Barra de seleção de documento
        st.write('**Listar documentos**')

        #Seleção de coleção
        def selecionar_colecao(selecao:str):
            st.session_state.selecao_colecao = [colecao['id'] if colecao['display_name'] == selecao else None for colecao in colecoes][0]
            st.session_state.ferramenta = 'listar_colecao'

        def limpar_selecao_colecao():
            st.session_state.ferramenta = 'inicial'
            st.session_state['selecionar_colecao'] = None
            st.session_state['texto_busca_acervo'] = None

        with st.container():
            selecao = st.selectbox('Coleções disponíveis:', [colecao['display_name'] for colecao in colecoes], placeholder='Selecione a coleção', index=None, width=500, key='selecionar_colecao')

            with st.container(horizontal=True):
                selecionar = st.button('Listar', key='listar_colecoes', on_click=selecionar_colecao, args=(selecao,))
                limpar = st.button('Limpar', key='limpar_colecoes', on_click=limpar_selecao_colecao)

            st.session_state.selecao_colecao = [colecao['id'] if colecao['display_name'] == selecao else None for colecao in colecoes][0]
        
            st.divider(width=600)   

        def definir_termo_busca(termo_busca):
            st.session_state.termo_busca = termo_busca
            st.session_state.ferramenta = 'busca'

        #Obter dados para tabela a partir de lista completa de coleção
        def dados_lista_colecao():
            st.session_state.doc_selecionado = None 
            collection = client[db_name][st.session_state.selecao_colecao]
            st.subheader(f'{st.session_state.selecao_colecao.replace('_',' ').title()}')
            dados = []
            for doc in collection.find():
                dados_tabela = {
                    'Título':f'{doc['titulo'].upper()}',
                    'Data de publicação':doc['data_publicacao'],
                    'Ementa':doc['ementa'],
                    'URN':doc['urn']
                }
                dados.append(dados_tabela)
            return dados 

        #Obter dados para a tabela a partir de busca
        def dados_busca_colecao(colecao='instrucoes_normativas'):
            query = st.session_state.termo_busca
            st.session_state.pop('docs_cache',None)
            st.session_state.pop('doc_selecionado', None)
            st.session_state.termo_busca = texto_busca
            db = 'atos_normativos'
            resultado = []
            for colecao in st.session_state.colecoes_disponiveis:
                busca_colecao = client[db][colecao].aggregate([{
                                "$search":{
                                    "index":"busca_textual",
                                    "text":{
                                        "query":query,
                                        "path":"texto_completo"
                                    }},
                                    }])
                resultado.append([resultado for resultado in busca_colecao])
            
            st.session_state.doc_selecionado = None 
            st.subheader('Busca no acervo')
            dados = []
            for colecao in resultado:
                for doc in colecao:
                    dados_tabela = {
                        'Título':f'{doc['titulo'].upper()}',
                        'Data de publicação':doc['data_publicacao'],
                        'Ementa':doc['ementa'],
                        'URN':doc['urn']
                    }
                    dados.append(dados_tabela)
            st.session_state.ferramenta = 'busca'
            return dados

        def voltar_busca():
            st.session_state.termo_busca = None
            st.session_state.ferramenta = 'inicial' 


        #Exibir tabela (dataframe) a partir de dados de busca ou seleção
        def exibir_tabela_docs(dados: list, colecao='instrucoes_normativas'):
            df = pd.DataFrame(dados)
            evento = st.dataframe(df, on_select='rerun',selection_mode='single-row',hide_index=True)
            linhas = evento.selection.rows
            if linhas:

                linha = df.iloc[linhas[0]]
                urn = linha['URN']
                st.session_state.doc_selecionado = client['atos_normativos'][f'{colecao}'].find_one({'urn':urn})
                st.session_state.ferramenta = 'selecao'

        #Adicionar à coletânea

        def adicionar_doc_coletanea():

            with campo_adicionar:

                def confirmar_adicao():
                    for coletanea in st.session_state.coletaneas:
                        if coletanea['Nome'] == selecionar_coletanea:
                            coletanea['Normas'].append(st.session_state.doc_selecionado)
                            st.info(f'Documento {st.session_state.doc_selecionado['titulo']} adicionado à coletânea {selecionar_coletanea}')

                selecionar_coletanea = st.selectbox('Selecione a coletânea:', options=[coletanea['Nome'] for coletanea in st.session_state.coletaneas])
                botao_confirmar = st.button('Confirmar', on_click=confirmar_adicao, key=f'adicionar_colecao_a_coletanea_{selecionar_coletanea}')
                    
        #Widget de busca
        with st.container():
            texto_busca = st.text_input('Busca no acervo normativo', key='texto_busca_acervo', width=500,type='search')
            with st.container(horizontal=True):
                buscar_acervo = st.button('Buscar', on_click=definir_termo_busca, kwargs=({'termo_busca':texto_busca}))
                limpar_busca = st.button('Limpar', on_click=limpar_selecao_documento)
            if not texto_busca:
                st.session_state.pop('termo_busca', None)
            
            #Determina fonte de dados para a tabela
    if st.session_state.ferramenta == 'busca':
        dados = dados_busca_colecao()        
    elif st.session_state.ferramenta == 'listar_colecao':
        dados = dados_lista_colecao()
    else:
        dados = []
    
    with st.container(): 
        if dados:
            exibir_tabela_docs(dados)

        if st.session_state.ferramenta == 'busca':
            st.button('Voltar', on_click=voltar_busca)

    #Após seleção do documento para exibição

    if st.session_state.ferramenta == 'selecao':
        if st.session_state.selecao_colecao:
            collection = st.session_state.selecao_colecao
        if st.session_state.doc_selecionado:
            selecao_doc = st.session_state.doc_selecionado['titulo']
        else:
            st.stop()
        documento = st.session_state.doc_selecionado
        texto = documento['html']
        st.caption(f'{st.session_state.selecao_colecao} > {selecao_doc}')
        with st.container():
            st.header(documento['titulo'].upper())
            st.table(
                    {'Título': documento['titulo'].replace('.', ' ').upper(),
                    'Data de publicação': documento['data_publicacao'],
                    'categoria':documento['categoria'].replace('.', ' ').title(),
                    'Ementa':documento['ementa'],
                    'URN':documento['urn']},
                    
                    width='content'
                )

            campo_adicionar = st.container()

            with campo_adicionar: 
                botao_adicionar = st.button(label='Adicionar', on_click=adicionar_doc_coletanea)
                    


       

        #ABAS

        aba_texto, aba_referencias, aba_listar= st.tabs(
            ["📖 Texto Integral", "🔗Referências", "📋 Listar"]
        )

        # --- TEXTO ----
        ## TODO -> Ver como exibir imagem em base64
        with aba_texto:
            with st.container():
                st.markdown(texto, unsafe_allow_html=True)

        # --- REFERÊNCIAS ----
        ## TODO -> Linkar referência ao documento no banco

        with aba_referencias:
            for referencia in documento['documentos_referenciados']:
                st.markdown(f'**{referencia['referencia'].upper()}**')
                st.table({
                    'Tipo':referencia['tipo'],
                    'Numero':referencia['numero'],
                    'Órgão':referencia['orgao'],
                    'Data de publicação':referencia['data_publicacao']
                }, width='content', )
            st.write(documento['documentos_referenciados'])


        # --- LISTAR ---
        with aba_listar:
            st.write('Clique na linha para ver dispositivos')
            lista_dispositivos = documento['dispositivos']
            df = pd.DataFrame(lista_dispositivos)
            evento = st.dataframe(
                df,
                on_select='rerun',
                selection_mode='single-row'
            )
            linhas = evento.selection.rows
            if linhas:
                linha = df.iloc[linhas[0]]

#Modo -> Minhas coletâneas
if st.session_state.modo == 'minhas_coletaneas':
    st.subheader('Minhas Coletâneas')
    aba_nova_coletanea, aba_ver_coletaneas = st.tabs(['Nova Coletânea', 'Ver Coletâneas'])

    def criar_coletanea(nome_coletanea, descricao_coletanea):
        coletanea = {
            'Nome':nome_coletanea,
            'Descrição':descricao_coletanea,
            'Normas':[]
            }

        coletaneas = [col['Nome'] for col in st.session_state.coletaneas]

        if coletanea['Nome'] in coletaneas:
            st.warning(f'Coletânea chamada {coletanea['Nome']} já existe, escolha um nome diferente.')
        else:
            st.session_state.coletaneas.append(coletanea)
            st.info('Coletânea criada com sucesso! Acesse a aba **Ver Coletâneas** ou use o modo de **Busca** para adicionar documentos.') 

    with aba_nova_coletanea:
        nome_coletanea = st.text_input('Nome da coletânea:')
        descricao_coletanea = st.text_input('Descrição:')

        if nome_coletanea and descricao_coletanea:
            criar = st.button('Criar', key='botao_criar_coletanea', on_click=criar_coletanea, args=(nome_coletanea, descricao_coletanea), disabled=False)
        else:
            criar = st.button('Criar', key='botao_criar_coletanea', on_click=criar_coletanea, args=(nome_coletanea, descricao_coletanea), disabled=True)

    with aba_ver_coletaneas:
        for coletanea in st.session_state.coletaneas:
            st.table([f'##### **{coletanea['Nome']}**', coletanea['Descrição']])
            with st.container(horizontal=True):
                st.button('Exportar em JSON', key=f'json_{coletanea['Nome']}')
                st.button('Exportar em HTML', key=f'html_{coletanea['Nome']}')
                st.button('Excluir coletânea', key=f'excluir_{coletanea['Nome']}', type='tertiary')

            st.write('**Documentos da coletânea:**')
            if len(coletanea['Normas']) == 0:
                st.info('Sua coletânea ainda está vazia. Utilize o modo de **Busca** para adicionar documentos.')
            else:
                st.dataframe([norma for norma in coletanea['Normas']], height=150)

            st.divider()
        
    
#Modo -> Upload
if st.session_state.modo == 'upload':
    def envio_de_arquivo() -> None:
        st.header('Upload de arquivos')
        st.caption('Envie documento em .docx para inserção no banco de dados')
        arquivo_enviado = st.file_uploader(label='Selecionar arquivo', type='.docx',accept_multiple_files=False)
        if arquivo_enviado:
            convertido = mammoth.convert_to_html(arquivo_enviado)
            if convertido:
                st.download_button('Baixar arquivo .html', convertido.value, file_name='download.html')
            exibir_html = st.button('Exibir conteúdo', )
            if exibir_html:
                html = st.markdown(convertido.value, unsafe_allow_html=True)
                    
        
    envio_de_arquivo()

# --- ATUALIZAR ---
def atualizar():
    with aba_atualizar:
        st.subheader("Atualizar documento existente")
        doc_id_atualizar = st.text_input("ID do documento (_id)", key="id_atualizar")
        campos_atualizar = st.text_area(
            "Campos a atualizar (JSON — só o que precisa mudar)",
            value='{\n  "valor": 456\n}',
            height=150,
            key="campos_atualizar",
        )
        if st.button("Atualizar documento"):
            try:
                dados = json.loads(campos_atualizar)
                qtd = atualizar_documento(doc_id_atualizar, dados)
                if qtd:
                    st.success("Documento atualizado com sucesso.")
                    st.session_state.pop("docs_cache", None)
                else:
                    st.warning("Nenhum documento foi modificado (verifique o ID).")
            except json.JSONDecodeError as e:
                st.error(f"JSON inválido: {e}")
            except InvalidId:
                st.error("ID inválido.")
            except Exception as e:
                st.error(f"Erro ao atualizar documento: {e}")

# --- EXCLUIR ---
def excluir():
    with aba_excluir:
        st.subheader("Excluir documento")
        doc_id_excluir = st.text_input("ID do documento (_id)", key="id_excluir")
        confirmar = st.checkbox("Confirmo que desejo excluir este documento")
        if st.button("Excluir documento", disabled=not confirmar):
            try:
                qtd = excluir_documento(doc_id_excluir)
                if qtd:
                    st.success("Documento excluído com sucesso.")
                    st.session_state.pop("docs_cache", None)
                else:
                    st.warning("Nenhum documento encontrado com esse ID.")
            except InvalidId:
                st.error("ID inválido.")
            except Exception as e:
                st.error(f"Erro ao excluir documento: {e}")
