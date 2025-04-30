import re

class HTMLCleaner:
    def __init__(self):
        pass

    def remove_html_tags(self, text):
        clean_text = re.sub(r'<.*?>', '', text)
        return clean_text