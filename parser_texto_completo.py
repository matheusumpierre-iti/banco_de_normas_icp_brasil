#!/usr/bin/env python3
"""
parse_documento.py

Faz o parsing de um documento .docx ou .odt e gera um JSON com:
  - titulo
  - data_primeira_pagina
  - texto_completo
  - tabelas (lista, em ordem, cada uma com "legenda" e "linhas")

Uso:
    python parse_documento.py caminho/do/arquivo.docx [-o saida.json]
    python parse_documento.py caminho/do/arquivo.odt  [-o saida.json]

Dependências:
    pip install python-docx odfpy
"""

import argparse
import json
from bson import BSON
import pandas as pd
import re
import sys
import io
from pathlib import Path


# --------------------------------------------------------------------------
# Utilitários gerais
# --------------------------------------------------------------------------

# Padrões de data comumente usados em documentos em português
DATE_PATTERNS = [
    # 12/05/2024, 12-05-2024, 12.05.2024
    r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b",
    # 12 de maio de 2024
    r"\b\d{1,2}\s+de\s+(?:janeiro|fevereiro|março|marco|abril|maio|junho|"
    r"julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+\d{4}\b",
    # Brasília, 12 de maio de 2024
    r"\b\d{1,2}\s+de\s+(?:janeiro|fevereiro|março|marco|abril|maio|junho|"
    r"julho|agosto|setembro|outubro|novembro|dezembro)\s*(?:,)?\s*\d{4}\b",
]

DATE_REGEX = re.compile("|".join(DATE_PATTERNS), re.IGNORECASE)

# Palavras que costumam iniciar uma legenda de tabela
CAPTION_KEYWORDS = re.compile(
    r"^\s*(tabela|quadro|table|anexo|figura)\s*\d*[\-:.)]?\s*",
    re.IGNORECASE,
)


def find_date_in_text(text: str) -> str | None:
    """Procura a primeira data reconhecível dentro de um texto."""
    if not text:
        return None
    match = DATE_REGEX.search(text)
    return match.group(0).strip() if match else None


def looks_like_caption(text: str) -> bool:
    """Heurística simples para saber se um parágrafo é legenda de tabela."""
    return bool(text) and bool(CAPTION_KEYWORDS.match(text.strip()))


# --------------------------------------------------------------------------
# Parsing de .docx
# --------------------------------------------------------------------------

