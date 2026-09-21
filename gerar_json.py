"""
gerar_json_norma.py

Converte um documento .docx de um ato normativo brasileiro (Instrução
Normativa, Lei, Decreto, Resolução, Portaria etc.) em um objeto JSON
estruturado, com os campos:

    - titulo                 (epígrafe do ato: tipo + número + data)
    - categoria               (tipo do ato, ex.: "Instrução Normativa")
    - data_publicacao         (ISO: AAAA-MM-DD)
    - ementa
    - documentos_referenciados
    - dispositivos            (Art. / § / inciso / alínea, aninhados)
    - controle_alteracoes     (relação tipo de alteração -> documento)
    - urn

ESTRATÉGIA
----------
Documentos de atos normativos publicados seguem, quase sempre, um
padrão de ESTILOS de parágrafo do Word (herdado de templates oficiais
como os da Casa Civil / CGNPE):

    *EPÍGRAFE*    -> título/identificação do ato (e, ao final do
                     documento, também o(s) bloco(s) de assinatura,
                     que usam o mesmo estilo)
    *EMENTA*      -> resumo do que o ato faz
    *PREÂMBULO*   -> fundamentação legal ("no uso das atribuições...")
    *ATO* (corpo) -> os "Art.", "§", incisos, alíneas

Por isso a extração é feita PRIMEIRO por nome de estilo do parágrafo
(mais robusto) e, quando o estilo não ajuda (documento sem os estilos
oficiais), cai para heurísticas por regex sobre o texto puro.

O parsing de "Dispositivos" (Art./§/inciso/alínea) REAPROVEITA
integralmente o `parser_lei.py` já existente — nenhuma lógica de
sequência foi duplicada aqui.

Uso:
    python gerar_json_norma.py caminho/para/ato.docx [saida.json]
"""

import os
import re
import sys
import json
import unicodedata

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

# reaproveita o parser de Art./§/inciso/alínea já existente
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser_lei import parse_lei


# ---------------------------------------------------------------------------
# Vocabulário de tipos de ato conhecidos (usado para achar a "categoria"
# e para reconhecer citações de outros documentos no texto)
# ---------------------------------------------------------------------------

# Ordem importa: tipos compostos (mais específicos) antes dos genéricos,
# para o regex não casar só a parte comum (ex.: "Lei Complementar" antes
# de "Lei"; "Decreto-Lei" antes de "Decreto").
TIPOS_ATO = [
    "Instrução Normativa",
    "Lei Complementar",
    "Decreto-Lei",
    "Decreto",
    "Medida Provisória",
    "Emenda Constitucional",
    "Resolução",
    "Portaria",
    "Deliberação",
    "Circular",
    "Ato Declaratório",
    "Lei",
]

TIPOS_ATO_RE = "|".join(
    re.escape(t).replace(r"\ ", r"\s+") for t in TIPOS_ATO
)

MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

# Reconhece citações de atos normativos no formato brasileiro padrão:
#   "Instrução Normativa ITI nº 15, de 18 de novembro de 2020"
#   "Decreto n° 12.103, de 8 de julho de 2024"
#   "Resolução n° 33 do Comitê Gestor da ICP-Brasil, de 21 de outubro de 2004"
CITACAO_RE = re.compile(
    r"(?P<tipo>" + TIPOS_ATO_RE + r")"
    r"(?:\s+(?P<sigla_orgao>[A-ZÀ-Ú]{2,10}))?"
    r"\s*n?[ºo°]?\.?\s*(?P<numero>[\d./-]+)"
    r"(?:\s*,?\s*\((?P<referencia_extra>[^)]+)\))?"
    r"(?:\s+do\s+(?P<orgao_do>[^,]+?)|\s+da\s+(?P<orgao_da>[^,]+?))?"
    r"\s*,\s*de\s+(?P<dia>\d{1,2})\s+de\s+(?P<mes>[A-Za-zçãéíóúÇÃÉÍÓÚ]+)\s+de\s+(?P<ano>\d{4})",
    re.IGNORECASE,
)

