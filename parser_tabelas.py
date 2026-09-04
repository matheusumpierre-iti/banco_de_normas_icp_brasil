import pdfplumber
import pandas as pd
import json

if __name__ == '__main__':
    with pdfplumber.open(r'C:\Users\matheus.umpierre\Projetos\lexml_icp_brasil_gitlab\lex_icp_brasil\testes\DOC-ICP-03.02_v.2.0_REQUISITOS_MÍNIMOS_SEGURANÇA_PSBIO.pdf', ) as pdf:
        tabelas_documento = []
        for p, page in enumerate(pdf.pages):
            tabelas_pagina = page.extract_tables()
            for i, tabela in enumerate(tabelas_pagina):
                header = tabela[0]
                dados = tabela[1:]
                if len(dados) > 0:
                    df = pd.DataFrame(dados, columns=header)
                    tabela_dict = df.to_dict(orient='records')
                    tabelas_documento.append({
                        'pagina_tabela':p+1,
                        'ordem_tabela': i+1,
                        'indice_tabela':f'tabela.{p+1}.{i+1}',
                        'tabela':tabela_dict
                    })
        tabelas_json = json.dumps(tabelas_documento, ensure_ascii=False, indent=2)
        tabelas_json = tabelas_json.replace(r'\n', ' ')
        print(tabelas_json)

def parse_tabelas_pdf(arquivo_pdf:str):
    if arquivo_pdf.endswith('pdf'):
        with pdfplumber.open(arquivo_pdf) as pdf:
                tabelas_documento = []
                for p, page in enumerate(pdf.pages):
                    tabelas_pagina = page.extract_tables()
                    for i, tabela in enumerate(tabelas_pagina):
                        header = tabela[0]
                        dados = tabela[1:]
                        if len(dados) > 0:
                            df = pd.DataFrame(dados, columns=header)
                            tabela_dict = df.to_dict(orient='records')
                            tabelas_documento.append({
                                'pagina_tabela':p+1,
                                'ordem_tabela': i+1,
                                'indice_tabela':f'tabela.{p+1}.{i+1}',
                                'tabela':tabela_dict
                            })
                tabelas_json = json.dumps(tabelas_documento, ensure_ascii=False, indent=2)
                tabelas_json = tabelas_json.replace(r'\n', ' ')
                return tabelas_documento
    else:
        return r'{}'

