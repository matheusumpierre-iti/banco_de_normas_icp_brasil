"""
parser_lei.py

Script para extrair a estrutura de um texto legal (lei, decreto, etc.),
agrupando cada "Art." com seus respectivos parágrafos (§) e incisos
(I, II, III...), incluindo alíneas (a, b, c...) quando existirem.

Regra de validação de SEQUÊNCIA:
    Um dispositivo só é aceito como um NOVO artigo/parágrafo/inciso/alínea
    se o número dele fizer sentido na sequência do documento:
      - O primeiro artigo deve ser o Art. 1º; os seguintes devem
        incrementar em 1 (2º, 3º, 4º...). Artigos com sufixo de letra
        (ex.: "6º-A", "6º-B" — artigos incluídos por lei posterior) são
        aceitos sem quebrar a sequência principal, desde que o número
        base já tenha aparecido antes.
      - O primeiro parágrafo de um artigo deve ser "único" ou "1º"; os
        seguintes devem incrementar em 1 (2º, 3º...).
      - Os incisos devem seguir a sequência de numerais romanos
        (I, II, III, IV...), dentro do contexto em que aparecem (direto
        no artigo, ou dentro de um parágrafo específico).
      - As alíneas devem seguir a sequência alfabética (a, b, c...)
        dentro do inciso em que aparecem.

    Quando uma linha bate com o padrão regex de um dispositivo, mas o
    número NÃO faz sentido na sequência esperada, ela é tratada como
    CONTINUAÇÃO DE TEXTO do dispositivo mais específico que estiver
    aberto, em vez de virar um novo item na estrutura.

Uso básico:
    from parser_lei import parse_lei
    artigos = parse_lei(texto)

Ou via linha de comando:
    python parser_lei.py caminho/para/lei.txt
"""

import re
import json
import sys


# ---------------------------------------------------------------------------
# Padrões (regex) para reconhecer cada tipo de dispositivo legal
# ---------------------------------------------------------------------------

# Ex.: "Art. 5º", "Art. 12", "Art. 6º-A"
ART_RE = re.compile(
    r'^\s*Art\.?\s*(\d+)[ºo°]?(-[A-Za-z]+)?\.?\s*(.*)$',
    re.IGNORECASE
)

# Ex.: "§ 1º", "§1º", "Parágrafo único"
PARAGRAFO_RE = re.compile(
    r'^\s*(?:§\s*(\d+)[ºo°]?|(Par[aá]grafo\s+[uú]nico))\.?\s*(.*)$',
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


# ---------------------------------------------------------------------------
# Utilitários de conversão / validação de sequência
# ---------------------------------------------------------------------------

_ROMANOS = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}


def _roman_to_int(s):
    """Converte um numeral romano em inteiro. Retorna None se inválido."""
    s = s.upper()
    if not s or any(ch not in _ROMANOS for ch in s):
        return None
    total = 0
    anterior = 0
    for ch in reversed(s):
        valor = _ROMANOS[ch]
        if valor < anterior:
            total -= valor
        else:
            total += valor
            anterior = valor
    return total


def _letra_para_indice(letra):
    """'a' -> 0, 'b' -> 1, ..."""
    return ord(letra.lower()) - ord('a')


# ---------------------------------------------------------------------------
# Construtores de nós da árvore
# ---------------------------------------------------------------------------

def _novo_artigo(numero, texto_inicial):
    return {
        "artigo": numero,
        "caput": texto_inicial.strip(),
        "sufixo_urn": f'art.{numero}',
        "incisos": [],      # incisos que pertencem diretamente ao caput
        "paragrafos": []    # cada parágrafo tem sua própria lista de incisos
    }


def _novo_paragrafo(numero, texto_inicial):
    return {
        "paragrafo": numero,
        "texto": texto_inicial.strip(),
        "sufixo_urn": f'paragrafo.{numero}',
        "incisos": []
    }


def _novo_inciso(numero, texto_inicial):
    return {
        "inciso": numero,
        "texto": texto_inicial.strip(),
        "sufixo_urn": f'inciso.{numero}',
        "alineas": []
    }


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

