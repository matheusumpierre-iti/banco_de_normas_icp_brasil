import json
import os
from pathlib import Path
from dotenv import dotenv_values, set_key, load_dotenv
from datetime import datetime
import pandas as pd
import streamlit as st
from pymongo import MongoClient
from db import configurar_ambiente, configurar_login
from bson.objectid import ObjectId
from bson.errors import InvalidId

st.set_page_config(page_title="Demo CRUD — MongoDB", layout="wide")

# ==========================================================
# CONEXÃO COM O MONGODB
# ==========================================================

@st.cache_resource
def get_client(uri: str) -> MongoClient:
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.header(st.session_state.to_dict())


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


st.title("Demonstração CRUD — MongoDB")

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

# ==========================================================
# ABAS: LISTAR / CRIAR / ATUALIZAR / EXCLUIR
# ==========================================================
if st.session_state.logado:
    client = get_client(st.session_state.uri)
    db_name = 'atos_normativos'
    with st.sidebar:
            st.write('Coleções disponíveis:')
            colecoes = [doc for doc in client['atos_normativos'].list_collection_names()]
            selecao = st.selectbox('Coleções disponíveis:', colecoes)
            collection = client[db_name][selecao]
            collection.create_index({ "$**": "text" })
            st.session_state.pop('docs_cache', None)
            busca = st.text_input('Busca textual')
            st.button('Desconectar', width='stretch', on_click=desconectar)
           


aba_busca, aba_texto, aba_listar, aba_criar, aba_atualizar, aba_excluir = st.tabs(
    ["🔍 Busca","📖 Texto", "📋 Listar", "➕ Criar", "✏️ Atualizar", "🗑️ Excluir"]
)

# --- BUSCA ---
with aba_busca:
    resultado = buscar_texto(busca)
    for doc in resultado:
        with st.container(border=True):
            st.subheader(doc.get('texto'))
            if doc.get('subtopicos'):
                st.write([(subtopico['numero'], subtopico['texto']) for subtopico in doc['subtopicos']])


# --- TEXTO ----
with aba_texto:
    st.header(collection.find_one({'titulo':{'$exists':'true'}})['titulo'].upper())
    for doc in collection.find({'texto':{'$exists':'true'}}):
        st.subheader((doc['numero'] + ' - ' + doc['texto']))
        for subtopico in doc['subtopicos']:
            st.write(subtopico['numero'], '-',subtopico['texto'])
            
# --- LISTAR ---
with aba_listar:
    st.header(collection.find_one({'titulo':{'$exists':'true'}})['titulo'].upper())
    limite = st.number_input("Limite de resultados", min_value=1, max_value=1000, value=50)
    if st.button("Atualizar lista"):
        st.session_state.pop("docs_cache", None)
    if "docs_cache" not in st.session_state:
        try:
            st.session_state.docs_cache = listar_documentos(limite=limite)
        except Exception as e:
            st.error(f"Erro ao buscar documentos: {e}")
            st.session_state.docs_cache = []

    docs = st.session_state.docs_cache
    if not docs:
        st.info("Nenhum documento encontrado.")
    else:
        metadados = listar_documentos(limite=limite, filtro={'titulo': {'$exists':'true'}})
        conteudo = listar_documentos(limite=limite, filtro={'texto':{'$exists':'true'}})
        st.subheader('Metadados')
        tabela_metadados = st.dataframe([serializar(d) for d in metadados], width='stretch')
        st.subheader('Conteúdo')
        tabela_conteudo = st.dataframe([serializar(d) for d in conteudo], width='stretch', on_select='rerun', selection_mode='single-cell')
        linhas_selecionadas = tabela_conteudo.selection.cells
        if linhas_selecionadas:
            tabela_subtopicos = selecionar_celula(conteudo, linhas_selecionadas)
            sub_linhas_selecionadas = tabela_subtopicos.selection.cells
            if sub_linhas_selecionadas:
                pass




# --- CRIAR ---
with aba_criar:
    st.subheader("Criar novo documento")
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

# --- ATUALIZAR ---
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