"""
parser_topicos.py

Script para extrair a estrutura de um documento organizado em tópicos
numerados hierarquicamente, no formato:

    1.
    1.1.
    1.1.1.
    1.1.1.1.
    1.1.1.1.1.
    1.1.1.1.1.1.

Suporta até 6 níveis de profundidade (ajustável).

Uso básico:
    from parser_topicos import parse_topicos
    topicos = parse_topicos(texto)

Ou via linha de comando:
    python parser_topicos.py caminho/para/documento.txt
"""

import re
import json
import sys


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

MAX_NIVEIS = 6  # altere aqui se precisar de mais ou menos níveis

# Reconhece números como "1", "1.1", "1.1.1" ... no início da linha,
# com ponto final opcional após o último segmento, seguido de espaço
# (título do tópico) ou fim de linha.
#   Ex.: "1. Introdução"      -> numero="1"      texto="Introdução"
#        "1.1 Objetivo"       -> numero="1.1"    texto="Objetivo"
#        "1.1.1."             -> numero="1.1.1"  texto=""
TOPICO_RE = re.compile(
    r'^\s*(\d+(?:\.\d+){0,%d})\.?(?:\s+(.*))?$' % (MAX_NIVEIS - 1)
)


def _novo_topico(numero, texto_inicial):
    return {
        "numero": numero,
        "texto": (texto_inicial or "").strip(),
        "subtopicos": []
    }


def parse_topicos(texto: str):
    """
    Recebe o texto bruto do documento e devolve uma lista de tópicos
    de nível 1, cada um com seus subtópicos aninhados recursivamente.

    Cada tópico é um dict:
    {
        "numero": "1.1",
        "texto": "texto do tópico...",
        "subtopicos": [ {...}, {...} ]
    }
    """
    raiz = []
    # pilha[i] = último tópico de nível (i+1) aberto
    pilha = [None] * MAX_NIVEIS
    topico_atual = None  # último tópico criado, para anexar continuações de texto

    for linha_bruta in texto.splitlines():
        linha = linha_bruta.strip()
        if not linha:
            continue

        m = TOPICO_RE.match(linha)
        if m:
            numero, resto = m.groups()
            nivel = numero.count(".") + 1

            if nivel > MAX_NIVEIS:
                # segurança: numeração mais profunda que o esperado,
                # trata como continuação de texto em vez de novo nível
                if topico_atual is not None:
                    topico_atual["texto"] += " " + linha
                continue

            novo = _novo_topico(numero, resto)

            if nivel == 1:
                raiz.append(novo)
            else:
                pai = pilha[nivel - 2]  # nível pai = nivel - 1 -> índice nivel-2
                if pai is not None:
                    pai["subtopicos"].append(novo)
                else:
                    # não encontrou pai (numeração fora de ordem) ->
                    # promove para a raiz para não perder o conteúdo
                    raiz.append(novo)

            pilha[nivel - 1] = novo
            # limpa níveis mais profundos, pois um novo tópico "fecha" os filhos anteriores
            for i in range(nivel, MAX_NIVEIS):
                pilha[i] = None

            topico_atual = novo
            continue

        # --- Linha de continuação (não bate com o padrão de numeração) ---
        if topico_atual is not None:
            topico_atual["texto"] += " " + linha
        # se ainda não há nenhum tópico aberto, a linha é ignorada
        # (ex.: título do documento, cabeçalho, etc.)

    return raiz


def main():
    if len(sys.argv) < 2:
        print("Uso: python parser_topicos.py <arquivo.txt> [saida.json]")
        sys.exit(1)

    caminho_entrada = sys.argv[1]
    caminho_saida = sys.argv[2] if len(sys.argv) > 2 else "topicos.json"

    with open(caminho_entrada, "r", encoding="utf-8") as f:
        texto = f.read()

    topicos = parse_topicos(texto)

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(topicos, f, ensure_ascii=False, indent=2)

    print(f"{len(topicos)} tópico(s) de nível 1 encontrados. Resultado salvo em '{caminho_saida}'.")


# ---------------------------------------------------------------------------
# Exemplo de uso direto
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        exemplo = """
1. Introdução
Este documento estabelece as diretrizes gerais.

1.1 Objetivo
Definir o escopo do projeto.

1.1.1 Escopo técnico
Abrange os requisitos de sistema.
1.1.1.1 Requisitos funcionais
O sistema deve permitir login de usuários.
1.1.1.2 Requisitos não funcionais
O sistema deve responder em até 2 segundos.

1.2 Justificativa
Atender à demanda crescente de usuários.

2. Metodologia
Descreve as etapas do trabalho.

2.1 Etapas
2.1.1 Planejamento
2.1.2 Execução
"""
        resultado = parse_topicos(exemplo)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))