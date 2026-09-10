# Banco de normas ICP-Brasil

Este projeto tem o objetivo de disponibilizar o arcabouço normativo da ICP-Brasil em formato de banco de dados para consulta facilitada por humanos e máquinas, com o objetivo de simplificar processos de consulta, atualização e arquivamento normativo, assim como dar suporte a desenvolvimentos futuros de ferramentas de auditoria, fiscalização e pesquisa no âmbito da ICP-Brasil.

## Funcionalidades
**Processamento de textos normativos**: recebe documentos normativos nos formatos .docx, .odt, .pdf ou .html e realiza a identificação de metadados, subdivisão em dispositivos (artigos, parágrafos, tópicos) e conversão para formato de objeto JSON.

**CRUD de banco de dados**: lê, grava, altera e exclui dados do banco NoSQL (chave de acesso deve ser fornecida pelo usuário).

**Interface de usuário**: dispõe de interface gráfica e aplicação Streamlit para autenticação de usuário e processos de CRUD.


## Tecnologias utilizadas
**Python**: Principal linguagem de desenvolvimento

**MongoDB**: Banco de dados NoSQL


**Streamlit**: Plataforma de front-end e deploy para web


**spaCy**: Biblioteca de processamento de linguagem natural

Demais bibliotecas, pacotes e recursos presentes no arquivo requirements.txt


## Roadmap
Este projeto ainda está em fase inicial de desenvolvimento. Todas as funcionalidades podem passar por alterações grandes em versões subsequentes. 

### Funcionalidades a implementar
- Gravação, alteração e exclusão no banco de dados via interface gráfica;
- Verificação de versionamento do documento;
- Solicitações de chave de API para desenvolvedores;
- Exportação de ato normativo editado como documento de texto;
- Ferramenta gráfica de comparação textual;
- Busca textual em múltiplos documentos simultâneos;
- Processamento de figuras e tabelas;

## 