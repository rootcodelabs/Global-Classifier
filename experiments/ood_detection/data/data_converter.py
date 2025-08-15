#!/usr/bin/env python3
"""
CSV Conversion Script for OOD Detection Framework

This script converts CSV files with turn-by-turn conversation data to the format
required by the OOD detection framework.

Input format:
conversation_id | turn | speaker | text | agency

Output format:
conversation | agency

Usage:
    python convert_csv.py input.csv output.csv [--format-style bot_prefix]
"""

import pandas as pd
import argparse
import sys
import os
from typing import List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert turn-by-turn conversation CSV to OOD detection format"
    )

    parser.add_argument(
        "input_file",
        type=str,
        help="Path to input CSV file with turn-by-turn conversations",
    )

    parser.add_argument(
        "output_file", type=str, help="Path to output CSV file in OOD detection format"
    )

    parser.add_argument(
        "--format-style",
        type=str,
        choices=["bot_prefix", "speaker_prefix", "clean"],
        default="bot_prefix",
        help="How to format the conversation text (default: bot_prefix)",
    )

    parser.add_argument(
        "--speaker-mapping",
        type=str,
        nargs=2,
        metavar=("USER_SPEAKER", "BOT_SPEAKER"),
        default=["user", "bot"],
        help="Mapping for speaker names (default: user bot)",
    )

    parser.add_argument(
        "--exclude-conversations",
        type=str,
        nargs="*",
        help="List of conversation IDs to exclude from conversion",
    )

    parser.add_argument(
        "--min-turns",
        type=int,
        default=2,
        help="Minimum number of turns required for a conversation (default: 2)",
    )

    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Maximum number of turns to include per conversation",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


def load_and_validate_data(input_file: str) -> pd.DataFrame:
    """
    Load CSV data and validate required columns.

    Args:
        input_file: Path to input CSV file

    Returns:
        DataFrame with validated data

    Raises:
        ValueError: If required columns are missing
        FileNotFoundError: If input file doesn't exist
    """
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    logger.info(f"Loading data from {input_file}")
    df = pd.read_csv(input_file)

    # Check required columns
    required_columns = ["conversation_id", "turn", "speaker", "text", "agency"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    logger.info(f"Loaded {len(df)} rows with columns: {list(df.columns)}")

    # Basic data validation
    null_counts = df[required_columns].isnull().sum()
    if null_counts.any():
        logger.warning("Found null values:")
        for col, count in null_counts.items():
            if count > 0:
                logger.warning(f"  {col}: {count} null values")

    return df


def clean_and_filter_data(
    df: pd.DataFrame,
    exclude_conversations: Optional[List[str]] = None,
    min_turns: int = 2,
    max_turns: Optional[int] = None,
) -> pd.DataFrame:
    """
    Clean and filter the conversation data.

    Args:
        df: Input DataFrame
        exclude_conversations: List of conversation IDs to exclude
        min_turns: Minimum number of turns required
        max_turns: Maximum number of turns per conversation

    Returns:
        Cleaned and filtered DataFrame
    """
    logger.info("Cleaning and filtering data...")

    # Remove rows with null values in critical columns
    df = df.dropna(subset=["conversation_id", "text", "agency"])

    # Exclude specific conversations if requested
    if exclude_conversations:
        logger.info(f"Excluding {len(exclude_conversations)} conversations")
        df = df[~df["conversation_id"].isin(exclude_conversations)]

    # Clean text data
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""]  # Remove empty text

    # Sort by conversation_id and turn
    df = df.sort_values(["conversation_id", "turn"])

    # Filter conversations by turn count
    conversation_turn_counts = df.groupby("conversation_id").size()

    if min_turns > 1:
        valid_conversations = conversation_turn_counts[
            conversation_turn_counts >= min_turns
        ].index
        df = df[df["conversation_id"].isin(valid_conversations)]
        logger.info(f"Filtered to conversations with at least {min_turns} turns")

    if max_turns:
        # Keep only the first max_turns for each conversation
        df = df.groupby("conversation_id").head(max_turns)
        logger.info(f"Limited conversations to maximum {max_turns} turns")

    logger.info(
        f"After filtering: {len(df)} rows, {df['conversation_id'].nunique()} conversations"
    )

    return df


def format_conversation_text(
    conversation_df: pd.DataFrame, format_style: str, speaker_mapping: List[str]
) -> str:
    """
    Format conversation turns into a single text string.

    Args:
        conversation_df: DataFrame containing turns for a single conversation
        format_style: How to format the conversation
        speaker_mapping: [user_speaker, bot_speaker] names

    Returns:
        Formatted conversation string
    """
    user_speaker, bot_speaker = speaker_mapping
    turns = []

    for _, row in conversation_df.iterrows():
        speaker = str(row["speaker"]).lower().strip()
        text = str(row["text"]).strip()

        if format_style == "bot_prefix":
            # Format: "User: text Bot: text"
            if speaker == user_speaker.lower():
                turns.append(f"User: {text}")
            elif speaker == bot_speaker.lower():
                turns.append(f"Bot: {text}")
            else:
                # Handle unknown speakers
                turns.append(f"{speaker.title()}: {text}")

        elif format_style == "speaker_prefix":
            # Format: "user: text bot: text"
            turns.append(f"{speaker}: {text}")

        elif format_style == "clean":
            # Format: just the text without speaker prefixes
            turns.append(text)

    return " ".join(turns)


