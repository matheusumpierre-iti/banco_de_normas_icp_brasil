import json
from datetime import datetime
import pandas as pd

import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId

st.set_page_config(page_title="Banco de Normas", layout='wide')

readme = 'README.md'

st.header('Banco de normas ICP-Brasil')
st.write('Busque no acervo normativo ou selecione um documento:')

debug = st.button('Exibir session_state (debug)')

if debug:
    debug = st.empty()
    with st.container():
       bloco_debug = st.write(st.session_state)
       fechar_debug = st.button('Fechar bloco debug')
       if fechar_debug:
           bloco_debug = st.empty()
           

# ==========================================================
# CONEXÃO COM O MONGODB
# ==========================================================

@st.cache_resource
def get_client(uri: str) -> MongoClient:
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


if 'logado' not in st.session_state:
    st.session_state.logado = False

st.session_state.ferramenta = 'inicial'

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



# ==========================================================
# GANCHOS PARA SUAS FUNÇÕES DE CRUD JÁ EXISTENTES
# Troque o corpo destas funções pelas suas implementações reais,
# ou apague-as e importe suas próprias funções, ex.:
#   from meu_crud import listar_documentos, criar_documento, ...
# ==========================================================




def listar_documentos(filtro: dict | None = None, limite: int = 50):
    """TODO: troque pela sua função de listagem, se já tiver uma."""
    filtro = filtro or {}
    return list(collection.find(filtro).limit(limite))

def buscar_texto(texto_busca:str):
    busca = collection.find({'$text':{'$search':texto_busca}})
    resultado = [doc for doc in busca]
    return resultado

def criar_documento(dados: dict):
    """TODO: troque pela sua função de criação."""
    resultado = collection.insert_one(dados)
    return resultado.inserted_id

def atualizar_documento(doc_id: str, dados: dict):
    """TODO: troque pela sua função de atualização."""
    resultado = collection.update_one({"_id": ObjectId(doc_id)}, {"$set": dados})
    return resultado.modified_count


def excluir_documento(doc_id: str):
    """TODO: troque pela sua função de exclusão."""
    resultado = collection.delete_one({"_id": ObjectId(doc_id)})
    return resultado.deleted_count


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

st.session_state.resultado = []

def busca_textual(texto_busca:str, colecao = 'instrucoes_normativas') -> list:
    query = texto_busca
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
    st.session_state.resultado = resultado

# ==========================================================
# ABAS: LISTAR / CRIAR / ATUALIZAR / EXCLUIR
# ==========================================================

if st.session_state.logado:
    client = get_client(st.session_state.uri)
    meta = client['atos_normativos'].get_collection('meta')
    colecoes = [colecao for colecao in meta.distinct('colecoes')]
    #colecoes = meta_colecoes.distinct('colecoes')
    db_name = 'atos_normativos'
    st.session_state.inicial = True
    st.divider()
    # Alterna para o modo Busca se a barra de busca é preenchida
    texto_busca = st.text_input('Busca no acervo normativo', width=500,type='search')
    buscar_acervo = st.button('Buscar', kwargs=({'texto_busca':texto_busca}))
    if buscar_acervo:
        busca_textual(texto_busca)
        st.session_state.ferramenta = 'busca'

    st.divider(width=600)

    #Barra de seleção de documento
    st.write('**Selecionar documento**')
    selecao = st.selectbox('Coleções disponíveis:', [colecao['display_name'] for colecao in colecoes], placeholder='Selecione a coleção', index=None, width=500)
    selecao_colecao = [colecao['id'] if colecao['display_name'] == selecao else None for colecao in colecoes][0]

    if selecao_colecao:
        st.session_state.colecao_selecionada = True
        collection = client[db_name][selecao_colecao]
        documentos = [doc for doc in collection.distinct('titulo')]
        selecao_doc = st.selectbox('Selecione o documento',documentos, placeholder='Selecione o documento', index=None, width=500)
        if selecao_doc:
            st.session_state.pop('docs_cache', None)
            busca = st.text_input('Busca textual', width=500)
            st.session_state.documento_selecionado = True
            st.session_state.ferramenta = 'selecao'
        elif selecao_colecao and not selecao_doc:
            st.info('Selecione um documento.', width=500)

            
                
if st.session_state.ferramenta == 'inicial':
    st.divider(width=600)
    with open('README.md', encoding='utf8') as file:
        st.markdown(file.read())
    
