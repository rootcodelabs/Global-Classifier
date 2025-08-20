import os
import sys
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import json
import argparse
from loguru import logger
import matplotlib.pyplot as plt
import seaborn as sns

logger.remove()
# add stout handler
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


def load_raw_data(input_file):
    """
    Load and process the raw conversation data.

    Args:
        input_file: Path to the raw data file

    Returns:
        DataFrame with processed conversation data
    """
    logger.info(f"Loading data from {input_file}")

    if input_file.endswith(".csv"):
        df = pd.read_csv(input_file)
    else:
        raise ValueError(f"Unsupported file format: {input_file}")

    # Check required columns
    required_cols = ["turn", "speaker", "text", "agency"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in data")

    return df


def process_conversations(df):
    """
    Process the raw data into conversation-level samples for classification.
    Each conversation (all turns together) becomes one training instance.

    Args:
        df: DataFrame with raw conversation data

    Returns:
        DataFrame with one row per conversation
    """
    logger.info("Processing conversations...")

    # Group by conversation_id
    conversations = []
    for conv_id, group in df.groupby("conversation_id"):
        agency = group["agency"].iloc[0]

        # Format the conversation as a string with speaker labels
        conversation_text = []
        for _, row in group.iterrows():
            conversation_text.append(f"{row['speaker']}: {row['text']}")

        full_text = "\n".join(conversation_text)

        conversations.append(
            {
                "conversation_id": conv_id,
                "text": full_text,
                "agency": agency,
                "num_turns": len(group),
            }
        )

    conversation_df = pd.DataFrame(conversations)

    # Print statistics
    logger.info(
        f"Created {len(conversation_df)} conversation instances from {len(df)} turns"
    )
    logger.info("Conversations per agency:")
    agency_counts = conversation_df["agency"].value_counts()
    for agency, count in agency_counts.items():
        logger.info(f"  {agency}: {count} conversations")

    return conversation_df


def split_dataset(df, test_size=0.2, val_size=0.1, random_state=42):
    """
    Split the dataset into training, validation, and test sets.

    Args:
        df: DataFrame with processed conversation data
        test_size: Proportion for the test set
        val_size: Proportion for the validation set
        random_state: Random seed for reproducibility

    Returns:
        train_df, val_df, test_df: Split DataFrames
    """
    # Check if we can use stratification (at least 2 samples per class)
    class_counts = df["agency"].value_counts()
    use_stratify = all(count >= 2 for count in class_counts)

    if not use_stratify:
        logger.warning(
            "Warning: Some classes have fewer than 2 samples. Stratification disabled."
        )
        stratify = None
    else:
        stratify = df["agency"]

    # First split: train+val vs test
    train_val_df, test_df = train_test_split(
        df, test_size=test_size, random_state=random_state, stratify=stratify
    )

    # For the second split, check again if we can stratify
    if use_stratify:
        val_class_counts = train_val_df["agency"].value_counts()
        use_val_stratify = all(count >= 2 for count in val_class_counts)
        val_stratify = train_val_df["agency"] if use_val_stratify else None

        if not use_val_stratify:
            logger.warning(
                "Warning: After first split, some classes have too few samples for stratified validation split."
            )
    else:
        val_stratify = None

    # Second split: train vs val (calculated from remaining data)
    val_ratio = val_size / (1 - test_size)

    train_df, val_df = train_test_split(
        train_val_df,
        test_size=val_ratio,
        random_state=random_state,
        stratify=val_stratify,
    )

    logger.info(
        f"Dataset splits: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}"
    )

    # Print class distribution in each split
    logger.info("\nClass distribution:")
    for split_name, split_df in [
        ("Train", train_df),
        ("Val", val_df),
        ("Test", test_df),
    ]:
        class_dist = split_df["agency"].value_counts().to_dict()
        logger.info(f"  {split_name}: {class_dist}")

    return train_df, val_df, test_df


def analyze_dataset(df, output_dir):
    """
    Analyze the dataset and save visualizations.

    Args:
        df: DataFrame with processed conversation data
        output_dir: Directory to save analysis files
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Class distribution
    plt.figure(figsize=(10, 6))
    sns.countplot(y="agency", data=df)
    plt.title("Distribution of Agencies")
    plt.xlabel("Count")
    plt.ylabel("Agency")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "agency_distribution.png"))
    plt.close()

    # 2. Number of turns distribution
    plt.figure(figsize=(10, 6))
    sns.countplot(x="num_turns", data=df)
    plt.title("Distribution of Conversation Length (Turns)")
    plt.xlabel("Number of Turns")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "turns_distribution.png"))
    plt.close()

    # 3. Text length distribution
    df["text_length"] = df["text"].apply(len)
    plt.figure(figsize=(10, 6))
    sns.histplot(data=df, x="text_length", bins=20)
    plt.title("Distribution of Text Length")
    plt.xlabel("Number of Characters")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "text_length_distribution.png"))
    plt.close()

    # 4. Summary statistics as JSON
    stats = {
        "num_conversations": int(len(df)),
        "conversations_per_agency": {
            k: int(v) for k, v in df["agency"].value_counts().to_dict().items()
        },
        "avg_turns": float(df["num_turns"].mean()),
        "min_turns": int(df["num_turns"].min()),
        "max_turns": int(df["num_turns"].max()),
        "avg_text_length": float(df["text_length"].mean()),
        "min_text_length": int(df["text_length"].min()),
        "max_text_length": int(df["text_length"].max()),
    }

    with open(os.path.join(output_dir, "dataset_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    # 5. Create a summary markdown file
    with open(os.path.join(output_dir, "dataset_summary.md"), "w") as f:
        f.write("# Synthetic Dataset Summary\n\n")

        f.write("## Dataset Statistics\n\n")
        f.write(f"- Total conversations: {stats['num_conversations']}\n")
        f.write(f"- Average turns per conversation: {stats['avg_turns']:.2f}\n")
        f.write(f"- Average text length: {stats['avg_text_length']:.2f} characters\n\n")

        f.write("## Agency Distribution\n\n")
        f.write("| Agency | Count | Percentage |\n")
        f.write("|--------|-------|------------|\n")

        for agency, count in stats["conversations_per_agency"].items():
            percentage = (count / stats["num_conversations"]) * 100
            f.write(f"| {agency} | {count} | {percentage:.2f}% |\n")


def save_datasets(train_df, val_df, test_df, output_dir):
    """
    Save the datasets to CSV files.

    Args:
        train_df, val_df, test_df: DataFrames for each split
        output_dir: Directory to save the files
    """
    os.makedirs(output_dir, exist_ok=True)

    # Ensure we only keep necessary columns
    columns = ["text", "agency"]

    train_df[columns].to_csv(os.path.join(output_dir, "train.csv"), index=False)
    val_df[columns].to_csv(os.path.join(output_dir, "val.csv"), index=False)
    test_df[columns].to_csv(os.path.join(output_dir, "test.csv"), index=False)

    print(f"Datasets saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare datasets for agency classification"
    )
    parser.add_argument(
        "--input_file",
        type=str,
        default="data/raw/synthetic_conversations.csv",
        help="Path to the raw conversation data",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="data/processed",
        help="Directory to save the processed datasets",
    )
    parser.add_argument(
        "--analysis_dir",
        type=str,
        default="data/analysis",
        help="Directory to save dataset analysis",
    )
    parser.add_argument(
        "--test_size",
        type=float,
        default=0.2,
        help="Proportion of data for the test set",
    )
    parser.add_argument(
        "--val_size",
        type=float,
        default=0.1,
        help="Proportion of data for the validation set",
    )
    parser.add_argument(
        "--augment",
        action="store_true",
        help="Create augmented data for additional synthetic examples",
    )
    parser.add_argument(
        "--augment_factor",
        type=int,
        default=2,
        help="How many augmented examples per original",
    )
    parser.add_argument(
        "--random_seed", type=int, default=42, help="Random seed for reproducibility"
    )

    args = parser.parse_args()

    # Set random seed
    np.random.seed(args.random_seed)

    # Load and process data
    raw_df = load_raw_data(args.input_file)
    conversation_df = process_conversations(raw_df)

    # Analyze dataset
    analyze_dataset(conversation_df, args.analysis_dir)

    # Split dataset
    train_df, val_df, test_df = split_dataset(
        conversation_df,
        test_size=args.test_size,
        val_size=args.val_size,
        random_state=args.random_seed,
    )

    # Save datasets
    save_datasets(train_df, val_df, test_df, args.output_dir)

    logger.info("Dataset preparation complete!")


if __name__ == "__main__":
    main()
