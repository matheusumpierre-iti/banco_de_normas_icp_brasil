import pandas as pd
import json
import spacy 
import pypandoc
from pypandoc.pandoc_download import download_pandoc

output = pypandoc.convert_file(r'C:\Users\matheus.umpierre\Projetos\Ambiente Python\LexML - ICP-Brasil\Resolucao152_revogada.odt', to='html', outputfile='output.html')
