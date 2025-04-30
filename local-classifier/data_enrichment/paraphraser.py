import json
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from typing import List
import torch

class Paraphraser:
    def __init__(self, config_path: str = "config_files/paraphraser_config.json"):
        print(f"in para init")
        with open(config_path, 'r') as file:
            config = json.load(file)
        
        self.model_name = config["model_name"]
        print("in para init2")
        self.num_beams = config["num_beams"]
        self.num_beam_groups = config["num_beam_groups"]
        self.default_num_return_sequences = config["num_return_sequences"]
        self.repetition_penalty = config["repetition_penalty"]
        self.diversity_penalty = config["diversity_penalty"]
        self.no_repeat_ngram_size = config["no_repeat_ngram_size"]
        self.temperature = config["temperature"]
        self.max_length = config["max_length"]
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name).to(self.device)  # Move model to device
        # self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
        # self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name, local_files_only=True).to(self.device)

    def generate_paraphrases(self, question: str, num_return_sequences: int = None) -> List[str]:
        if num_return_sequences is None or num_return_sequences <= 0:
            num_return_sequences = self.default_num_return_sequences

        input_ids = self.tokenizer(
            f'paraphrase: {question}',
            return_tensors="pt", padding="longest",
            max_length=self.max_length,
            truncation=True,
        ).input_ids.to(self.device)

        print(f"[Paraphraser generate_paraphrases] Input IDs are on device: {input_ids.device}")

        outputs = self.model.generate(
            input_ids,
            temperature=self.temperature,
            repetition_penalty=self.repetition_penalty,
            num_return_sequences=num_return_sequences,
            no_repeat_ngram_size=self.no_repeat_ngram_size,
            num_beams=self.num_beams,
            num_beam_groups=self.num_beam_groups,
            max_length=self.max_length,
            diversity_penalty=self.diversity_penalty
        )

        print(f"[Paraphraser generate_paraphrases] Outputs are on device: {outputs.device}")

        res = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)

        return res
