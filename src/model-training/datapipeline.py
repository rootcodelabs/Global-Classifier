import pandas as pd
import requests
from constants import (
    DATA_DOWNLOAD_ENDPOINT,
    GET_DATASET_METADATA_ENDPOINT,
)
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


class DataPipeline:
    def __init__(self, dg_id, cookie):
        logger.info(f"DOWNLOADING DATASET WITH DGID - {dg_id}")

        cookies = {"customJwtCookie": cookie}

        # Download dataset
        response = requests.get(
            DATA_DOWNLOAD_ENDPOINT, params={"dgId": dg_id}, cookies=cookies
        )

        if response.status_code == 200:
            logger.info("DATA DOWNLOAD SUCCESSFUL")
            data = response.json()
            df = pd.DataFrame(data)

            # Remove rowId if it exists
            if "rowId" in df.columns:
                df = df.drop("rowId", axis=1)

            self.df = df
            logger.info(f"Downloaded dataset with {len(df)} samples")
            logger.info(f"Dataset columns: {list(df.columns)}")
        else:
            logger.error(
                f"DATA DOWNLOAD FAILED WITH ERROR CODE: {response.status_code}"
            )
            logger.error(f"RESPONSE: {response.text}")
            raise RuntimeError(f"ERROR RESPONSE {response.text}")

        # Get dataset metadata
        logger.info("****** Getting Dataset Metadata ******")
        logger.info(f"Endpoint: {GET_DATASET_METADATA_ENDPOINT}")

        response_hierarchy = requests.get(
            GET_DATASET_METADATA_ENDPOINT, params={"groupId": dg_id}, cookies=cookies
        )

        if response_hierarchy.status_code == 200:
            logger.info("DATASET METADATA RETRIEVAL SUCCESSFUL")
            hierarchy = response_hierarchy.json()
            self.hierarchy = hierarchy["response"]["data"][0]
            logger.info(
                f"Retrieved metadata for dataset: {self.hierarchy.get('name', 'Unknown')}"
            )
        else:
            logger.error(
                f"DATASET METADATA RETRIEVAL FAILED: {response_hierarchy.status_code}"
            )
            logger.error(f"RESPONSE: {response_hierarchy.text}")
            raise RuntimeError(f"ERROR RESPONSE\n {response_hierarchy.text}")

    def extract_input_columns(self):
        """Extract input columns from validation rules"""
        validation_rules = self.hierarchy["validationCriteria"]["validationRules"]
        input_columns = [
            key for key, value in validation_rules.items() if not value["isDataClass"]
        ]
        logger.info(f"Input columns identified: {input_columns}")
        return input_columns

    def extract_target_column(self):
        """Extract the target column from validation rules"""
        validation_rules = self.hierarchy["validationCriteria"]["validationRules"]
        target_columns = [
            key for key, value in validation_rules.items() if value["isDataClass"]
        ]

        if not target_columns:
            logger.error("No target column found in validation rules")
            raise ValueError("No target column found in validation rules")

        target_column = target_columns[0]
        logger.info(f"Target column identified: {target_column}")
        return target_column

    def models_and_filters(self):
        """
        Create models and filters for flat classification.
        This maintains compatibility with the original hierarchical interface
        but returns simplified structures for flat classification.
        """
        target_column = self.extract_target_column()
        unique_classes = sorted(self.df[target_column].unique().tolist())

        # Create simple model structure for compatibility
        models = [{1: unique_classes}]  # Single model with all classes
        filters = [unique_classes]  # Single filter with all classes

        logger.info("Flat classification setup:")
        logger.info(f"  Target column: {target_column}")
        logger.info(f"  Classes ({len(unique_classes)}): {unique_classes}")
        logger.info(
            f"  Class distribution: {self.df[target_column].value_counts().to_dict()}"
        )

        return models, filters

    def create_dataframes(self):
        """Create dataframes for flat classification"""
        logger.info("CREATING DATAFRAME FOR FLAT CLASSIFICATION")

        try:
            input_columns = self.extract_input_columns()
            target_column = self.extract_target_column()

            df = self.df.copy()

            # Create input text by combining input columns
            if len(input_columns) == 1:
                # Single input column - use directly
                input_col = input_columns[0]
                df["input"] = df[input_col].astype(str)
                logger.info(f"Using single input column: {input_col}")
            else:
                # Multiple input columns - combine them
                df["input"] = df[input_columns].apply(
                    lambda row: " ".join(row.dropna().astype(str)), axis=1
                )
                logger.info(f"Combined input columns: {input_columns}")

            # Set target column
            df = df.rename(columns={target_column: "target"})

            # Keep only input and target columns, remove any NaN values
            df = df[["input", "target"]].dropna()

            # Validate the data
            if len(df) == 0:
                raise ValueError("No valid data samples after preprocessing")

            # Check for empty inputs
            empty_inputs = df[df["input"].str.strip() == ""].shape[0]
            if empty_inputs > 0:
                logger.warning(
                    f"Found {empty_inputs} empty input samples, removing them"
                )
                df = df[df["input"].str.strip() != ""]

            # Final validation
            if len(df) == 0:
                raise ValueError("No valid data samples after cleaning")

            unique_classes = df["target"].unique()
            class_counts = df["target"].value_counts()

            logger.info("DATAFRAME CREATED SUCCESSFULLY:")
            logger.info(f"  Total samples: {len(df)}")
            logger.info(f"  Unique classes: {len(unique_classes)}")
            logger.info(f"  Class distribution: {class_counts.to_dict()}")
            logger.info(
                f"  Sample input (first 100 chars): {df['input'].iloc[0][:100]}..."
            )

            # Check for class imbalance
            min_class_size = class_counts.min()
            max_class_size = class_counts.max()

            if min_class_size < 5:
                logger.warning(
                    f"Some classes have very few samples (min: {min_class_size})"
                )

            if max_class_size / min_class_size > 10:
                logger.warning(
                    f"Significant class imbalance detected (ratio: {max_class_size / min_class_size:.1f})"
                )

            return [
                df
            ]  # Return as list for compatibility with multi-dataframe training

        except Exception as e:
            logger.error(f"ERROR CREATING DATAFRAME: {e}")
            logger.error(f"Available columns: {list(self.df.columns)}")
            logger.error(f"DataFrame shape: {self.df.shape}")
            logger.error(f"DataFrame info: {self.df.info()}")
            raise

    def get_data_statistics(self):
        """Get detailed statistics about the dataset"""
        try:
            target_column = self.extract_target_column()
            input_columns = self.extract_input_columns()

            stats = {
                "total_samples": len(self.df),
                "input_columns": input_columns,
                "target_column": target_column,
                "unique_classes": self.df[target_column].unique().tolist(),
                "class_distribution": self.df[target_column].value_counts().to_dict(),
                "missing_values": self.df.isnull().sum().to_dict(),
                "data_types": self.df.dtypes.to_dict(),
            }

            # Add text statistics for input columns
            for col in input_columns:
                if col in self.df.columns:
                    text_lengths = self.df[col].astype(str).str.len()
                    stats[f"{col}_text_stats"] = {
                        "avg_length": text_lengths.mean(),
                        "min_length": text_lengths.min(),
                        "max_length": text_lengths.max(),
                        "median_length": text_lengths.median(),
                    }

            return stats

        except Exception as e:
            logger.error(f"Error getting data statistics: {e}")
            return {}

    def validate_data_quality(self):
        """Validate data quality and return issues"""
        issues = []

        try:
            target_column = self.extract_target_column()
            input_columns = self.extract_input_columns()

            # Check for missing target values
            missing_targets = self.df[target_column].isnull().sum()
            if missing_targets > 0:
                issues.append(f"Missing target values: {missing_targets}")

            # Check for missing input values
            for col in input_columns:
                if col in self.df.columns:
                    missing_inputs = self.df[col].isnull().sum()
                    if missing_inputs > 0:
                        issues.append(f"Missing values in {col}: {missing_inputs}")

            # Check for empty strings in input columns
            for col in input_columns:
                if col in self.df.columns:
                    empty_strings = (self.df[col].astype(str).str.strip() == "").sum()
                    if empty_strings > 0:
                        issues.append(f"Empty strings in {col}: {empty_strings}")

            # Check class distribution
            class_counts = self.df[target_column].value_counts()
            min_class_size = class_counts.min()
            if min_class_size < 3:
                issues.append(f"Classes with very few samples (min: {min_class_size})")

            # Check for duplicate samples
            if len(input_columns) == 1:
                duplicates = self.df.duplicated(
                    subset=input_columns + [target_column]
                ).sum()
                if duplicates > 0:
                    issues.append(f"Duplicate samples: {duplicates}")

            if issues:
                logger.warning(f"Data quality issues found: {issues}")
            else:
                logger.info("Data quality validation passed")

            return issues

        except Exception as e:
            logger.error(f"Error validating data quality: {e}")
            return [f"Validation error: {str(e)}"]
