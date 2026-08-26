"""
parser_lei.py

Script para extrair a estrutura de um texto legal (lei, decreto, etc.),
agrupando cada "Art." com seus respectivos parágrafos (§) e incisos
(I, II, III...), incluindo alíneas (a, b, c...) quando existirem.

Uso básico:
    from parser_lei import parse_lei
    artigos = parse_lei(texto)

Ou via linha de comando:
    python parser_lei.py caminho/para/lei.txt
"""

import re
import pandas as pd
import json
import os
import sys

# ---------------------------------------------------------------------------
# Estrutura de suporte para validar ordem de dispositivos
# ---------------------------------------------------------------------------

log_sequencial =  {'artigo':1,'paragrafo':1,'inciso':1,'tópico':1,'ntópico':1}

# ---------------------------------------------------------------------------
# Padrões (regex) para reconhecer cada tipo de dispositivo legal
# ---------------------------------------------------------------------------

# Ex.: "Art. 5º", "Art. 12", "Art. 6º-A"
ART_RE = re.compile(
    r'^\s*Art\.?\s*(\d+[ºo°]?(?:-[A-Za-z])?)\.?\s*(.*)$',
    re.IGNORECASE
)

# Ex.: "§ 1º", "§1º", "Parágrafo único"
PARAGRAFO_RE = re.compile(
    r'^\s*(?:§\s*(\d+[ºo°]?)|(Par[aá]grafo\s+[uú]nico))\.?\s*(.*)$',
    re.IGNORECASE
)

# Ex.: "I -", "II –", "III."  (numeral romano no início da linha)
INCISO_RE = re.compile(
    r'^\s*([IVXLCDM]+)\s*[-–—.]\s*(.*)$'
)

# Ex.: "a)", "b)"
ALINEA_RE = re.compile(
    r'^\s*([a-z])\)\s*(.*)$'
)

def _novo_artigo(numero, texto_inicial):
    return {
        "artigo": numero,
        "caput": texto_inicial.strip(),
        "incisos": [],      # incisos que pertencem diretamente ao caput
        "paragrafos": []    # cada parágrafo tem sua própria lista de incisos
    }


def _novo_paragrafo(numero, texto_inicial):
    return {
        "paragrafo": numero,
        "texto": texto_inicial.strip(),
        "incisos": []
    }


def _novo_inciso(numero, texto_inicial):
    return {
        "inciso": numero,
        "texto": texto_inicial.strip(),
        "alineas": []
    }

def _metadata(documento):
    return {
        "titulo":"",
        "tipo_ato":"",
        "data":"",
        "is_versao_atual":bool,
        "versao":"",
        "ementa":"",
        "urn":""
    }


