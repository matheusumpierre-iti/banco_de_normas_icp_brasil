# LexML ICP-Brasil
## Introdução
Este projeto tem a proposta de aplicar os aprendizados do projeto LexML Brasil, desenvolvido por GT do Senado Federal em 2008 [[1]](https://projeto.lexml.gov.br/documentacao/Apresentacao.pdf) à gestão do arcabouço normativo da ICP-Brasil. O projeto em referência objetiva padronizar a estruturação e prover mais facilidade de acesso a documentos normativos.
>>Na organização de um acervo (conjunto de itens) é necessário definir, entre 
outras coisas, um critério de  identidade, ou seja, que tipos de itens devem ser 
considerados e que parâmetros identificam univocamente cada item. Por exemplo, no 
caso de normas jurídicas, é possível considerar os seguintes tipos de itens: a) a norma, 
partindo de uma perspectiva histórica, considerando toda a sua evolução no tempo; b) a 
versão do texto de uma norma para uma determinada data; c) o dispositivo de uma 
versão específica da norma. Para cada um destes três níveis de granularidade listados, é 
possível definir um grupo de elementos (datas, tipos, números seqüenciais etc.) para a 
composição de um identificador unívoco [[1](https://projeto.lexml.gov.br/documentacao/Apresentacao.pdf), p.3]

### Diagnóstico



## Objetivos

1. Estruturar os atos normativos da ICP-Brasil no formato interoperável XML.
2. Gerar uma URN (Nome Uniforme) para cada ato normativo e cada dispotivo interno dos referidos atos.
3. Disponibiizar metadados em nível de dispositivo normativo em banco de dados estruturados.


### Resultados esperados
- Controle preciso de remissões e referências documentais.
- Redução do trabalho operacional na edição de atos normativos.
- Permitir interoperabilidade com aplicações de auditoria, fiscalização e normatização.
- Permitir interoperabilidade com repositórios e acervos normativos nacionais e internacionais. 
- Possibilitar a validação automática de estrutura documental.

## Solução
### Requisitos
- A solução deve ser capaz de catalogar de forma estrutura o texto legal dos atos normativos a nível de dispositivo.
- A solução deve ser capaz de adaptar sua lógica aos diferentes tipos de atos normativos da ICP-Brasil (DOC-ICP, Ato Normativo, Resolução, entre outros).
- As ações de catalogar, atualizar, consultar e filtrar os dados armazenados devem ser acessíveis para usuários tecnicamente leigos.

### Bibliotecas e ferramentas
- **Streamlit**: Front-end e deploy do app finalizado;
- **Pandas**: Processamento de dados estruturados;
- **SQLite**: Solução portátil de banco de dados;

### Arquitetura
- **Módulo principal (main.py)**: contém as classes e funções responsáveis pela extração de metadados estruturados a partir dos documentos.
- **Módulo de operações de banco de dados (db.py)** : contém as funções de SQLite
- **Módulo de banco de dados (database.db)**: contém o banco de dados SQLite
- **Módulo de interface (streamlit.py)**: contém a GUI construída em Streamlit
  
## Referências
[1] https://projeto.lexml.gov.br/documentacao/Apresentacao.pdf