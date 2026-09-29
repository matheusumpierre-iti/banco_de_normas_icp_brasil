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

if 'coletanea' not in st.session_state:
    st.session_state.coletanea = []

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
        'Upload':'upload'
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



def busca_textual(texto_busca:str, colecao = 'instrucoes_normativas'):
    query = texto_busca
    st.session_state.pop('docs_cache',None)
    st.session_state.termo_busca = texto_busca
    db = 'atos_normativos'
    collection = colecao
    resultado = client[db][collection].aggregate([{
                    "$search":{
                        "index":"busca_textual",
                        "text":{
                            "query":query,
                            "path":"texto_completo"
                        }},
                        }])
    st.session_state.resultado = list(resultado)
    st.session_state.ferramenta = 'busca'
    st.session_state.selecao_colecao = colecao

def limpar_selecao_documento():
    st.session_state.pop('doc_selecionado',None)
    st.session_state.ferramenta = 'inicial'




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
        #colecoes = meta_colecoes.distinct('colecoes')
        db_name = 'atos_normativos'
        st.divider()

        # Alterna para o modo Busca se a barra de busca é preenchida
        texto_busca = st.text_input('Busca no acervo normativo', width=500,type='search')
        with st.container(horizontal=True):
            buscar_acervo = st.button('Buscar', on_click=busca_textual, kwargs=({'texto_busca':texto_busca}))
            limpar_busca = st.button('Limpar', on_click=limpar_selecao_documento)
        if not texto_busca:
            st.session_state.ferramenta = 'inicial'

        st.divider(width=600)

        #Barra de seleção de documento
        st.write('**Selecionar documento**')

        #Seleção de coleção
        selecao = st.selectbox('Coleções disponíveis:', [colecao['display_name'] for colecao in colecoes], placeholder='Selecione a coleção', index=None, width=500)
        st.session_state.selecao_colecao = [colecao['id'] if colecao['display_name'] == selecao else None for colecao in colecoes][0]
    
        def selecao_tabela():

            def selecionar_linha(titulo): 
                collection = client[db_name][st.session_state.selecao_colecao]
                documentos = [doc for doc in collection.distinct(titulo)]

            if st.session_state.selecao_colecao:
                st.session_state.doc_selecionado = None 
                collection = client[db_name][st.session_state.selecao_colecao]
                documentos = [(i, doc) for (i, doc) in enumerate(collection.distinct('titulo'))]
                st.subheader(f'{st.session_state.selecao_colecao.replace('_',' ').title()}')
                dados = []
                for i, doc in enumerate(collection.find()):
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

        selecao_tabela()

                    
       
    def selecionar_por_busca(doc):
        st.session_state.pop('docs_cache', None)
        st.session_state.doc_selecionado = None
        st.session_state.doc_selecionado = doc  # guarda o documento escolhido
        st.session_state.ferramenta = 'selecao'

    if st.session_state.ferramenta == 'busca':
        def busca_v2(i:int, doc):
            key = i
            with st.container(border=False, width='stretch'):
                identificador = doc['titulo']
                indice_busca = doc['texto_completo'].lower().find(texto_busca.lower())
                destaque_busca = doc['texto_completo'][indice_busca-150:indice_busca+150].replace(texto_busca, f'**{texto_busca}**'),
                with st.container(horizontal=True):
                    tabela_busca = {
                            'Titulo':f'**{identificador}**'.upper(),
                            'Resultado da busca':destaque_busca,
                            }
                    st.table(border=True, data=tabela_busca, height=150)
                    st.button(key=f'botao_{key}',label='Abrir Documento', on_click=selecionar_por_busca, args=(doc,))

        for i, doc in enumerate(st.session_state.resultado):
            busca_v2(i, doc)

                
    def voltar_busca():
        st.session_state.ferramenta = 'busca' 

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
        st.header(documento['titulo'].upper())
        st.table(
                {'Título': documento['titulo'].replace('.', ' ').upper(),
                'Data de publicação': documento['data_publicacao'],
                'categoria':documento['categoria'].replace('.', ' ').title(),
                'Ementa':documento['ementa'],
                'URN':documento['urn']},
                
                width='content'
            )

        #Adicionar à coletânea
        def adicionar_doc_coletanea():
            if st.session_state.doc_selecionado:
                st.session_state.coletanea.append(st.session_state.doc_selecionado)

        botao_adicionar = st.button(label='Adicionar', on_click=adicionar_doc_coletanea)
        if botao_adicionar:
            st.info('Documento adicionado à coletânea!')
        

        #ABAS

        aba_texto, aba_referencias, aba_listar, aba_atualizar, aba_excluir = st.tabs(
            ["📖 Texto Integral", "🔗Referências", "📋 Listar", "✏️ Atualizar", "🗑️ Excluir"]
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
    def exibir_coletaneas():
        pass
    
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