def extract_docx(path: Path) -> dict:
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(str(path))

    # --- Título -----------------------------------------------------------
    titulo = None
    core_title = (doc.core_properties.title or "").strip()
    if core_title:
        titulo = core_title
    else:
        # fallback: primeiro parágrafo não vazio, ou primeiro estilo "Title"/"Heading"
        for p in doc.paragraphs:
            texto_p = p.text.strip()
            if not texto_p:
                continue
            if p.style and p.style.name and (
                "title" in p.style.name.lower() or "heading" in p.style.name.lower()
            ):
                titulo = texto_p
                break
            if titulo is None:
                titulo = texto_p  # guarda o primeiro parágrafo como fallback
        # se não achou nenhum heading, usa o primeiro parágrafo não vazio já guardado

    # --- Corpo do documento em ordem (parágrafos + tabelas) --------------
    # python-docx não expõe nativamente a ordem intercalada de parágrafos e
    # tabelas, então percorremos o XML do corpo diretamente.
    body = doc.element.body
    paragraphs_by_elem = {p._p: p for p in doc.paragraphs}
    tables_by_elem = {t._tbl: t for t in doc.tables}

    texto_completo_partes = []
    tabelas = []

    # Para detectar "primeira página": acumulamos texto até encontrar
    # uma quebra de página explícita (<w:br w:type="page"/> ou <w:lastRenderedPageBreak/>)
    primeira_pagina_partes = []
    quebrou_pagina = False

    ultima_legenda_candidata = None  # último parágrafo de texto visto (para legenda ANTES da tabela)
    pendente_apos_tabela = []  # tabelas que ainda não acharam legenda antes, tentaremos depois

    def paragrafo_tem_quebra_pagina(p_elem) -> bool:
        for br in p_elem.iter(qn("w:br")):
            if br.get(qn("w:type")) == "page":
                return True
        if p_elem.iter(qn("w:lastRenderedPageBreak")):
            for _ in p_elem.iter(qn("w:lastRenderedPageBreak")):
                return True
        return False

    for child in body.iterchildren():
        tag = child.tag
        if tag == qn("w:p") and child in paragraphs_by_elem:
            p = paragraphs_by_elem[child]
            texto_p = p.text.strip()

            if texto_p:
                texto_completo_partes.append(texto_p)
                if not quebrou_pagina:
                    primeira_pagina_partes.append(texto_p)
                ultima_legenda_candidata = texto_p

            if not quebrou_pagina and paragrafo_tem_quebra_pagina(child):
                quebrou_pagina = True

        elif tag == qn("w:tbl") and child in tables_by_elem:
            t = tables_by_elem[child]
            linhas = [
                [cell.text.strip() for cell in row.cells]
                for row in t.rows
            ]

            legenda = None
            if ultima_legenda_candidata and looks_like_caption(ultima_legenda_candidata):
                legenda = ultima_legenda_candidata

            tabelas.append({
                "legenda": legenda,
                "linhas": linhas,
            })
            # reseta para não reaproveitar a mesma legenda em outra tabela
            ultima_legenda_candidata = None

    # Se alguma tabela ficou sem legenda, tenta usar o parágrafo seguinte
    # (algumas convenções colocam a legenda abaixo da tabela)
    if any(t["legenda"] is None for t in tabelas):
        _preencher_legenda_apos(body, paragraphs_by_elem, tables_by_elem, tabelas, qn)

    texto_completo = "\n".join(texto_completo_partes)

    # --- Data na primeira página ------------------------------------------
    texto_primeira_pagina = "\n".join(primeira_pagina_partes)
    data_primeira_pagina = find_date_in_text(texto_primeira_pagina)
    if not data_primeira_pagina:
        # fallback: procura em todo o texto
        data_primeira_pagina = find_date_in_text(texto_completo)
    if not data_primeira_pagina:
        # fallback final: data de criação do arquivo (metadados)
        created = doc.core_properties.created
        if created:
            data_primeira_pagina = created.strftime("%d/%m/%Y")

    if titulo is None:
        titulo = path.stem

    return {
        "titulo": titulo,
        "data_primeira_pagina": data_primeira_pagina,
        "texto_completo": texto_completo,
        "tabelas": tabelas,
    }


def _preencher_legenda_apos(body, paragraphs_by_elem, tables_by_elem, tabelas, qn):
    """Para tabelas sem legenda encontrada antes, tenta olhar o parágrafo
    imediatamente seguinte no XML."""
    children = list(body.iterchildren())
    idx_tabela = 0
    for i, child in enumerate(children):
        if child.tag == qn("w:tbl") and child in tables_by_elem:
            if tabelas[idx_tabela]["legenda"] is None:
                # procura o próximo parágrafo não vazio
                for nxt in children[i + 1:]:
                    if nxt.tag == qn("w:p") and nxt in paragraphs_by_elem:
                        texto_nxt = paragraphs_by_elem[nxt].text.strip()
                        if texto_nxt:
                            if looks_like_caption(texto_nxt):
                                tabelas[idx_tabela]["legenda"] = texto_nxt
                            break
                    elif nxt.tag == qn("w:tbl"):
                        break
            idx_tabela += 1


# --------------------------------------------------------------------------
# Parsing de .odt
# --------------------------------------------------------------------------

