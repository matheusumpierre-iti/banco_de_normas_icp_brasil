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

Por isso a extração tenta PRIMEIRO por nome de estilo do parágrafo
(mais robusto). Quando o documento não usa esses estilos oficiais
(ex.: tudo em "Normal"), o script cai automaticamente para um
FALLBACK por regex sobre o texto puro: título = primeiro parágrafo
que bate com "<Categoria> nº <número>, de <data>"; ementa = parágrafo
seguinte; preâmbulo = parágrafos até a autoridade que assina
("O DIRETOR-PRESIDENTE...", "CONSIDERANDO...") até o "Art. 1º"; corpo
= tudo a partir do primeiro "Art.".

Outro problema comum: incisos/alíneas nem sempre têm o marcador
("I -", "a)") como TEXTO -- muitas vezes são listas numeradas
automáticas do Word, cujo número só existe no XML de numeração
(numbering.xml), não no texto extraído. Por isso, antes de mandar o
texto do corpo para o parser_lei.py, cada parágrafo que for item de
lista automática tem seu formato de numeração (upperRoman/lowerLetter)
resolvido via numbering.xml, e um marcador equivalente ("I - ", "a) ")
é sintetizado na frente do texto -- assim o parser_lei.py (que só
entende marcadores literais) reconhece a estrutura normalmente.

O parsing de "Dispositivos" (Art./§/inciso/alínea) em si REAPROVEITA
integralmente o `parser_lei.py` já existente — nenhuma lógica de
sequência foi duplicada aqui.

Uso:
    python gerar_json_norma.py caminho/para/ato.docx [saida.json]
