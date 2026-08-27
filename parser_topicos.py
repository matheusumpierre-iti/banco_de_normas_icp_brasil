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

Regras de validação aplicadas:

  1) SEQUÊNCIA: um número só é aceito como um novo tópico se fizer
     sentido na sequência esperada:
       - Nível 1: deve seguir 1, 2, 3, 4...
       - Nível N (N>1): o primeiro filho de um tópico-pai deve ser 1
         (ex.: 2.1, não 2.3 antes de existir 2.1/2.2); os seguintes
         devem incrementar em 1 dentro do MESMO pai.
     Quando o número não bate com o esperado, a linha é tratada como
     CONTINUAÇÃO DE TEXTO do tópico mais específico aberto no momento,
     em vez de virar um novo item.

  2) DETECÇÃO DE SUMÁRIO / ELEMENTOS PRÉ-TEXTUAIS: é comum documentos
     terem um sumário/índice antes do corpo real, repetindo a MESMA
     numeração que reaparece depois. Usamos isso como sinal: se um
     tópico de nível 1 igual a "1" aparece de novo depois que a
     numeração já havia avançado além de 1, entende-se que tudo
     coletado até ali era sumário/pré-textual — o resultado acumulado
     é DESCARTADO e a leitura recomeça a partir desse ponto.
     Esse reinício só é aceito UMA VEZ por documento: se "1" aparecer
     de novo fora de sequência depois que o reinício já foi usado,
     ele é tratado como qualquer outra violação de sequência (vira
     continuação de texto do tópico aberto), sem apagar o conteúdo
     já coletado. Isso evita que um documento com reinícios legítimos
     de numeração (ex.: um anexo que recomeça em "1.") tenha seu
     corpo principal apagado por engano.
     Além disso, linhas com "cara" de entrada de sumário (pontilhado
     seguido de número de página, ex.: "1. Introdução ....... 5") são
     ignoradas mesmo que a numeração faça sentido, pois não fazem
     parte do corpo real do texto.

Uso básico:
    from parser_topicos import parse_topicos
    topicos = parse_topicos(texto)

    # Para ver também os avisos (reinícios detectados, itens rejeitados):
    topicos, avisos = parse_topicos(texto, retornar_avisos=True)

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
TOPICO_RE = re.compile(
    r'^\s*(\d+(?:\.\d+){0,%d})\.?(?:\s+(.*))?$' % (MAX_NIVEIS - 1)
)

# Linhas com "cara" de entrada de sumário/índice: título seguido de
# pontilhado (....) e um número de página no final, ou de vários
# espaços/tabs e um número no final.
#   Ex.: "1. Introdução .......................... 5"
#        "2.1 Objetivos	9"
TOC_LINE_RE = re.compile(
    r'(\.{3,}\s*\d+\s*$)|(\t+\d+\s*$)|(\s{3,}\d+\s*$)'
)

# Cabeçalhos típicos de seção de sumário/índice (para referência /
# possível filtragem adicional, embora a detecção principal seja via
# reinício de sequência).
SUMARIO_HEADER_RE = re.compile(
    r'^\s*(sum[aá]rio|[íi]ndice)\s*$', re.IGNORECASE
)


def _novo_topico(numero, texto_inicial):
    return {
        "numero": numero,
        "texto": (texto_inicial or "").strip(),
        "subtopicos": []
    }