def extract_odt(path: Path) -> dict:
    from odf.opendocument import load
    from odf.text import P, H
    from odf.table import Table, TableRow, TableCell
    from odf import teletype

    doc = load(str(path))

    # --- Título -------------------------------------------------------
    titulo = None
    try:
        meta_el = doc.meta
        for e in meta_el.childNodes:
            if getattr(e, "qname", None) and e.qname[1] == "title":
                texto_meta = teletype.extractText(e).strip()
                if texto_meta:
                    titulo = texto_meta
    except Exception:
        pass

    body = doc.text

    # Percorre o corpo em ordem, distinguindo parágrafos/headings de tabelas
    texto_completo_partes = []
    tabelas = []
    ultima_legenda_candidata = None

    def eh_paragrafo_ou_heading(el):
        return el.qname[1] in ("p", "h")

    def eh_tabela(el):
        return el.qname[1] == "table"

    elementos = [el for el in body.childNodes if hasattr(el, "qname")]

    for i, el in enumerate(elementos):
        if eh_paragrafo_ou_heading(el):
            texto_el = teletype.extractText(el).strip()
            if texto_el:
                texto_completo_partes.append(texto_el)
                ultima_legenda_candidata = texto_el
                if titulo is None and el.qname[1] == "h":
                    titulo = texto_el

        elif eh_tabela(el):
            linhas = []
            for row in el.getElementsByType(TableRow):
                linha = []
                for cell in row.getElementsByType(TableCell):
                    linha.append(teletype.extractText(cell).strip())
                linhas.append(linha)

            legenda = None
            if ultima_legenda_candidata and looks_like_caption(ultima_legenda_candidata):
                legenda = ultima_legenda_candidata
            else:
                # tenta o próximo parágrafo como legenda
                for nxt in elementos[i + 1:]:
                    if eh_paragrafo_ou_heading(nxt):
                        texto_nxt = teletype.extractText(nxt).strip()
                        if texto_nxt:
                            if looks_like_caption(texto_nxt):
                                legenda = texto_nxt
                            break
                    elif eh_tabela(nxt):
                        break

            tabelas.append({
                "legenda": legenda,
                "linhas": linhas,
            })
            ultima_legenda_candidata = None

    texto_completo = "\n".join(texto_completo_partes)

    # ODT não guarda quebras de página como marcador simples de forma
    # confiável via odfpy; usamos os primeiros parágrafos (até uns 2000
    # caracteres, aproximando "primeira página") para buscar a data.
    aproximacao_primeira_pagina = ""
    acumulado = 0
    for parte in texto_completo_partes:
        aproximacao_primeira_pagina += parte + "\n"
        acumulado += len(parte)
        if acumulado > 2000:
            break

    data_primeira_pagina = find_date_in_text(aproximacao_primeira_pagina)
    if not data_primeira_pagina:
        data_primeira_pagina = find_date_in_text(texto_completo)

    if titulo is None:
        titulo = path.stem

    return {
        "titulo": titulo,
        "data_primeira_pagina": data_primeira_pagina,
        "texto_completo": texto_completo,
        "tabelas": tabelas,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extrai título, data, texto completo e tabelas de um .docx/.odt para JSON."
    )
    parser.add_argument("arquivo", help="Caminho do arquivo .docx ou .odt de entrada")
    parser.add_argument(
        "-o", "--output",
        help="Caminho do JSON de saída (padrão: mesmo nome do arquivo de entrada, com .json)",
        default=None,
    )
    args = parser.parse_args()

    caminho = Path(args.arquivo)
    if not caminho.exists():
        print(f"Erro: arquivo não encontrado: {caminho}", file=sys.stderr)
        sys.exit(1)

    ext = caminho.suffix.lower()
    if ext == ".docx":
        resultado = extract_docx(caminho)
    elif ext == ".odt":
        resultado = extract_odt(caminho)
    else:
        print(f"Erro: extensão não suportada '{ext}'. Use .docx ou .odt.", file=sys.stderr)
        sys.exit(1)

    saida = Path(args.output) if args.output else caminho.with_suffix(".json")
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"JSON gerado em: {saida}")

#--------------------------
# Módulo
#--------------------------

def parser_texto_bruto(doc: Path) -> dict:
    ext = doc.suffix.lower()
    if ext == '.docx':
        parse = extract_docx(doc)
    elif ext == '.odt':
        parse = extract_odt(doc)
    else:
        print(f"Erro: extensão não suportada '{ext}'. Use .docx ou .odt.")
        sys.exit()
    return parse
    

#--------------------------
# Execução
#--------------------------

if __name__ == "__main__":
  main()