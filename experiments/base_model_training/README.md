# Agency Classification Model Project

Training folder contains code and resources for evaluating transformer-based models (BERT, RoBERTa, XLM-RoBERTa) for classifying agency-based conversations. 

## Project Structure

```
project_root/
├── data/
│   ├── raw/                   # Raw conversation data
│   ├── processed/             # Processed and split datasets
│   └── splits/                # Train/val/test data splits
├── models/
│   └── saved/                 # Saved model checkpoints
├── scripts/
│   ├── train.py               # Training script for transformer models
│   ├── evaluate.py            # Evaluation script for model assessment
│   ├── inference.py           # Inference performance benchmarking
│   ├── utils.py               # Utility functions used across scripts
│   ├── mlflow_log.py          # MLflow logging and experiment tracking
│   └── create_datasets.py     # Dataset preparation script
├── experiments/
│   ├── bert/                  # BERT experiment configurations and results
│   ├── roberta/               # RoBERTa experiment configurations and results
│   └── xlm/                   # XLM-RoBERTa experiment configurations and results
├── mlruns/                    # MLflow tracking directory
├── ANALYSIS.md                # Comprehensive analysis of model performance
├── DECISION.md                # Final decision on model selection
├── requirements.txt           # Project dependencies
└── README.md                  # This file
```


## Models

We evaluate the following transformer-based models:

- **BERT** (`bert-base-uncased`): A bidirectional transformer pre-trained on English text.
- **RoBERTa** (`roberta-base`): An optimized version of BERT with improved training methodology.
- **XLM-RoBERTa** (`xlm-roberta-base`): A multilingual version of RoBERTa trained on 100 languages.


