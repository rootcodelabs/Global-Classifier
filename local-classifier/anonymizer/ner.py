from transformers import pipeline

class NERProcessor:
    def __init__(self):
        self.model = pipeline("ner", model="xlm-roberta-large-finetuned-conll03-english")

    def identify_entities(self, text: str):
        return self.model(text)
