from transformers import XLMRobertaTokenizer, XLMRobertaForSequenceClassification,Trainer, TrainingArguments, DistilBertTokenizer, DistilBertForSequenceClassification, BertForSequenceClassification, BertTokenizer
from torch.utils.data import Dataset
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import torch
import shutil
import pandas as pd
import os
from constants import TRAINING_LOGS_PATH
from loguru import logger

from transformers import logging
import warnings
warnings.filterwarnings("ignore", message="Some weights of the model checkpoint were not used when initializing")
logging.set_verbosity_error()

logger.add(sink=TRAINING_LOGS_PATH)

class CustomDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        item['labels'] = self.labels[idx]
        return item

    def __len__(self):
        return len(self.labels)
    

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
logger.info(f"TRAINING HARDWARE {device}")


class TrainingPipeline:
    def __init__(self, dfs,model_name):           
        
        self.model_name = model_name
        self.dfs = dfs
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        if model_name == 'distil-bert':
            self.base_model= DistilBertForSequenceClassification.from_pretrained('distilbert-base-uncased')

            for param in self.base_model.distilbert.parameters():
                param.requires_grad = False

            for param in self.base_model.distilbert.transformer.layer[-2:].parameters():
                param.requires_grad = True

            for param in self.base_model.classifier.parameters():
                param.requires_grad = True

        elif model_name == 'roberta':
            self.base_model= XLMRobertaForSequenceClassification.from_pretrained('xlm-roberta-base')
            for param in self.base_model.roberta.parameters():
                param.requires_grad = False

            for param in self.base_model.roberta.encoder.layer[-2:].parameters():
                param.requires_grad = True

            for param in self.base_model.classifier.parameters():
                param.requires_grad = True

        elif model_name == 'bert':
            self.base_model= BertForSequenceClassification.from_pretrained('bert-base-uncased')

            for param in self.base_model.base_model.parameters():
                param.requires_grad = False

            for param in self.base_model.base_model.encoder.layer[-2:].parameters():
                param.requires_grad = True

            for param in self.base_model.classifier.parameters():
                param.requires_grad = True
        
    
    def replicate_data(self, df, target_rows):
        while len(df) < target_rows:
            df = pd.concat([df, df])
        return df[:target_rows]
    
    
    def tokenize_data(self, data, tokenizer):
        tokenized = tokenizer.batch_encode_plus(
            data,
            truncation=True,
            padding=True,
            return_token_type_ids=False,
            return_attention_mask=True,
            return_tensors='pt'
        )
        return tokenized
    
    def data_split(self, df):
        unique_values_sample = df.drop_duplicates(subset=['target'])
        remaining_df = df[~df.index.isin(unique_values_sample.index)]
        remaining_train_df, test_df = train_test_split(remaining_df, test_size=0.2, random_state=42)
        train_df = pd.concat([remaining_train_df, unique_values_sample])
        test_df =pd.concat([test_df, unique_values_sample])
        return train_df, test_df
    
    def train(self):
        classes = []
        accuracies = []
        f1_scores = []
        models = []
        classifiers = []
        label_encoders =[]

        logger.info(f"INITIATING TRAINING FOR {self.model_name} MODEL")
        for i in range(len(self.dfs)):
            logger.info(f"TRAINING FOR DATAFRAME {i+1} of {len(self.dfs)}")
            current_df = self.dfs[i]
            if len(current_df) < 10:
                current_df = self.replicate_data(current_df, 50).reset_index(drop=True)
            
            train_df, test_df = self.data_split(current_df)
            label_encoder = LabelEncoder()
            train_labels = label_encoder.fit_transform(train_df['target'])
            test_labels = label_encoder.transform(test_df['target'])
            
            
            
            if self.model_name == 'distil-bert':
                model = DistilBertForSequenceClassification.from_pretrained('distilbert-base-uncased',num_labels=len(label_encoder.classes_), state_dict=self.base_model.state_dict(), ignore_mismatched_sizes=True)
                tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')

                for param in model.distilbert.parameters():
                    param.requires_grad = False

                for param in model.distilbert.transformer.layer[-2:].parameters():
                    param.requires_grad = True

                for param in model.classifier.parameters():
                    param.requires_grad = True

            elif self.model_name == 'roberta':
                model = XLMRobertaForSequenceClassification.from_pretrained('xlm-roberta-base', num_labels=len(label_encoder.classes_), state_dict=self.base_model.state_dict(), ignore_mismatched_sizes=True)
                tokenizer = XLMRobertaTokenizer.from_pretrained('xlm-roberta-base')
                for param in model.roberta.parameters():
                    param.requires_grad = False

                for param in model.roberta.encoder.layer[-2:].parameters():
                    param.requires_grad = True

                for param in model.classifier.parameters():
                    param.requires_grad = True
        
            elif self.model_name == 'bert':
                model = BertForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=len(label_encoder.classes_), state_dict=self.base_model.state_dict(), ignore_mismatched_sizes=True)
                tokenizer = BertTokenizer.from_pretrained('bert-base-uncased') 
                
                for param in model.base_model.parameters():
                    param.requires_grad = False
                    
                for param in model.base_model.encoder.layer[-2:].parameters():
                    param.requires_grad = True
                
                for param in model.classifier.parameters():
                    param.requires_grad = True
                
            train_encodings = self.tokenize_data(train_df['input'].tolist(), tokenizer)
            test_encodings = self.tokenize_data(test_df['input'].tolist(), tokenizer)
            
            train_dataset = CustomDataset(train_encodings, train_labels)
            test_dataset = CustomDataset(test_encodings, test_labels)
                                 
            training_args = TrainingArguments(
                output_dir= 'tmp',
                num_train_epochs=4,
                per_device_train_batch_size=16,
                per_device_eval_batch_size=16,
                logging_dir='./logs',
                logging_steps=100,
                eval_strategy='epoch',
                disable_tqdm=False
            )

            trainer = Trainer(
                model=model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=test_dataset,
                compute_metrics=lambda eval_pred: {"accuracy": accuracy_score(eval_pred.label_ids, eval_pred.predictions.argmax(axis=1))}
            )
            
            trainer.train()
            if self.model_name == 'distil-bert':
                models.append(model.distilbert.transformer.layer[-2:].state_dict())
            elif self.model_name == 'roberta':
                models.append(model.roberta.encoder.layer[-2:].state_dict())
            elif self.model_name == 'bert':
                models.append(model.base_model.encoder.layer[-2:].state_dict())
            
          
            classifiers.append(model.classifier.state_dict())
            predictions, labels, _ = trainer.predict(test_dataset)
            predictions = predictions.argmax(axis=-1)
            report = classification_report(labels, predictions, target_names=label_encoder.classes_ ,output_dict=True, zero_division=0)
            for cls in label_encoder.classes_:
                classes.append(cls)
                accuracies.append(report[cls]['precision'])
                f1_scores.append(report[cls]['f1-score'])
            
            label_encoders.append(label_encoder)
            shutil.rmtree('tmp')

        basic_model = self.base_model.state_dict()
        metrics = (classes, accuracies, f1_scores)
        return metrics, models, classifiers, label_encoders, basic_model
    
        