"""

import os
import mammoth
import re
import sys
import json
import unicodedata

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

# reaproveita o parser de Art./§/inciso/alínea já existente -- inclusive
# os próprios regexes de cada tipo de dispositivo, para a etapa de
# síntese de marcadores (ver _sintetizar_marcador_corpo) usar
# EXATAMENTE os mesmos padrões que o parser vai validar depois.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser_lei import parse_lei, ART_RE, PARAGRAFO_RE, INCISO_RE, ALINEA_RE


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


# Cabeçalhos estruturais (Capítulo/Título/Seção) e o título em caixa
# alta que costuma vir logo abaixo (ex.: "CAPÍTULO I" / "DAS
# DISPOSIÇÕES GERAIS"): não fazem parte do texto de nenhum dispositivo
# e por isso são DESCARTADOS (não viram "continuação" grudada no
# artigo anterior nem no preâmbulo).
CABECALHO_ESTRUTURAL_RE = re.compile(
    r"^\s*(LIVRO|T[IÍ]TULO|CAP[IÍ]TULO|SE[CÇ][AÃ]O|SUBSE[CÇ][AÃ]O)\b",
    re.IGNORECASE,
)


def parece_cabecalho_estrutural(texto: str) -> bool:
    """True para 'CAPÍTULO I', 'SEÇÃO II' etc., e para a linha de
    título em caixa alta que normalmente vem logo em seguida (ex.:
    'DAS DISPOSIÇÕES GERAIS'). Também casa com o bloco de assinatura
    final (nome da autoridade em caixa alta), o que é o comportamento
    desejado: assinatura não deve virar texto de dispositivo."""
    t = texto.strip()
    if not t:
        return False
    if CABECALHO_ESTRUTURAL_RE.match(t):
        return True
    # linha inteira em maiúsculas, curta, sem pontuação de fim de frase
    if (
        t == t.upper()
        and any(c.isalpha() for c in t)
        and len(t) <= 100
        and not t.rstrip().endswith((".", ";", ":"))
    ):
        return True
    return False


# Sinaliza o início do preâmbulo (fundamentação legal / autoridade que
# assina o ato), usado apenas no MODO FALLBACK (quando não há estilos
# oficiais para identificar isso diretamente).
PREAMBULO_INICIO_RE = re.compile(
    r"^CONSIDERANDO\b"
    r"|^(O|A)\s+[A-ZÀ-Ú]{2,}(?:[\s\-][A-ZÀ-Ú]{2,}){1,}"
    r"|no\s+uso\s+(?:de\s+suas|das)\s+atribui[cç][oõ]es",
    re.IGNORECASE,
)

# Detecta a epígrafe (título do ato) só pelo TEXTO, para o modo
# fallback: "<Categoria> [sigla] nº <número>, de <data por extenso>".
TITULO_FALLBACK_RE = re.compile(
    r"^\s*(?:" + TIPOS_ATO_RE + r")\b.*n[ºo°]?\.?\s*[\d./-]+.*"
    r"\bde\s+\d{1,2}\s+de\s+[A-Za-zçãéíóúÇÃÉÍÓÚ]+\s+de\s+\d{4}",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Resolução de numeração automática do Word (listas sem marcador
# literal no texto -- o número/letra só existe no numbering.xml)
# ---------------------------------------------------------------------------

def _carregar_mapa_estilo_numpr(documento):
    """Mapeia nome_do_estilo -> (numId, ilvl) para estilos de parágrafo
    que têm numeração embutida no próprio estilo (ex.: um estilo
    'Inciso' cujo <w:style> já define <w:numPr>), caso em que o
    parágrafo em si não carrega w:numPr diretamente."""
    mapa = {}
    for style_el in documento.styles.element.findall(qn("w:style")):
        name_el = style_el.find(qn("w:name"))
        if name_el is None:
            continue
        nome = name_el.get(qn("w:val"))
        pPr = style_el.find(qn("w:pPr"))
        numPr = pPr.find(qn("w:numPr")) if pPr is not None else None
        if numPr is None:
            continue
        numId_el = numPr.find(qn("w:numId"))
        ilvl_el = numPr.find(qn("w:ilvl"))
        numId = numId_el.get(qn("w:val")) if numId_el is not None else None
        ilvl = ilvl_el.get(qn("w:val")) if ilvl_el is not None else "0"
        if numId is not None:
            mapa[nome] = (numId, ilvl)
    return mapa


def _carregar_mapa_numfmt_por_num(documento):
    """Devolve {(numId, ilvl): numFmt} lendo numbering.xml (resolve
    numId -> abstractNumId -> formato do nível). numFmt é o valor bruto
    do Word: 'upperRoman' (I, II, III...), 'lowerLetter' (a, b, c...),
    'decimal' (1, 2, 3...) etc."""
    mapa = {}
    numbering_part = getattr(documento.part, "numbering_part", None)
    if numbering_part is None:
        return mapa
    numbering_el = numbering_part.element

    niveis_por_abstract = {}
    for absnum in numbering_el.findall(qn("w:abstractNum")):
        abs_id = absnum.get(qn("w:abstractNumId"))
        niveis = {}
        for lvl in absnum.findall(qn("w:lvl")):
            ilvl = lvl.get(qn("w:ilvl"))
            numFmt_el = lvl.find(qn("w:numFmt"))
            niveis[ilvl] = numFmt_el.get(qn("w:val")) if numFmt_el is not None else None
        niveis_por_abstract[abs_id] = niveis

    for num in numbering_el.findall(qn("w:num")):
        numId = num.get(qn("w:numId"))
        absid_el = num.find(qn("w:abstractNumId"))
        abs_id = absid_el.get(qn("w:val")) if absid_el is not None else None
        for ilvl, numFmt in niveis_por_abstract.get(abs_id, {}).items():
            mapa[(numId, ilvl)] = numFmt

    return mapa


def _resolver_numfmt(paragrafo, mapa_estilo_numpr, mapa_numfmt_por_num):
    """Para um parágrafo, descobre se ele é item de uma lista numerada
    automática do Word e devolve o numFmt correspondente ('upperRoman',
    'lowerLetter', 'decimal', ...), ou None se não for item de lista."""
    pPr = paragrafo._p.pPr
    numId = ilvl = None

    if pPr is not None:
        numPr = pPr.find(qn("w:numPr"))
        if numPr is not None:
            numId_el = numPr.find(qn("w:numId"))
            ilvl_el = numPr.find(qn("w:ilvl"))
            numId = numId_el.get(qn("w:val")) if numId_el is not None else None
            ilvl = ilvl_el.get(qn("w:val")) if ilvl_el is not None else "0"

    if numId is None:
        nome_estilo = paragrafo.style.name if paragrafo.style else None
        par = mapa_estilo_numpr.get(nome_estilo)
        if par:
            numId, ilvl = par

    if numId is None:
        return None

    return mapa_numfmt_por_num.get((numId, ilvl))


def _int_to_roman(n: int) -> str:
    valores = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    partes = []
    for valor, simbolo in valores:
        while n >= valor:
            partes.append(simbolo)
            n -= valor
    return "".join(partes)


def _int_to_letras(n: int) -> str:
    """1 -> 'a', 2 -> 'b', ..., 26 -> 'z', 27 -> 'aa', ... (mesma lógica
    de nomeação de colunas de planilha, para não travar se um artigo
    tiver mais de 26 alíneas)."""
    letras = ""
    while n > 0:
        n, resto = divmod(n - 1, 26)
        letras = chr(ord("a") + resto) + letras
    return letras


def _sintetizar_marcador_corpo(paragrafo, texto, estado, mapa_estilo_numpr, mapa_numfmt_por_num):
    """
    Recebe uma linha de texto do corpo e devolve o texto pronto para o
    parser_lei.py -- com um marcador ('I - ', 'a) ') sintetizado na
    frente SE (e somente se) o parágrafo for item de uma lista
    numerada automática do Word sem marcador literal já escrito.

    'estado' é um dict mutável {'inciso': int, 'alinea': int} com os
    contadores correntes, reiniciados pelo PRÓPRIO chamador (via
    ART_RE/PARAGRAFO_RE) nos mesmos pontos em que o parser_lei.py
    reinicia sua validação de sequência -- garantindo que os números
    sintéticos sempre batam com o que o parser_lei.py espera.

    upperRoman -> vira inciso ('I - ', 'II - ', ...)
    lowerLetter -> vira alínea ('a) ', 'b) ', ...)
    outros formatos (decimal, lowerRoman...) -> sem equivalente na
    estrutura Art./§/inciso/alínea; a linha é devolvida sem marcador e
    entra como continuação do dispositivo mais específico aberto.
    """
    if ART_RE.match(texto) or PARAGRAFO_RE.match(texto):
        estado["inciso"] = 0
        estado["alinea"] = 0
        return texto

    if INCISO_RE.match(texto):
        estado["alinea"] = 0
        return texto

    if ALINEA_RE.match(texto):
        return texto

    numfmt = _resolver_numfmt(paragrafo, mapa_estilo_numpr, mapa_numfmt_por_num)
    if numfmt == "upperRoman":
        estado["inciso"] += 1
        estado["alinea"] = 0
        return f"{_int_to_roman(estado['inciso'])} - {texto}"
    if numfmt == "lowerLetter":
        estado["alinea"] += 1
        return f"{_int_to_letras(estado['alinea'])}) {texto}"

    return texto


# Pontuação que indica "isto é uma frase normal do corpo do ato" (não
# um título de subseção solto). Usada em _deve_pular_linha_corpo.
_PONTUACAO_FIM_FRASE = (".", ";", ":", "!", "?")


def _deve_pular_linha_corpo(paragrafo, texto, mapa_estilo_numpr, mapa_numfmt_por_num):
    """
    Decide se uma linha do corpo deve ser DESCARTADA por inteiro (não
    vira nem dispositivo novo, nem continuação de texto): cobre tanto
    'CAPÍTULO I' / 'DAS DISPOSIÇÕES GERAIS' (parece_cabecalho_estrutural)
    quanto títulos de subseção soltos em title-case sem numeração
    própria, do tipo 'Confirmação inicial da identidade' -- comuns
    entre um Art. e outro, sem estarem em caixa alta nem terem prefixo
    'CAPÍTULO'/'SEÇÃO'.

    Um parágrafo só entra nessa segunda regra se, ALÉM de curto e sem
    pontuação de fim de frase, ele NÃO for nenhum dispositivo
    reconhecido (Art./§/inciso/alínea) nem item de lista numerada
    automática -- para não descartar por engano um item de lista
    legítimo que termine sem ponto final (ex.: '...Titularidade; e').
    """
    if parece_cabecalho_estrutural(texto):
        return True

    if (
        len(texto) <= 100
        and texto[:1].isalpha()
        and texto[:1] == texto[:1].upper()
        and not texto.rstrip().endswith(_PONTUACAO_FIM_FRASE)
        and not ART_RE.match(texto)
        and not PARAGRAFO_RE.match(texto)
        and not INCISO_RE.match(texto)
        and not ALINEA_RE.match(texto)
        and _resolver_numfmt(paragrafo, mapa_estilo_numpr, mapa_numfmt_por_num) is None
    ):
        return True

    return False


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


def _coletar_texto_completo_e_tabelas(blocos_ordenados):
    """Passagem independente do papel estrutural: monta o texto linear
    completo do documento e a lista de tabelas com legenda -- igual
    nos dois modos de extração, por isso fica fora deles."""
    texto_completo_partes = []
    tabelas = []
    ultima_legenda_candidata = None

    for idx, bloco in enumerate(blocos_ordenados):
        if isinstance(bloco, Paragraph):
            texto = bloco.text.strip()
            if texto:
                texto_completo_partes.append(texto)
                ultima_legenda_candidata = texto
        else:
            linhas = [[cell.text.strip() for cell in row.cells] for row in bloco.rows]

            legenda = None
            if ultima_legenda_candidata and looks_like_caption(ultima_legenda_candidata):
                legenda = ultima_legenda_candidata
            else:
                for prox in blocos_ordenados[idx + 1:]:
                    if isinstance(prox, Paragraph):
                        texto_prox = prox.text.strip()
                        if texto_prox:
                            if looks_like_caption(texto_prox):
                                legenda = texto_prox
                            break
                    else:
                        break

            tabelas.append({"legenda": legenda, "linhas": linhas})
            ultima_legenda_candidata = None

    return "\n".join(texto_completo_partes), tabelas


def _extrair_blocos_por_estilo(blocos_ordenados, mapa_estilo_numpr, mapa_numfmt_por_num):
    """MODO PRINCIPAL: classifica cada parágrafo pelo nome do estilo do
    Word (CGNPE ATO EPÍGRAFE/Ementa/Preâmbulo/ATO). Funciona bem em
    documentos publicados com o template oficial; em documentos sem
    esses estilos, todo parágrafo cai em 'outro' e o resultado sai
    vazio -- sinal para o chamador tentar o modo fallback."""
    epigrafes = []
    ementas = []
    preambulo_partes = []
    corpo_linhas = []
    estado_numeracao = {"inciso": 0, "alinea": 0}

    ultimo_papel_corpo_visto = False

    for bloco in blocos_ordenados:
        if not isinstance(bloco, Paragraph):
            if ultimo_papel_corpo_visto:
                texto_tabela = tabela_para_texto(bloco)
                if texto_tabela:
                    corpo_linhas.append(texto_tabela)
            continue

        texto = bloco.text.strip()
        estilo = bloco.style.name if bloco.style else ""
        papel = classificar_estilo(estilo)

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
            if texto and not _deve_pular_linha_corpo(bloco, texto, mapa_estilo_numpr, mapa_numfmt_por_num):
                texto_processado = _sintetizar_marcador_corpo(
                    bloco, texto, estado_numeracao, mapa_estilo_numpr, mapa_numfmt_por_num
                )
                corpo_linhas.append(texto_processado)
            ultimo_papel_corpo_visto = True
        else:
            if texto and ultimo_papel_corpo_visto and not _deve_pular_linha_corpo(bloco, texto, mapa_estilo_numpr, mapa_numfmt_por_num):
                texto_processado = _sintetizar_marcador_corpo(
                    bloco, texto, estado_numeracao, mapa_estilo_numpr, mapa_numfmt_por_num
                )
                corpo_linhas.append(texto_processado)

    titulo = epigrafes[0] if epigrafes else None
    assinatura = epigrafes[1:] if len(epigrafes) > 1 else []

    return {
        "titulo_bruto": titulo,
        "assinatura": assinatura,
        "ementa_bruta": " ".join(ementas).strip(),
        "preambulo_bruto": " ".join(preambulo_partes).strip(),
        "corpo_texto": "\n".join(corpo_linhas),
    }


def _extrair_blocos_fallback_regex(blocos_ordenados, mapa_estilo_numpr, mapa_numfmt_por_num):
    """MODO FALLBACK: usado quando o documento não tem os estilos
    oficiais (ex.: tudo em 'Normal'). Identifica os papéis estruturais
    só pelo TEXTO:

        título     -> primeiro parágrafo batendo com TITULO_FALLBACK_RE
        ementa     -> parágrafo(s) logo depois do título, até aparecer
                      o preâmbulo ou o primeiro "Art."
        preâmbulo  -> parágrafos entre a ementa e o primeiro "Art."
                      (pulando cabeçalhos estruturais tipo "CAPÍTULO I")
        corpo      -> tudo a partir do primeiro "Art." (pulando
                      cabeçalhos estruturais e a assinatura final)
    """
    epigrafes = []
    ementas = []
    preambulo_partes = []
    corpo_linhas = []
    estado_numeracao = {"inciso": 0, "alinea": 0}

    FASE_ANTES_TITULO, FASE_EMENTA, FASE_PREAMBULO, FASE_CORPO = range(4)
    fase = FASE_ANTES_TITULO

    for bloco in blocos_ordenados:
        if not isinstance(bloco, Paragraph):
            if fase == FASE_CORPO:
                texto_tabela = tabela_para_texto(bloco)
                if texto_tabela:
                    corpo_linhas.append(texto_tabela)
            continue

        texto = bloco.text.strip()
        if not texto:
            continue

        if fase == FASE_CORPO:
            if _deve_pular_linha_corpo(bloco, texto, mapa_estilo_numpr, mapa_numfmt_por_num):
                continue
            texto_processado = _sintetizar_marcador_corpo(
                bloco, texto, estado_numeracao, mapa_estilo_numpr, mapa_numfmt_por_num
            )
            corpo_linhas.append(texto_processado)
            continue

        if ART_RE.match(texto):
            fase = FASE_CORPO
            texto_processado = _sintetizar_marcador_corpo(
                bloco, texto, estado_numeracao, mapa_estilo_numpr, mapa_numfmt_por_num
            )
            corpo_linhas.append(texto_processado)
            continue

        if fase == FASE_ANTES_TITULO:
            if TITULO_FALLBACK_RE.match(texto):
                epigrafes.append(texto)
                fase = FASE_EMENTA
            # texto antes do título (ex.: cabeçalho de página) é ignorado
            continue

        if fase == FASE_EMENTA:
            if PREAMBULO_INICIO_RE.match(texto):
                fase = FASE_PREAMBULO
                if not parece_cabecalho_estrutural(texto):
                    preambulo_partes.append(texto)
            elif parece_cabecalho_estrutural(texto):
                pass  # ex.: "CAPÍTULO I" logo após o título, sem ementa
            else:
                ementas.append(texto)
            continue

        if fase == FASE_PREAMBULO:
            if parece_cabecalho_estrutural(texto):
                continue
            preambulo_partes.append(texto)
            continue

    titulo = epigrafes[0] if epigrafes else None

    return {
        "titulo_bruto": titulo,
        "assinatura": [],
        "ementa_bruta": " ".join(ementas).strip(),
        "preambulo_bruto": " ".join(preambulo_partes).strip(),
        "corpo_texto": "\n".join(corpo_linhas),
    }


def extrair_blocos(caminho_docx: str):
    """
    Percorre o .docx UMA ÚNICA VEZ para montar o texto completo/tabelas
    (independente do papel estrutural) e tenta extrair título/ementa/
    preâmbulo/corpo primeiro pelo MODO ESTILO (mais confiável, usa os
    estilos oficiais CGNPE); se isso não encontrar título nem corpo
    (documento sem esses estilos), cai automaticamente para o MODO
    FALLBACK, que identifica tudo por regex sobre o texto puro.

    Em qualquer um dos dois modos, o texto do corpo já sai com
    marcadores sintéticos ('I - ', 'a) ') para itens de lista numerada
    automática do Word sem marcador literal, e com as tabelas
    intercaladas como continuação do dispositivo aberto no momento --
    tudo isso para o parser_lei.py conseguir estruturar Art./§/
    inciso/alínea normalmente.
    """
    documento = docx.Document(caminho_docx)
    blocos_ordenados = list(iter_block_items(documento))

    mapa_estilo_numpr = _carregar_mapa_estilo_numpr(documento)
    mapa_numfmt_por_num = _carregar_mapa_numfmt_por_num(documento)

    texto_completo, tabelas = _coletar_texto_completo_e_tabelas(blocos_ordenados)

    resultado = _extrair_blocos_por_estilo(blocos_ordenados, mapa_estilo_numpr, mapa_numfmt_por_num)

    if not resultado["titulo_bruto"] or not resultado["corpo_texto"].strip():
        resultado = _extrair_blocos_fallback_regex(blocos_ordenados, mapa_estilo_numpr, mapa_numfmt_por_num)

    resultado["texto_completo"] = texto_completo
    resultado["tabelas"] = tabelas
    return resultado


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

def converter_html(arquivo_docx):
    convertido = mammoth.convert_to_html(arquivo_docx)
    html = convertido.value
    return html



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

    html = converter_html(caminho_docx)

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
        "html": html,
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