if st.session_state.ferramenta == 'busca':

    def selecionar_por_busca():
        st.session_state.pop('docs_cache', None)
        st.session_state.documento_selecionado = True
        st.session_state.ferramenta = 'selecao'


    keys = 0
    for doc in st.session_state.resultado:
        keys += 1
        with st.container(border=False, width='stretch'):
            indice_busca = doc['texto_completo'].lower().find(texto_busca.lower())
            destaque_busca = doc['texto_completo'][indice_busca-250:indice_busca+250]
            botao_selecionar = st.button(f" **{doc['titulo']}**\n\n{doc['data_publicacao']}\n\n'{destaque_busca}','...'", key=f'botao_{keys}', use_container_width=True)
            
    if botao_selecionar:
        selecao_doc = doc['titulo']
            

if st.session_state.ferramenta == 'selecao':
    documento = collection.find_one({'titulo':f'{selecao_doc}'})
    texto = documento['html']
    st.caption(f'{selecao} > {selecao_doc}')
    st.header(documento['titulo'])
    st.table(
            {'Título': documento['titulo'].replace('.', ' ').title(),
            'Data de publicação': documento['data_publicacao'],
            'categoria':documento['categoria'].replace('.', ' ').title(),
            'Ementa':documento['ementa'],
            'URN':documento['urn']},
            

            width='content'
        )

    aba_texto, aba_listar, aba_atualizar, aba_excluir = st.tabs(
        ["📖 Texto Integral", "📋 Listar", "✏️ Atualizar", "🗑️ Excluir"]
    )

    # --- TEXTO ----
    with aba_texto:
        with st.container():
            st.markdown(texto, unsafe_allow_html=True)
           

    # --- BUSCA ---
    def busca():
        with aba_busca:
            resultado = buscar_texto(busca)
            for doc in resultado:
                with st.container(border=True):
                    st.subheader(doc.get('texto'))
                    if doc.get('subtopicos'):
                        st.write([(subtopico['numero'], subtopico['texto']) for subtopico in doc['subtopicos']])
                
    # --- LISTAR ---
    with aba_listar:
        lista_dispositivos = documento['dispositivos']
        for dispositivo in lista_dispositivos:
            st.write(dispositivo)
        

# --- CRIAR ---
def envio_de_arquivo() -> None:
    st.session_state.arquivo_enviado = True


    st.subheader("Criar novo documento")
    st.write("Selecione a opção de envio via JSON ou upload de arquivo:")
    aba_json, aba_upload = st.tabs(["JSON","Upload"])
    with aba_json:
        st.caption("Informe o conteúdo do documento em formato JSON.")
        novo_doc_texto = st.text_area(
            "Documento (JSON)",
            value='{\n  "nome": "exemplo",\n  "valor": 123\n}',
            height=180,
        )
        if st.button("Criar documento"):
            try:
                dados = json.loads(novo_doc_texto)
                novo_id = criar_documento(dados)
                st.success(f"Documento criado com _id: {novo_id}")
                st.session_state.pop("docs_cache", None)
            except json.JSONDecodeError as e:
                st.error(f"JSON inválido: {e}")
            except Exception as e:
                st.error(f"Erro ao criar documento: {e}")
    with aba_upload:
        st.session_state.arquivo_enviado = False
        envio = st.file_uploader("Envie o arquivo em formato .docx", accept_multiple_files=False, on_change=envio_de_arquivo)
        if envio:
            if envio.readable() and envio.name.endswith('.docx'):
                st.info('Envio feito com sucesso.')
                st.session_state.arquivo_enviado = True
            else:
                st.error('Arquivo com erro ou não suportado. Verifique se está no formato .docx')
            arquivo_upload = AtoNormativo(arquivo_upload=envio, nlp=False).texto_completo
            colunas1 = st.columns(2)
            with colunas1[0]:
                st.caption('**Texto completo do arquivo enviado:**')
                paragrafos = [paragraph.text for paragraph in arquivo_upload.paragraphs]
                with st.container(border=True, width='content', height=300):
                    for paragraph in arquivo_upload.paragraphs:
                        st.write(paragraph.text)
                        paragrafos.append(paragraph.text)
            with colunas1[1]:
                st.text_area('Editar texto',placeholder=paragrafos)
            
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