import pypandoc
import mammoth
import docx

convertido = mammoth.convert_to_html(r'testes\IN2024-28_DOC_ICP_04.01.docx')

print(convertido)