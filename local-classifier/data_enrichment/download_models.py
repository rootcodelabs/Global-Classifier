from transformers import MarianMTModel, MarianTokenizer, AutoTokenizer, AutoModelForSeq2SeqLM
import json

def download_translator_models(config_path="config_files/translator_config.json"):
    with open(config_path, 'r') as file:
        config = json.load(file)
    models = config["models"]
    unsupported_model = config["unsupported-en-pl_model"]

    for key, (model_name, reverse_model_name) in models.items():
        MarianTokenizer.from_pretrained(model_name)
        MarianMTModel.from_pretrained(model_name)
        reverse_key = f"{key.split('-')[1]}-{key.split('-')[0]}"
        if reverse_model_name != unsupported_model:
            MarianTokenizer.from_pretrained(reverse_model_name)
            MarianMTModel.from_pretrained(reverse_model_name)

def download_paraphraser_model(config_path="config_files/paraphraser_config.json"):
    with open(config_path, 'r') as file:
        config = json.load(file)
    model_name = config["model_name"]
    AutoTokenizer.from_pretrained(model_name)
    AutoModelForSeq2SeqLM.from_pretrained(model_name)

if __name__ == "__main__":
    download_translator_models()
    download_paraphraser_model()