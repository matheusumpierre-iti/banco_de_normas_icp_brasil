import spacy
import roman
from spacy.matcher import Matcher
from main import doc

nlp = spacy.load('pt_core_news_lg')
matcher = Matcher(nlp.vocab)

matcher.add('INICIO_PARAGRAFO', [[{'ORTH':{'IN':['Parágrafo','§']}, 'IS_SENT_START':True}, {'LIKE_NUM':True}]])
matcher.add('INICIO_ARTIGO', [[{'ORTH':'Art.','IS_SENT_START':True}, {'LIKE_NUM':True}]])
matcher.add('INCISO', [[{'ORTH':{'IN':[roman.toRoman(i) for i in range(1,99)]}}]])
matcher.add('FIM', [[{'TEXT':'.'}]])


matches = matcher(doc)

for match_id, start, end in matches:
    label = nlp.vocab.strings[match_id]  # converte hash -> string
    span = doc[start:end]                # Span com o texto real
    print(f"{label}: '{span.text}'  (tokens {start}-{end})")