def parse_topicos(texto: str, retornar_avisos: bool = False):
    """
    Recebe o texto bruto do documento e devolve uma lista de tópicos
    de nível 1, cada um com seus subtópicos aninhados recursivamente.

    Cada tópico é um dict:
    {
        "numero": "1.1",
        "texto": "texto do tópico...",
        "subtopicos": [ {...}, {...} ]
    }

    Se retornar_avisos=True, devolve uma tupla (topicos, avisos), em
    que 'avisos' é uma lista de strings descrevendo reinícios
    detectados e linhas rejeitadas por não seguirem a sequência.
    """
    raiz = []
    pilha = [None] * MAX_NIVEIS       # pilha[i] = último tópico aberto no nível i+1
    topico_atual = None

    ultimo_nivel1 = 0                 # último número de nível 1 aceito
    # contadores_filhos[id(topico)] = próximo número de filho esperado
    contadores_filhos = {}
    reinicio_ja_ocorreu = False       # a detecção de reinício só pode disparar 1 vez

    avisos = []

    def contador_filho_esperado(pai):
        return contadores_filhos.get(id(pai), 1)

    def registrar_filho_aceito(pai, numero_filho):
        contadores_filhos[id(pai)] = numero_filho + 1

    def resetar_estado(motivo):
        nonlocal raiz, pilha, topico_atual, ultimo_nivel1, contadores_filhos, reinicio_ja_ocorreu
        avisos.append(motivo)
        raiz = []
        pilha = [None] * MAX_NIVEIS
        topico_atual = None
        ultimo_nivel1 = 0
        contadores_filhos = {}
        reinicio_ja_ocorreu = True

    for num_linha, linha_bruta in enumerate(texto.splitlines(), start=1):
        linha = linha_bruta.strip()
        if not linha:
            continue

        # --- Ignora linhas com cara de entrada de sumário/índice --------
        if TOC_LINE_RE.search(linha):
            avisos.append(
                f"Linha {num_linha} ignorada (parece entrada de sumário/índice): {linha!r}"
            )
            continue

        m = TOPICO_RE.match(linha)
        if m:
            numero_str, resto = m.groups()
            segmentos = [int(s) for s in numero_str.split(".")]
            nivel = len(segmentos)

            if nivel > MAX_NIVEIS:
                if topico_atual is not None:
                    topico_atual["texto"] += " " + linha
                continue

            valido = False

            if nivel == 1:
                n = segmentos[0]
                if n == ultimo_nivel1 + 1:
                    valido = True
                elif n == 1 and ultimo_nivel1 >= 1 and not reinicio_ja_ocorreu:
                    # Reinício em "1" após já termos avançado -> sinal de
                    # que tudo até aqui era sumário/pré-textual.
                    # Só é permitido UMA VEZ por documento (ver docstring).
                    resetar_estado(
                        f"Linha {num_linha}: reinício detectado em '{numero_str}' "
                        f"(numeração já havia avançado até {ultimo_nivel1}). "
                        f"Conteúdo anterior descartado como sumário/pré-textual."
                    )
                    valido = True
                # elif n == 1 e reinicio_ja_ocorreu: 'valido' permanece False
                # de propósito -> cai no bloco genérico de rejeição abaixo,
                # que já registra o aviso e trata a linha como continuação
                # de texto do tópico aberto (não apaga nada do que já foi
                # coletado).
            else:
                pai = pilha[nivel - 2]
                if pai is not None:
                    esperado = contador_filho_esperado(pai)
                    if segmentos[-1] == esperado:
                        valido = True

            if valido:
                novo = _novo_topico(numero_str, resto)

                if nivel == 1:
                    raiz.append(novo)
                    ultimo_nivel1 = segmentos[0]
                else:
                    pai = pilha[nivel - 2]
                    pai["subtopicos"].append(novo)
                    registrar_filho_aceito(pai, segmentos[-1])

                pilha[nivel - 1] = novo
                for i in range(nivel, MAX_NIVEIS):
                    pilha[i] = None

                topico_atual = novo
                continue
            else:
                avisos.append(
                    f"Linha {num_linha} rejeitada (fora da sequência esperada): {linha!r}"
                )
            # se não validou, cai para tratar como continuação de texto

        # --- Linha de continuação -----------------------------------
        if topico_atual is not None:
            topico_atual["texto"] += " " + linha
        # se ainda não há nenhum tópico aberto, a linha é ignorada
        # (ex.: capa, título do documento, cabeçalho, etc.)

    if retornar_avisos:
        return raiz, avisos
    return raiz


def main():
    if len(sys.argv) < 2:
        print("Uso: python parser_topicos.py <arquivo.txt> [saida.json]")
        sys.exit(1)

    caminho_entrada = sys.argv[1]
    caminho_saida = sys.argv[2] if len(sys.argv) > 2 else "topicos.json"

    with open(caminho_entrada, "r", encoding="utf-8") as f:
        texto = f.read()

    topicos, avisos = parse_topicos(texto, retornar_avisos=True)

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(topicos, f, ensure_ascii=False, indent=2)

    print(f"{len(topicos)} tópico(s) de nível 1 encontrados. Resultado salvo em '{caminho_saida}'.")
    if avisos:
        print("\nAvisos:")
        for a in avisos:
            print(f"  - {a}")


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