class TextProcessor:
    @staticmethod
    def split_text(text: str, max_length: int):
        chunks = []
        for i in range(0, len(text), max_length):
            chunk = text[i:i + max_length]
            if i != 0:
                chunk = text[i-100:i + max_length]
            chunks.append(chunk)
        return chunks

    @staticmethod
    def combine_chunks(chunks: list):
        combined_text = "".join(chunks)
        return combined_text
