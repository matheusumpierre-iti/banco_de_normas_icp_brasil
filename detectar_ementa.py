"""
detectar_ementa.py

Detecta a ementa de um texto legal (.docx) usando pistas de FORMATAÇÃO,
não apenas o conteúdo do texto.

Características típicas da ementa em documentos legislativos brasileiros:
  - Fica posicionada ENTRE o título da norma e o primeiro "Art. 1º".
  - Costuma estar em itálico.
  - Costuma ter recuo à esquerda maior que o corpo do texto
    (frequentemente alinhada a partir do meio da página).
  - Não é um título (não costuma estar em negrito/caixa alta) e não é
    o preâmbulo ("O PRESIDENTE DA REPÚBLICA... decreta...").

O script pontua cada parágrafo candidato (os que vêm antes do primeiro
"Art.") de acordo com essas pistas e escolhe o de maior pontuação.

Uso:
    from detectar_ementa import detectar_ementa
    resultado = detectar_ementa("lei.docx")
    print(resultado["texto"])

Ou via linha de comando:
    python detectar_ementa.py lei.docx
"""

import re
import sys
from docx import Document

ART_RE = re.compile(r'^\s*Art\.?\s*\d+', re.IGNORECASE)


def _indent_em_polegadas(paragraph):
    """Retorna o recuo à esquerda em polegadas (0 se não definido)."""
    indent = paragraph.paragraph_format.left_indent
    if indent is None:
        return 0.0
    return indent.inches


def _percentual_italico(paragraph):
    """Proporção de caracteres em itálico dentro do parágrafo (0 a 1)."""
    total = 0
    italico = 0
    for run in paragraph.runs:
        n = len(run.text)
        total += n
        if run.italic:
            italico += n
    if total == 0:
        return 0.0
    return italico / total


def _percentual_negrito(paragraph):
    total = 0
    negrito = 0
    for run in paragraph.runs:
        n = len(run.text)
        total += n
        if run.bold:
            negrito += n
    if total == 0:
        return 0.0
    return negrito / total


def _eh_preambulo(texto):
    """Heurística simples para reconhecer o preâmbulo e descartá-lo
    como candidato a ementa (ex.: 'O PRESIDENTE DA REPÚBLICA...')."""
    gatilhos = [
        "faço saber", "decreta", "sanciono", "resolve", "promulgo",
        "o congresso nacional", "o presidente da república",
        "o governador", "o prefeito"
    ]
    texto_lower = texto.lower()
    return any(g in texto_lower for g in gatilhos)


def detectar_ementa(caminho_docx: str, indent_minimo_polegadas: float = 0.7):
    """
    Abre o .docx e tenta identificar o parágrafo da ementa usando
    pistas de formatação. Retorna um dict com o texto encontrado e
    a pontuação/justificativa, ou None se nenhum candidato plausível
    for encontrado.
    """
    doc = Document(caminho_docx)

    candidatos = []
    for idx, paragraph in enumerate(doc.paragraphs):
        texto = paragraph.text.strip()
        if not texto:
            continue

        # Para assim que encontrar o primeiro "Art." — a ementa sempre
        # vem antes dele.
        if ART_RE.match(texto):
            break

        candidatos.append((idx, paragraph, texto))

    if not candidatos:
        return None

    melhor = None
    melhor_pontuacao = -1
    detalhes_melhor = None

    for idx, paragraph, texto in candidatos:
        pontuacao = 0
        motivos = []

        pct_italico = _percentual_italico(paragraph)
        if pct_italico > 0.7:
            pontuacao += 3
            motivos.append(f"itálico ({pct_italico:.0%})")

        recuo = _indent_em_polegadas(paragraph)
        if recuo >= indent_minimo_polegadas:
            pontuacao += 2
            motivos.append(f"recuo à esquerda de {recuo:.2f}\"")

        alinhamento = paragraph.alignment
        # WD_ALIGN_PARAGRAPH.JUSTIFY = 3 ; RIGHT = 2
        if alinhamento is not None and int(alinhamento) in (2, 3):
            pontuacao += 1
            motivos.append(f"alinhamento={alinhamento}")

        pct_negrito = _percentual_negrito(paragraph)
        if pct_negrito > 0.5:
            pontuacao -= 3  # títulos costumam ser negrito -> penaliza
            motivos.append("negrito (provável título, penalizado)")

        if _eh_preambulo(texto):
            pontuacao -= 5  # descarta preâmbulo
            motivos.append("parece preâmbulo (penalizado)")

        if texto.isupper():
            pontuacao -= 2  # títulos costumam estar em caixa alta
            motivos.append("caixa alta (provável título, penalizado)")

        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor = texto
            detalhes_melhor = {
                "indice_paragrafo": idx,
                "pontuacao": pontuacao,
                "motivos": motivos
            }

    if melhor is None or melhor_pontuacao <= 0:
        return None

    detalhes = {
        "texto": melhor,
        **detalhes_melhor
    }

    return detalhes['texto']


def main():
    if len(sys.argv) < 2:
        print("Uso: python detectar_ementa.py <arquivo.docx>")
        sys.exit(1)

    resultado = detectar_ementa(sys.argv[1])
    if resultado is None:
        print("Não foi possível identificar a ementa com confiança.")
    else:
        print("Ementa detectada:")
        print(f'  "{resultado["texto"]}"')
        print(f"  (parágrafo #{resultado['indice_paragrafo']}, "
              f"pontuação={resultado['pontuacao']}, "
              f"motivos={resultado['motivos']})")

def parse_ementa(arquivo_docx: str):
    if len(sys.argv) < 2:
        print("Uso: python detectar_ementa.py <arquivo.docx>")
        sys.exit(1)

    resultado = detectar_ementa(arquivo_docx)
    if resultado is None:
        print("Não foi possível identificar a ementa com confiança.")
    else:
        return resultado

if __name__ == "__main__":
    main()