def parse_lei(texto: str):
    """
    Recebe o texto bruto da lei e devolve uma lista de artigos estruturados.

    Cada artigo é um dict:
    {
        "artigo": "5º",
        "caput": "texto do caput...",
        "incisos": [ {"inciso": "I", "texto": "...", "alineas":[...]}, ... ],
        "paragrafos": [
            {
                "paragrafo": "1º",
                "texto": "...",
                "incisos": [ {...}, ... ]
            },
            ...
        ]
    }
    """
    artigos = []

    artigo_atual = None
    paragrafo_atual = None   # aponta para o parágrafo em construção (ou None)
    inciso_atual = None      # aponta para o inciso em construção (ou None)

    def contexto_de_incisos():
        """Decide se o próximo inciso pertence ao parágrafo atual
        ou diretamente ao artigo (quando não há parágrafo aberto)."""
        if paragrafo_atual is not None:
            return paragrafo_atual["incisos"]
        return artigo_atual["incisos"]

    linhas = texto.splitlines()

    for linha_bruta in linhas:
        linha = linha_bruta.strip()
        if not linha:
            continue

        # --- Novo artigo -----------------------------------------------
        m_art = ART_RE.match(linha)
        sequencia = log_sequencial.copy()
        if m_art:
            numero, resto = m_art.groups()
            if numero == f'{sequencia['artigo']}':
                sequencia['artigo'] += 1
                artigo_atual = _novo_artigo(numero, resto)
                artigos.append(artigo_atual)
                paragrafo_atual = None
                inciso_atual = None
            else:
                continue
            continue

        if artigo_atual is None:
            # Texto antes do primeiro "Art." (ementa, preâmbulo etc.)
            # Ignorado aqui; pode ser tratado separadamente se necessário.
            continue

        # --- Novo parágrafo ----------------------------------------------
        m_par = PARAGRAFO_RE.match(linha)
        if m_par:
            numero_num, unico, resto = m_par.groups()
            numero = numero_num if numero_num else "único"
            paragrafo_atual = _novo_paragrafo(numero, resto)
            artigo_atual["paragrafos"].append(paragrafo_atual)
            inciso_atual = None
            continue

        # --- Novo inciso ---------------------------------------------
        m_inc = INCISO_RE.match(linha)
        if m_inc:
            numero, resto = m_inc.groups()
            inciso_atual = _novo_inciso(numero, resto)
            contexto_de_incisos().append(inciso_atual)
            continue

        # --- Nova alínea -------------------------------------------------
        m_ali = ALINEA_RE.match(linha)
        if m_ali and inciso_atual is not None:
            letra, resto = m_ali.groups()
            inciso_atual["alineas"].append({
                "alinea": letra,
                "texto": resto.strip()
            })
            continue

        # --- Continuação de texto (linha "solta") -----------------------
        # Anexa a linha ao dispositivo mais específico que estiver aberto.
        if inciso_atual is not None and inciso_atual["alineas"]:
            inciso_atual["alineas"][-1]["texto"] += " " + linha
        elif inciso_atual is not None:
            inciso_atual["texto"] += " " + linha
        elif paragrafo_atual is not None:
            paragrafo_atual["texto"] += " " + linha
        else:
            artigo_atual["caput"] += " " + linha

    return artigos


def main():
    if len(sys.argv) < 2:
        print("Uso: python parser_lei.py <arquivo.txt> [saida.json]")
        sys.exit(1)

    caminho_entrada = sys.argv[1]
    caminho_saida = sys.argv[2] if len(sys.argv) > 2 else "artigos.json"

    with open(caminho_entrada, "r", encoding="utf-8") as f:
        texto = f.read()

    artigos = parse_lei(texto)

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(artigos, f, ensure_ascii=False, indent=2)

    print(f"{len(artigos)} artigo(s) encontrados. Resultado salvo em '{caminho_saida}'.")

def parser(entrada:str, saida):
        if len(entrada) < 2:
            print("Uso: python parser_lei.py <arquivo.txt> [saida.json]")
            sys.exit(1)

        caminho_entrada = entrada
        caminho_saida = saida 

        with open(caminho_entrada, "r", encoding="utf-8") as f:
            texto = f.read()

        artigos = parse_lei(texto)

        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(artigos, f, ensure_ascii=False, indent=2)

        print(f"{len(artigos)} artigo(s) encontrados. Resultado salvo em '{caminho_saida}'.")


# ---------------------------------------------------------------------------
# Exemplo de uso direto (executar este arquivo sem argumentos roda o exemplo)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        exemplo = """
Art. 1º Esta Lei estabelece normas gerais.

Art. 2º São beneficiários desta Lei:
I - os trabalhadores urbanos;
II - os trabalhadores rurais;
a) empregados;
b) autônomos.

§ 1º O disposto no caput não se aplica aos servidores públicos.
§ 2º Consideram-se trabalhadores rurais aqueles que:
I - exercem atividade agrícola;
II - exercem atividade pecuária.

Art. 3º Esta Lei entra em vigor na data de sua publicação.
Parágrafo único. Revogam-se as disposições em contrário.
"""
        resultado = parse_lei(exemplo)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))