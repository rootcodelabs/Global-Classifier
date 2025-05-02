from unittest import TestCase
import unittest
from data_enrichment import DataEnrichment

class TestDataEnrichment(TestCase):

    def setUp(self):
        self.enricher = DataEnrichment()

    def test_enrich_data_with_supported_language(self):
        original_sentence = "Hello, I hope this email finds you well. I am writing to inquire about the status of my application."

        enriched_data = self.enricher.enrich_data(original_sentence)
        self.assertIsNotNone(enriched_data)

        for i, paraphrase in enumerate(enriched_data, 1):
            print(f"Paraphrase {i}: {paraphrase}")

    def test_enrich_data_with_unsupported_language(self):
        original_sentence = "Pozdravljeni, upam, da vas to e-pošto dobro najde. Pišem, da se pozanimam o stanju moje prijave."

        enriched_data = self.enricher.enrich_data(original_sentence)
        self.assertEqual(enriched_data, [])

    def test_enrich_data_with_estonian_sentence(self):
        original_sentence = "Tere, ma loodan, et see e-kiri leiab teid hästi. Ma kirjutan päringu staatuse minu taotluse. Ma esitasin kõik nõutavad dokumendid möödunud kuu, kuid ma pole saanud ühtegi värskendust sellest ajast. Kas saaksite palun mulle hetkeseisu kohta teavet anda?"

        enriched_data = self.enricher.enrich_data(original_sentence)
        self.assertIsNotNone(enriched_data)

        for i, paraphrase in enumerate(enriched_data, 1):
            print(f"Paraphrase {i}: {paraphrase}")

    def test_enrich_data_with_russian_sentence(self):
        original_sentence = "Привет, надеюсь, что это письмо находит вас в порядке. Я пишу с запросом о статусе моего заявления. Я подал все необходимые документы в прошлом месяце, но с тех пор не получил никаких обновлений. Не могли бы вы, пожалуйста, предоставить мне текущий статус?"

        enriched_data = self.enricher.enrich_data(original_sentence)
        self.assertIsNotNone(enriched_data)

        for i, paraphrase in enumerate(enriched_data, 1):
            print(f"Paraphrase {i}: {paraphrase}")

    def test_enrich_data_with_polish_sentence(self):
        original_sentence = "Cześć, mam nadzieję, że to e-mail znajduje cię w dobrym zdrowiu. Piszę z zapytaniem o status mojej aplikacji. Złożyłem wszystkie wymagane dokumenty w zeszłym miesiącu, ale od tego czasu nie otrzymałem żadnej aktualizacji. Czy moglibyście podać mi bieżący status?"

        enriched_data = self.enricher.enrich_data(original_sentence)
        self.assertIsNotNone(enriched_data)

        for i, paraphrase in enumerate(enriched_data, 1):
            print(f"Paraphrase {i}: {paraphrase}")

    def test_enrich_data_with_finnish_sentence(self):
        original_sentence = "Hei, toivottavasti tämä sähköposti tavoittaa teidät hyvin. Kirjoitan tiedustelun tilastani hakemukseni suhteen. Lähetin kaikki tarvittavat asiakirjat viime kuussa, mutta en ole sen jälkeen saanut päivityksiä. Voisitteko antaa minulle ajantasaisen tilanteen?"

        enriched_data = self.enricher.enrich_data(original_sentence)
        self.assertIsNotNone(enriched_data)

        for i, paraphrase in enumerate(enriched_data, 1):
            print(f"Paraphrase {i}: {paraphrase}")

if __name__ == "__main__":
    unittest.main()
