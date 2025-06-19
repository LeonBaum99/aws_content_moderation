import os
import re
import spacy
from typing import List

_nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])

_THIS_DIR = os.path.dirname(__file__)
_STOPWORDS_PATH = os.path.join(_THIS_DIR, "stopwords.txt")
with open(_STOPWORDS_PATH, encoding="utf-8") as f:
    CUSTOM_STOP_WORDS = {w.strip().lower() for w in f if w.strip()}

def tokenize(text: str) -> List[str]:
    doc = _nlp(text)
    return [tok.text.lower() for tok in doc if not tok.is_punct]

def remove_stopwords(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t not in CUSTOM_STOP_WORDS]

def lemmatize(tokens: List[str]) -> List[str]:
    doc = _nlp(" ".join(tokens))
    return [tok.lemma_.lower() for tok in doc]

def preprocess_review(review: dict) -> List[str]:
    text = (review.get("summary", "") + " " + review.get("reviewText", "")).strip()
    tokens = tokenize(text)
    tokens = remove_stopwords(tokens)
    tokens = lemmatize(tokens)
    return [t for t in tokens if re.fullmatch(r"[a-z]+", t)]