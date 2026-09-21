
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