def parse_lei(texto: str):
    """
    Recebe o texto bruto da lei e devolve uma lista de artigos estruturados.

    Cada artigo é um dict:
    {
        "artigo": "5",
        "caput": "texto do caput...",
        "incisos": [ {"inciso": "I", "texto": "...", "alineas":[...]}, ... ],
        "paragrafos": [
            {
                "paragrafo": "1",
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

    # --- controle de sequência esperada em cada nível ---
    expected_art_base = 1        # próximo número base de artigo esperado
    last_art_base = None         # último número base de artigo aceito (p/ "6º-A")

    expected_par = None          # None = ainda não houve parágrafo neste artigo
                                  # 'unico' ou um inteiro (próximo número esperado)

    expected_inciso_artigo = 1   # próximo inciso esperado direto no artigo
    expected_inciso_par = 1      # próximo inciso esperado dentro do parágrafo atual

    expected_alinea_idx = 0      # próxima alínea esperada (0='a', 1='b', ...)

    def contexto_de_incisos():
        if paragrafo_atual is not None:
            return paragrafo_atual["incisos"]
        return artigo_atual["incisos"]

    def anexar_continuacao(linha):
        """Anexa uma linha que não pôde ser validada como novo dispositivo
        ao texto do dispositivo mais específico atualmente aberto."""
        if inciso_atual is not None and inciso_atual["alineas"]:
            inciso_atual["alineas"][-1]["texto"] += " " + linha
        elif inciso_atual is not None:
            inciso_atual["texto"] += " " + linha
        elif paragrafo_atual is not None:
            paragrafo_atual["texto"] += " " + linha
        elif artigo_atual is not None:
            artigo_atual["caput"] += " " + linha
        # se nada estiver aberto ainda, a linha é ignorada (texto antes do Art. 1º)

    linhas = texto.splitlines()

    for linha_bruta in linhas:
        linha = linha_bruta.strip()
        if not linha:
            continue

        # --- Possível novo artigo ---------------------------------------
        m_art = ART_RE.match(linha)
        if m_art:
            numero_base_str, sufixo, resto = m_art.groups()
            numero_base = int(numero_base_str)

            valido = False
            if sufixo:
                # Ex.: "6º-A" — só é válido se o número base já é o último
                # artigo "normal" aceito (artigo incluído logo após ele).
                if last_art_base is not None and numero_base == last_art_base:
                    valido = True
            else:
                if numero_base == expected_art_base:
                    valido = True

            if valido:
                numero_completo = numero_base_str + (sufixo or "")
                artigo_atual = _novo_artigo(numero_completo, resto)
                artigos.append(artigo_atual)

                if not sufixo:
                    expected_art_base = numero_base + 1
                    last_art_base = numero_base
                # se tinha sufixo, não avança expected_art_base nem last_art_base

                # reseta contadores dependentes do artigo
                paragrafo_atual = None
                inciso_atual = None
                expected_par = None
                expected_inciso_artigo = 1
                expected_inciso_par = 1
                expected_alinea_idx = 0
                continue
            # se não é válido na sequência, cai para tratar como continuação

        if artigo_atual is None:
            # Ainda não achamos um Art. 1º válido -> ignora linha (ementa,
            # preâmbulo etc.) em vez de tentar anexar em lugar nenhum.
            continue

        # --- Possível novo parágrafo -------------------------------------
        m_par = PARAGRAFO_RE.match(linha)
        if m_par:
            numero_num, unico, resto = m_par.groups()

            valido = False
            numero_final = None

            if unico:
                if expected_par is None:
                    valido = True
                    numero_final = "único"
                    # depois de "único" não deveria haver outro parágrafo,
                    # mas travamos expected_par num estado que só aceitaria
                    # nova sequência numérica caso o documento (raramente)
                    # tenha mais parágrafos após um "único" mal identificado.
                    expected_par = "unico_usado"
            elif numero_num is not None:
                n = int(numero_num)
                if expected_par is None and n == 1:
                    valido = True
                elif isinstance(expected_par, int) and n == expected_par:
                    valido = True

                if valido:
                    numero_final = numero_num
                    expected_par = n + 1

            if valido:
                paragrafo_atual = _novo_paragrafo(numero_final, resto)
                artigo_atual["paragrafos"].append(paragrafo_atual)
                inciso_atual = None
                expected_inciso_par = 1
                expected_alinea_idx = 0
                continue
            # se não bateu a sequência, cai para tratar como continuação

        # --- Possível novo inciso -----------------------------------
        m_inc = INCISO_RE.match(linha)
        if m_inc:
            numero_romano, resto = m_inc.groups()
            valor = _roman_to_int(numero_romano)

            if valor is not None:
                if paragrafo_atual is not None:
                    esperado = expected_inciso_par
                else:
                    esperado = expected_inciso_artigo

                if valor == esperado:
                    inciso_atual = _novo_inciso(numero_romano, resto)
                    contexto_de_incisos().append(inciso_atual)

                    if paragrafo_atual is not None:
                        expected_inciso_par += 1
                    else:
                        expected_inciso_artigo += 1
                    expected_alinea_idx = 0
                    continue
            # numeral inválido ou fora de sequência -> trata como continuação

        # --- Possível nova alínea ---------------------------------------
        m_ali = ALINEA_RE.match(linha)
        if m_ali and inciso_atual is not None:
            letra, resto = m_ali.groups()
            if _letra_para_indice(letra) == expected_alinea_idx:
                inciso_atual["alineas"].append({
                    "alinea": letra,
                    "texto": resto.strip()
                })
                expected_alinea_idx += 1
                continue
            # fora de sequência -> trata como continuação

        # --- Linha de continuação (não validada como novo dispositivo) ---
        anexar_continuacao(linha)

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

Art. 2º-A Este artigo foi incluído por lei posterior.

Art. 3º Esta Lei entra em vigor na data de sua publicação.
Parágrafo único. Revogam-se as disposições em contrário.
"""
        resultado = parse_lei(exemplo)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))