# Palavras-chave de controle de alterações -> tipo normalizado.
# A ordem importa: expressões mais específicas antes das mais genéricas
# (ex.: "redação dada pela" antes de um "altera" solto).
ALTERACAO_KEYWORDS = [
    (r"alterad[ao]s?\s+pel[ao]", "alterado_por"),
    (r"redaç[aã]o\s+dada\s+pel[ao]", "redacao_dada_por"),
    (r"consolidad[ao]\s+pel[ao]", "consolidado_por"),
    (r"passa\s+a\s+vigorar", "passa_a_vigorar"),
    (r"revis[ao]d[ao]?\s+pel[ao]|^revisa\b|\brevisa\s+", "revisa"),
    (r"revogad[ao]s?\s+pel[ao]", "revogado_por"),
    (r"\baltera\b", "altera"),
    (r"\brevoga\b", "revoga"),
]


# Palavras que costumam iniciar uma legenda de tabela (reaproveitado de
# parse_documento.py)
CAPTION_KEYWORDS = re.compile(
    r"^\s*(tabela|quadro|table|anexo|figura)\s*\d*[\-:.)]?\s*",
    re.IGNORECASE,
)


def looks_like_caption(texto: str) -> bool:
    """Heurística simples para saber se um parágrafo é legenda de tabela
    (mesma lógica de parse_documento.py)."""
    return bool(texto) and bool(CAPTION_KEYWORDS.match(texto.strip()))


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def slugify(texto: str) -> str:
    """Normaliza texto para um slug ascii, minúsculo, separado por hífens."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    sem_acento = sem_acento.lower()
    sem_acento = re.sub(r"[^a-z0-9]+", "-", sem_acento)
    return sem_acento.strip("-")


def data_para_iso(dia, mes_nome, ano) -> str | None:
    mes_nome_norm = slugify(mes_nome).replace("-", "")
    mes = MESES_PT.get(mes_nome_norm)
    if mes is None:
        return None
    try:
        return f"{int(ano):04d}-{mes:02d}-{int(dia):02d}"
    except (TypeError, ValueError):
        return None


def iter_block_items(parent):
    """
    Itera parágrafos e tabelas de um documento python-docx NA ORDEM em
    que aparecem no arquivo (a API padrão do python-docx só expõe
    `document.paragraphs` e `document.tables` separadamente, perdendo
    a ordem/intercalação original).
    """
    if isinstance(parent, docx.document.Document):
        parent_elm = parent.element.body
    else:
        raise ValueError("Tipo de parent não suportado")

    for child in parent_elm.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def tabela_para_texto(tabela: Table) -> str:
    """Serializa uma tabela como texto simples, linha a linha, células
    separadas por ' | ', para ser anexada como conteúdo/continuação do
    dispositivo em que a tabela está inserida."""
    linhas = []
    for row in tabela.rows:
        celulas = [cell.text.strip() for cell in row.cells]
        # remove duplicação de células mescladas (mesmo texto repetido
        # em células adjacentes) mantendo a ordem
        celulas_dedup = []
        for c in celulas:
            if not celulas_dedup or celulas_dedup[-1] != c:
                celulas_dedup.append(c)
        linha = " | ".join(c for c in celulas_dedup if c)
        if linha.strip():
            linhas.append(linha)
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Extração por estilo de parágrafo (estratégia principal)
# ---------------------------------------------------------------------------

def classificar_estilo(nome_estilo: str) -> str:
    """Mapeia o nome do estilo do Word para uma categoria conhecida.
    Funciona com os estilos oficiais (ex.: 'CGNPE ATO EPÍGRAFE') e é
    tolerante a variações, casando por substring em minúsculo."""
    if not nome_estilo:
        return "outro"
    s = nome_estilo.lower()
    if "epígrafe" in s or "epigrafe" in s:
        return "epigrafe"
    if "ementa" in s:
        return "ementa"
    if "preâmbulo" in s or "preambulo" in s:
        return "preambulo"
    if "ato" in s:
        return "corpo"
    return "outro"


def extrair_blocos(caminho_docx: str):
    """
    Percorre o .docx UMA ÚNICA VEZ, na ordem original, e devolve um
    dicionário com:

      - o texto agrupado por papel estrutural (epígrafe/ementa/
        preâmbulo/corpo), usado pelos campos já existentes;
      - o texto do corpo já com as tabelas intercaladas como
        continuação do dispositivo aberto no momento (necessário para
        o parser_lei.py enxergar o conteúdo das tabelas como parte do
        artigo em que estão);
      - "texto_completo": todo o texto dos parágrafos do documento,
        em ordem, SEM as divisões estruturais (título/ementa/
        preâmbulo/corpo tudo junto, um parágrafo por linha) -- é só a
        leitura linear do arquivo, sem o conteúdo das tabelas (que vai
        no campo "tabelas" abaixo, evitando duplicar a mesma
        informação em dois formatos diferentes);
      - "tabelas": lista, na ordem em que aparecem, de
        {"legenda": ..., "linhas": [[célula, célula, ...], ...]},
        reaproveitando a heurística de legenda de parse_documento.py
        (`looks_like_caption`): primeiro tenta o parágrafo ANTES da
        tabela; se não parecer legenda, tenta o parágrafo DEPOIS.
    """
    documento = docx.Document(caminho_docx)
    blocos_ordenados = list(iter_block_items(documento))

    epigrafes = []      # pode haver mais de uma (título + assinatura)
    ementas = []
    preambulo_partes = []
    corpo_linhas = []    # cada item é uma "linha" para o parser_lei
    texto_completo_partes = []
    tabelas = []

    ultimo_papel_corpo_visto = False
    ultima_legenda_candidata = None  # último parágrafo de texto visto

    for idx, bloco in enumerate(blocos_ordenados):
        if isinstance(bloco, Paragraph):
            texto = bloco.text.strip()
            estilo = bloco.style.name if bloco.style else ""
            papel = classificar_estilo(estilo)

            if texto:
                texto_completo_partes.append(texto)
                ultima_legenda_candidata = texto

            if papel == "epigrafe" and texto:
                epigrafes.append(texto)
                ultimo_papel_corpo_visto = False
            elif papel == "ementa" and texto:
                ementas.append(texto)
                ultimo_papel_corpo_visto = False
            elif papel == "preambulo" and texto:
                preambulo_partes.append(texto)
                ultimo_papel_corpo_visto = False
            elif papel == "corpo":
                if texto:
                    corpo_linhas.append(texto)
                ultimo_papel_corpo_visto = True
            else:
                # parágrafo sem estilo reconhecido (ex.: linha em
                # branco, ou texto solto dentro do corpo, como o
                # "Tabela 1 -- ..." que antecede uma tabela): se
                # estivermos dentro do corpo, trata como continuação.
                if texto and ultimo_papel_corpo_visto:
                    corpo_linhas.append(texto)
        else:
            # Table -----------------------------------------------------
            linhas = [
                [cell.text.strip() for cell in row.cells]
                for row in bloco.rows
            ]

            legenda = None
            if ultima_legenda_candidata and looks_like_caption(ultima_legenda_candidata):
                legenda = ultima_legenda_candidata
            else:
                # tenta o próximo parágrafo não vazio como legenda
                # (convenção de legenda abaixo da tabela)
                for prox in blocos_ordenados[idx + 1:]:
                    if isinstance(prox, Paragraph):
                        texto_prox = prox.text.strip()
                        if texto_prox:
                            if looks_like_caption(texto_prox):
                                legenda = texto_prox
                            break
                    else:
                        break  # outra tabela em seguida: desiste

            tabelas.append({"legenda": legenda, "linhas": linhas})
            # reseta para não reaproveitar a mesma legenda em outra tabela
            ultima_legenda_candidata = None

            # Só tem sentido anexar ao corpo (para o parser_lei) se já
            # estamos dentro dele; tabelas fora do corpo (ex.: capa),
            # se existirem, são ignoradas para fins de "dispositivos".
            if ultimo_papel_corpo_visto:
                texto_tabela = tabela_para_texto(bloco)
                if texto_tabela:
                    corpo_linhas.append(texto_tabela)

    # A primeira epígrafe é o título do ato; epígrafes subsequentes
    # (se houver) tendem a ser bloco de assinatura -- não usadas como
    # título, mas devolvidas separadamente para quem quiser inspecionar.
    titulo = epigrafes[0] if epigrafes else None
    assinatura = epigrafes[1:] if len(epigrafes) > 1 else []

    return {
        "titulo_bruto": titulo,
        "assinatura": assinatura,
        "ementa_bruta": " ".join(ementas).strip(),
        "preambulo_bruto": " ".join(preambulo_partes).strip(),
        "corpo_texto": "\n".join(corpo_linhas),
        "texto_completo": "\n".join(texto_completo_partes),
        "tabelas": tabelas,
    }


# ---------------------------------------------------------------------------
# Campos derivados
# ---------------------------------------------------------------------------

def extrair_categoria_e_data(titulo_bruto: str):
    """A partir da epígrafe (ex.: 'Instrução Normativa iti n° 28, DE 26
    DE NOVEMBRO DE 2024'), extrai a categoria do ato e a data de
    publicação (ISO)."""
    if not titulo_bruto:
        return None, None

    categoria = None
    for tipo in TIPOS_ATO:
        # casa no início da epígrafe, ignorando maiúsc./minúsc.
        if re.match(re.escape(tipo).replace(r"\ ", r"\s+"), titulo_bruto, re.IGNORECASE):
            categoria = tipo
            break

    data_iso = None
    m_data = re.search(
        r"de\s+(\d{1,2})\s+de\s+([A-Za-zçãéíóúÇÃÉÍÓÚ]+)\s+de\s+(\d{4})",
        titulo_bruto,
        re.IGNORECASE,
    )
    if m_data:
        dia, mes_nome, ano = m_data.groups()
        data_iso = data_para_iso(dia, mes_nome, ano)

    return categoria, data_iso


def extrair_numero_ato(titulo_bruto: str, categoria: str):
    """Extrai o número do próprio ato (ex.: '28') a partir da epígrafe,
    removendo o nome da categoria do início."""
    if not titulo_bruto or not categoria:
        return None
    resto = re.sub(
        re.escape(categoria).replace(r"\ ", r"\s+"), "", titulo_bruto, count=1, flags=re.IGNORECASE
    ).strip()
    m = re.search(r"n?[ºo°]?\.?\s*([\d./-]+)", resto)
    return m.group(1) if m else None


def extrair_documentos_referenciados(texto_completo: str):
    """Varre o texto completo do ato (preâmbulo + corpo) em busca de
    citações a outros atos normativos, devolvendo uma lista de objetos
    estruturados e deduplicados (por texto integral da citação)."""
    encontrados = {}
    for m in CITACAO_RE.finditer(texto_completo):
        gd = m.groupdict()
        data_iso = data_para_iso(gd["dia"], gd["mes"], gd["ano"])
        orgao = gd.get("orgao_do") or gd.get("orgao_da")
        referencia_texto = m.group(0).strip().rstrip(",")

        chave = referencia_texto.lower()
        if chave in encontrados:
            continue

        encontrados[chave] = {
            "referencia": referencia_texto,
            "tipo": gd["tipo"].strip(),
            "numero": gd["numero"],
            "orgao": orgao.strip() if orgao else None,
            "documento_relacionado": gd.get("referencia_extra"),
            "data_publicacao": data_iso,
        }

    return list(encontrados.values())


def extrair_controle_alteracoes(texto_completo: str, documentos_referenciados: list):
    """
    Para cada palavra-chave de alteração encontrada no texto (altera,
    alterado por, redação dada por, revisa, consolidado por, passa a
    vigorar, revoga...), tenta associar a citação de documento mais
    próxima na mesma frase, produzindo uma lista de relações:

        {
          "tipo_alteracao": "altera",
          "documento_relacionado": "<referência completa>",
          "trecho": "<frase onde foi encontrado>"
        }
    """
    # separa o texto em frases de forma simples (ponto final, mantendo
    # o restante como está -- é suficiente para o caso de atos legais,
    # que tendem a ter uma alteração por frase/artigo)
    frases = re.split(r"(?<=[.;])\s+", texto_completo)

    relacoes = []
    vistos = set()

    for frase in frases:
        for padrao, tipo_normalizado in ALTERACAO_KEYWORDS:
            if re.search(padrao, frase, re.IGNORECASE):
                # acha a citação de documento mais relevante dentro da
                # própria frase
                doc_relacionado = None
                m_cit = CITACAO_RE.search(frase)
                if m_cit:
                    doc_relacionado = m_cit.group(0).strip().rstrip(",")

                chave = (tipo_normalizado, doc_relacionado, frase.strip())
                if chave in vistos:
                    continue
                vistos.add(chave)

                relacoes.append({
                    "tipo_alteracao": tipo_normalizado,
                    "documento_relacionado": doc_relacionado,
                    "trecho": frase.strip(),
                })

    return relacoes


def montar_urn(categoria: str, titulo_bruto: str, data_iso: str) -> str:
    """
    Monta a URN no formato:
        urn:icp.brasil.<tipo_documento>:<titulo_documento>:<data_documento>

    - tipo_documento  -> slug da categoria (ex.: 'instrucao-normativa')
    - titulo_documento -> slug da epígrafe SEM a categoria e SEM a data
                          (evita repetir a data duas vezes na URN),
                          ex.: 'iti-n-28'
    - data_documento   -> data ISO (AAAA-MM-DD)
    """
    tipo_slug = slugify(categoria) if categoria else "documento"

    titulo_sem_categoria = titulo_bruto or ""
    if categoria:
        titulo_sem_categoria = re.sub(
            re.escape(categoria).replace(r"\ ", r"\s+"), "", titulo_sem_categoria,
            count=1, flags=re.IGNORECASE,
        )
    # remove a parte de data ("de 26 de novembro de 2024" / ", DE 26 DE...")
    titulo_sem_categoria = re.sub(
        r",?\s*de\s+\d{1,2}\s+de\s+[A-Za-zçãéíóúÇÃÉÍÓÚ]+\s+de\s+\d{4}\.?$",
        "",
        titulo_sem_categoria.strip(),
        flags=re.IGNORECASE,
    )
    titulo_slug = slugify(titulo_sem_categoria)

    data_documento = data_iso or "sem-data"

    return f"urn:icp.brasil.{tipo_slug}:{titulo_slug}:{data_documento}"


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_json(caminho_docx: str) -> dict:
    blocos = extrair_blocos(caminho_docx)

    titulo_bruto = blocos["titulo_bruto"]
    categoria, data_publicacao = extrair_categoria_e_data(titulo_bruto)
    numero_ato = extrair_numero_ato(titulo_bruto, categoria)

    texto_completo = "\n".join([
        blocos["preambulo_bruto"],
        blocos["corpo_texto"],
    ])

    documentos_referenciados = extrair_documentos_referenciados(texto_completo)
    controle_alteracoes = extrair_controle_alteracoes(texto_completo, documentos_referenciados)

    dispositivos = parse_lei(blocos["corpo_texto"])

    urn = montar_urn(categoria, titulo_bruto, data_publicacao)

    return {
        "titulo": titulo_bruto,
        "numero": numero_ato,
        "categoria": categoria,
        "data_publicacao": data_publicacao,
        "ementa": blocos["ementa_bruta"],
        "preambulo": blocos["preambulo_bruto"],
        "documentos_referenciados": documentos_referenciados,
        "dispositivos": dispositivos,
        "controle_alteracoes": controle_alteracoes,
        "tabelas": blocos["tabelas"],
        "texto_completo": blocos["texto_completo"],
        "urn": urn,
    }


def main():
    if len(sys.argv) < 2:
        print("Uso: python gerar_json_norma.py <arquivo.docx> [saida.json]")
        sys.exit(1)

    caminho_docx = sys.argv[1]
    caminho_saida = sys.argv[2] if len(sys.argv) > 2 else "resultado.json"

    resultado = gerar_json(caminho_docx)

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"JSON gerado em '{caminho_saida}'.")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()