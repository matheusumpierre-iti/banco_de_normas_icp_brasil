import json
from datetime import datetime
import streamlit as st
from pymongo import MongoClient
from db import configurar_ambiente, configurar_login
from bson.objectid import ObjectId
from bson.errors import InvalidId

st.set_page_config(page_title="Demo CRUD — MongoDB", layout="wide")

env = configurar_ambiente()
db_user, db_pass = configurar_login()

# ==========================================================
# CONEXÃO COM O MONGODB
# ==========================================================

URI = f"mongodb+srv://{db_user}:{db_pass}@clusterlexicp.ng8flgg.mongodb.net/?appName=ClusterLexICP"

@st.cache_resource
def get_client(uri: str) -> MongoClient:
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


with st.sidebar:
    st.header("Conexão")
    mongo_uri = URI
    db_name = st.text_input("Banco de dados", value="atos_normativos")
    collection_name = st.text_input("Coleção", value="minha_colecao")
    conectar = st.button("Conectar", width='stretch')

if "conectado" not in st.session_state:
    st.session_state.conectado = False

if conectar:
    try:
        client = get_client(URI)
        client.admin.command("ping")
        st.session_state.conectado = True
        st.sidebar.success("Conectado com sucesso!")
    except Exception as e:
        st.session_state.conectado = False
        st.sidebar.error(f"Erro ao conectar: {e}")

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


# ==========================================================
# ABAS: LISTAR / CRIAR / ATUALIZAR / EXCLUIR
# ==========================================================
if st.session_state.conectado:
    client = get_client(URI)
    with st.sidebar:
            st.write('Coleções disponíveis:')
            colecoes = [doc for doc in client['atos_normativos'].list_collection_names()]
            selecao = st.selectbox('Coleções disponíveis:', colecoes)
            collection = client[db_name][selecao]
            st.session_state.pop('docs_cache', None)

aba_texto, aba_listar, aba_criar, aba_atualizar, aba_excluir = st.tabs(
    ["📖 Texto", "📋 Listar", "➕ Criar", "✏️ Atualizar", "🗑️ Excluir"]
)

# --- TEXTO ----
with aba_texto:
    st.header(collection.find_one({'titulo':{'$exists':'true'}})['titulo'].upper())
    for doc in collection.find({'texto':{'$exists':'true'}}):
        st.subheader(doc['numero'])
        st.write(doc['texto'])
        for subtopico in doc['subtopicos']:
            st.write(subtopico['numero'],subtopico['texto'])
            
# --- LISTAR ---
with aba_listar:
    st.subheader("Documentos na coleção")
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
        st.dataframe([serializar(d) for d in docs], width='stretch')

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