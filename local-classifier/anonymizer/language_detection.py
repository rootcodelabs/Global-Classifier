from langdetect import detect, LangDetectException

class LanguageDetector:
    @staticmethod
    def detect_language(text: str) -> str:
        try:
            return detect(text)
        except LangDetectException:
            return "unknown"
