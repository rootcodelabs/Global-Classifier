from translator import Translator
from paraphraser import Paraphraser
from langdetect import detect
from typing import List, Optional

class DataEnrichment:
    def __init__(self):
        print("Initializing DataEnrichment...")
        self.translator = Translator()
        self.paraphraser = Paraphraser()

    def enrich_data(self, text: str, num_return_sequences: int = 1, language_id: Optional[str] = None) -> List[str]:
        supported_languages = ['en', 'et', 'ru', 'pl', 'fi']

        if language_id:
            if language_id not in supported_languages:
                print(f"Language ID {language_id} is not supported. Trying to detect the language automatically.")
                lang = detect(text)
            else:
                lang = language_id
        else:
            lang = detect(text)
        
        print(f"Detected/Used language: {lang}")

        if lang not in supported_languages:
            print(f"Unsupported language: {lang}")
            return []

        paraphrases = self.paraphraser.generate_paraphrases(text, num_return_sequences)
        if lang == 'en':
            paraphrases = self.paraphraser.generate_paraphrases(text, num_return_sequences)
        else:
            english_text = self.translator.translate(text, lang, 'en')
            paraphrases = self.paraphraser.generate_paraphrases(english_text, num_return_sequences)
            translated_paraphrases = []
            for paraphrase in paraphrases:
                translated_paraphrase = self.translator.translate(paraphrase, 'en', lang)
                translated_paraphrases.append(translated_paraphrase)
            return translated_paraphrases

        print("*")
        return paraphrases