def convert_conversations(
    df: pd.DataFrame,
    format_style: str = "bot_prefix",
    speaker_mapping: List[str] = ["user", "bot"],
) -> pd.DataFrame:
    """
    Convert turn-by-turn conversations to single-row format.

    Args:
        df: Input DataFrame with turn-by-turn data
        format_style: How to format conversations
        speaker_mapping: Speaker name mapping

    Returns:
        DataFrame with converted conversations
    """
    logger.info("Converting conversations...")

    converted_conversations = []

    # Group by conversation_id and agency
    grouped = df.groupby(["conversation_id", "agency"])

    for (conv_id, agency), group in grouped:
        # Sort by turn number
        group = group.sort_values("turn")

        # Format the conversation text
        conversation_text = format_conversation_text(
            group, format_style, speaker_mapping
        )

        converted_conversations.append(
            {
                "conversation": conversation_text,
                "agency": agency,
                "conversation_id": conv_id,  # Keep for reference
                "num_turns": len(group),
            }
        )

    result_df = pd.DataFrame(converted_conversations)
    logger.info(f"Converted {len(result_df)} conversations")

    return result_df


def save_output(df: pd.DataFrame, output_file: str, include_metadata: bool = False):
    """
    Save the converted data to output file.

    Args:
        df: Converted DataFrame
        output_file: Path to output file
        include_metadata: Whether to include metadata columns
    """
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Select columns for output
    if include_metadata:
        output_columns = ["conversation", "agency", "conversation_id", "num_turns"]
    else:
        output_columns = ["conversation", "agency"]

    # Save to CSV
    df[output_columns].to_csv(output_file, index=False)
    logger.info(f"Saved {len(df)} conversations to {output_file}")


def print_sample_conversions(df: pd.DataFrame, num_samples: int = 3):
    """Print sample conversions for verification."""
    logger.info(f"\nSample conversions (showing first {num_samples}):")
    logger.info("=" * 80)

    for i, row in df.head(num_samples).iterrows():
        logger.info(f"Conversation {i + 1}:")
        logger.info(f"Agency: {row['agency']}")
        logger.info(f"Text: {row['conversation'][:200]}...")
        logger.info(f"Turns: {row.get('num_turns', 'N/A')}")
        logger.info("-" * 40)


def generate_statistics(original_df: pd.DataFrame, converted_df: pd.DataFrame):
    """Generate and display conversion statistics."""
    logger.info("\nConversion Statistics:")
    logger.info("=" * 40)

    # Original data stats
    orig_conversations = original_df["conversation_id"].nunique()
    orig_turns = len(original_df)
    orig_agencies = original_df["agency"].nunique()

    logger.info("Original data:")
    logger.info(f"  Conversations: {orig_conversations}")
    logger.info(f"  Total turns: {orig_turns}")
    logger.info(f"  Unique agencies: {orig_agencies}")
    logger.info(
        f"  Average turns per conversation: {orig_turns / orig_conversations:.1f}"
    )

    # Converted data stats
    conv_conversations = len(converted_df)
    conv_agencies = converted_df["agency"].nunique()

    logger.info("\nConverted data:")
    logger.info(f"  Conversations: {conv_conversations}")
    logger.info(f"  Unique agencies: {conv_agencies}")

    if "num_turns" in converted_df.columns:
        avg_turns = converted_df["num_turns"].mean()
        logger.info(f"  Average turns per conversation: {avg_turns:.1f}")

    # Agency distribution
    logger.info("\nAgency distribution:")
    agency_counts = converted_df["agency"].value_counts()
    for agency, count in agency_counts.items():
        logger.info(f"  {agency}: {count}")


def main():
    """Main conversion function."""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Load and validate input data
        df = load_and_validate_data(args.input_file)

        # Clean and filter data
        df = clean_and_filter_data(
            df,
            exclude_conversations=args.exclude_conversations,
            min_turns=args.min_turns,
            max_turns=args.max_turns,
        )

        if len(df) == 0:
            logger.error("No data remaining after filtering!")
            sys.exit(1)

        # Convert conversations
        converted_df = convert_conversations(
            df, format_style=args.format_style, speaker_mapping=args.speaker_mapping
        )

        # Generate statistics
        generate_statistics(df, converted_df)

        # Show sample conversions
        if args.verbose:
            print_sample_conversions(converted_df)

        # Save output
        save_output(converted_df, args.output_file, include_metadata=args.verbose)

        logger.info("\nConversion completed successfully!")
        logger.info(f"Output saved to: {args.output_file}")

    except Exception as e:
        logger.error(f"Error during conversion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
