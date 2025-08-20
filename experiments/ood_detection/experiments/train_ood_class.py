"""
Training script for OOD as a class model.
"""

import os
import sys
import logging
import argparse
import tensorflow as tf
import numpy as np
import json
import time

from config.config import TRAINING_CONFIG, OODClassConfig
from data.data_loader import DataLoader
from models.ood_class_model import OODClassModel
from evaluation.metrics import OODMetrics
from evaluation.inference_metrics import InferenceMetrics
from utils.mlflow_logger import MLflowLogger
from utils.visualization import Visualizer


# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Train and evaluate OOD-as-class model"
    )

    parser.add_argument("--train-file", type=str, help="Path to training data")
    parser.add_argument("--dev-file", type=str, help="Path to validation data")
    parser.add_argument("--test-file", type=str, help="Path to test data")
    parser.add_argument("--ood-file", type=str, help="Path to OOD test data")

    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/ood_class",
        help="Directory to save outputs",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="models/ood_class",
        help="Directory to save model",
    )

    parser.add_argument(
        "--pretrained-model",
        type=str,
        default="xlm-roberta-base",
        help="Pretrained model name or path",
    )
    parser.add_argument(
        "--max-seq-length", type=int, default=512, help="Maximum sequence length"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for training and evaluation",
    )
    parser.add_argument(
        "--epochs", type=int, default=10, help="Number of training epochs"
    )
    parser.add_argument(
        "--learning-rate", type=float, default=2e-5, help="Learning rate"
    )

    parser.add_argument(
        "--synthetic-ood-ratio",
        type=float,
        default=0.2,
        help="Ratio of synthetic OOD examples to generate",
    )

    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--use-gpu", action="store_true", help="Whether to use GPU")

    parser.add_argument(
        "--mlflow-tracking-uri", type=str, default=None, help="MLflow tracking URI"
    )
    parser.add_argument(
        "--mlflow-experiment-name",
        type=str,
        default="ood_detection_ood_class",
        help="MLflow experiment name",
    )

    parser.add_argument(
        "--log-performance",
        action="store_true",
        help="Whether to log performance metrics",
    )

    return parser.parse_args()


def prepare_configs(args):
    """Prepare configurations based on command-line arguments."""
    # Create OOD class config
    ood_class_config = OODClassConfig(
        name="ood_class_model",
        model_type="ood_class",
        pretrained_model=args.pretrained_model,
        synthetic_ood_ratio=args.synthetic_ood_ratio,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        epochs=args.epochs,
        max_seq_length=args.max_seq_length,
        seed=args.seed,
    )

    # Create training config
    training_config = TRAINING_CONFIG
    training_config.train_file = args.train_file or training_config.train_file
    training_config.dev_file = args.dev_file or training_config.dev_file
    training_config.test_file = args.test_file or training_config.test_file
    training_config.ood_test_file = args.ood_file or training_config.ood_test_file
    training_config.output_dir = args.output_dir or training_config.output_dir
    training_config.mlflow_tracking_uri = (
        args.mlflow_tracking_uri or training_config.mlflow_tracking_uri
    )
    training_config.mlflow_experiment_name = (
        args.mlflow_experiment_name or training_config.mlflow_experiment_name
    )
    training_config.model_config = ood_class_config

    return training_config, ood_class_config


def train_and_evaluate(config, model_config, use_gpu=False, log_performance=False):
    """
    Train and evaluate the OOD-as-class model.

    Args:
        config: Training configuration
        model_config: Model configuration
        use_gpu: Whether to use GPU
        log_performance: Whether to log performance metrics

    Returns:
        results: Dictionary of evaluation results
    """
    # Set up directories
    os.makedirs(config.output_dir, exist_ok=True)
    model_dir = os.path.join(config.output_dir, "model")
    os.makedirs(model_dir, exist_ok=True)

    # Set random seed
    tf.random.set_seed(model_config.seed)
    np.random.seed(model_config.seed)

    # Set up MLflow logger
    mlflow_logger = MLflowLogger(
        experiment_name=config.mlflow_experiment_name,
        tracking_uri=config.mlflow_tracking_uri,
        model_dir=model_dir,
        artifact_dir=os.path.join(config.output_dir, "artifacts"),
    )

    # Start MLflow run
    random_id = np.random.default_rng(40).standard_normal()
    run_name = f"ood_class_{model_config.synthetic_ood_ratio}_{random_id:.4f}"
    mlflow_logger.start_run(run_name=run_name)

    # Log parameters
    mlflow_logger.log_params(
        {
            "model_type": model_config.model_type,
            "pretrained_model": model_config.pretrained_model,
            "synthetic_ood_ratio": model_config.synthetic_ood_ratio,
            "learning_rate": model_config.learning_rate,
            "batch_size": model_config.batch_size,
            "epochs": model_config.epochs,
            "max_seq_length": model_config.max_seq_length,
            "seed": model_config.seed,
        }
    )

    # Load data
    logger.info("Loading data...")
    data_loader = DataLoader(
        tokenizer_name=model_config.pretrained_model,
        max_seq_length=model_config.max_seq_length,
        batch_size=model_config.batch_size,
        seed=model_config.seed,
    )

    # Load regular training data first
    train_dataset, label_map, num_train_examples = data_loader.load_data(
        config.train_file, is_training=True
    )

    # Add OOD class to label map
    num_id_classes = len(label_map)
    label_map["OOD"] = num_id_classes

    # Create modified datasets with OOD class
    train_dataset_with_ood = data_loader.create_synthetic_ood(
        train_dataset, label_map, ratio=model_config.synthetic_ood_ratio
    )

    # Load validation and test data
    dev_dataset, _, num_dev_examples = data_loader.load_data(
        config.dev_file, is_training=False, add_ood_class=True
    )

    test_dataset, _, num_test_examples = data_loader.load_data(
        config.test_file, is_training=False, add_ood_class=True
    )

    # Load OOD test data if available
    if config.ood_test_file:
        ood_test_dataset = data_loader.load_ood_data(config.ood_test_file, label_map)
    else:
        ood_test_dataset = None

    # Number of classes including OOD
    num_labels = len(label_map)

    # Log data information
    mlflow_logger.log_params(
        {
            "num_train_examples": num_train_examples,
            "num_dev_examples": num_dev_examples,
            "num_test_examples": num_test_examples,
            "num_id_classes": num_id_classes,
            "num_labels": num_labels,
            "label_map": label_map,
        }
    )

    # Create model
    logger.info("Creating OOD-as-class model...")
    model = OODClassModel(
        pretrained_model=model_config.pretrained_model,
        num_labels=num_id_classes,  # Original number of classes, OOD will be added
        hidden_dims=[768],  # Add a hidden layer
        dropout_rate=0.1,
        synthetic_ood_ratio=model_config.synthetic_ood_ratio,
    )
    # Compile model
    optimizer = tf.keras.optimizers.Adam(learning_rate=model_config.learning_rate)
    loss = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
    metrics = [tf.keras.metrics.SparseCategoricalAccuracy(name="accuracy")]
    model.compile(optimizer=optimizer, loss=loss, metrics=metrics)
    # Create callbacks
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(model_dir, "checkpoint.keras"),
            save_best_only=True,
            monitor="val_accuracy",
            mode="max",
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy", patience=3, restore_best_weights=True
        ),
    ]
    # Train model
    logger.info("Training model...")
    training_start_time = time.time()
    history = model.fit(
        train_dataset_with_ood,
        validation_data=dev_dataset,
        epochs=model_config.epochs,
        callbacks=callbacks,
        verbose=1,
    )
    training_time = time.time() - training_start_time
    # Log training metrics
    for epoch, (loss, accuracy, val_loss, val_accuracy) in enumerate(
        zip(
            history.history["loss"],
            history.history["accuracy"],
            history.history["val_loss"],
            history.history["val_accuracy"],
        )
    ):
        mlflow_logger.log_metrics(
            {
                "train_loss": loss,
                "train_accuracy": accuracy,
                "val_loss": val_loss,
                "val_accuracy": val_accuracy,
            },
            step=epoch,
        )
    # Log training history plot
    visualizer = Visualizer(
        output_dir=os.path.join(config.output_dir, "visualizations")
    )
    # Evaluate on test set
    logger.info("Evaluating on test set...")
    evaluation_results = {}
    # Get predictions and uncertainties
    id_predictions = []
    id_uncertainties = []
    id_labels_list = []
    for batch in test_dataset:
        inputs, labels = batch
        preds, uncertainties = model.predict_with_uncertainty(inputs)
        id_predictions.extend(preds.numpy())
        id_uncertainties.extend(uncertainties.numpy())
        id_labels_list.extend(labels.numpy())
    id_predictions = np.array(id_predictions)
    id_uncertainties = np.array(id_uncertainties)
    id_labels = np.array(id_labels_list)
    # Evaluate OOD detection
    if ood_test_dataset:
        logger.info("Evaluating OOD detection...")
        ood_predictions = []
        ood_uncertainties = []
        for batch in ood_test_dataset:
            inputs, _ = batch
            preds, uncertainties = model.predict_with_uncertainty(inputs)
            ood_predictions.extend(preds.numpy())
            ood_uncertainties.extend(uncertainties.numpy())
        ood_predictions = np.array(ood_predictions)
        ood_uncertainties = np.array(ood_uncertainties)
        # Compute OOD detection metrics
        ood_metrics = OODMetrics()
        metrics_dict = ood_metrics.compute_metrics(
            id_uncertainties=id_uncertainties,
            ood_uncertainties=ood_uncertainties,
            id_labels=id_labels,
            id_predictions=id_predictions,
        )
        evaluation_results.update(metrics_dict)
        # Log OOD detection metrics
        mlflow_logger.log_metrics(metrics_dict)
        # Create and log visualizations
        roc_fig = visualizer.plot_roc_curve(
            id_uncertainties=id_uncertainties,
            ood_uncertainties=ood_uncertainties,
            model_name="OOD as Class",
        )
        mlflow_logger.log_figure(roc_fig, "visualizations/roc_curve.png")
        pr_fig = visualizer.plot_pr_curve(
            id_uncertainties=id_uncertainties,
            ood_uncertainties=ood_uncertainties,
            model_name="OOD as Class",
        )
        mlflow_logger.log_figure(pr_fig, "visualizations/pr_curve.png")
        dist_fig = visualizer.plot_score_distributions(
            id_uncertainties=id_uncertainties,
            ood_uncertainties=ood_uncertainties,
            model_name="OOD as Class",
        )
        mlflow_logger.log_figure(dist_fig, "visualizations/score_distributions.png")
        # Plot threshold impact
        threshold_fig = visualizer.plot_uncertainty_threshold_impact(
            id_uncertainties=id_uncertainties,
            ood_uncertainties=ood_uncertainties,
            model_name="OOD as Class",
        )
        mlflow_logger.log_figure(threshold_fig, "visualizations/threshold_impact.png")
    # Plot confusion matrix
    # Only include original classes, not OOD class
    class_names = [
        k
        for k, v in sorted(label_map.items(), key=lambda x: x[1])
        if k != "OOD" and v < num_id_classes
    ]
    # Filter labels and predictions to include only ID examples
    id_mask = id_labels < num_id_classes
    id_only_labels = id_labels[id_mask]
    id_only_predictions = id_predictions[id_mask]
    cm_fig = visualizer.plot_confusion_matrix(
        y_true=id_only_labels,
        y_pred=id_only_predictions,
        class_names=class_names,
        model_name="OOD as Class",
    )
    mlflow_logger.log_figure(cm_fig, "visualizations/confusion_matrix.png")
    # Log performance metrics if requested
    if log_performance:
        logger.info("Measuring inference performance...")
        inference_metrics = InferenceMetrics(use_gpu=use_gpu)
        # Get a sample batch
        for batch in test_dataset.take(1):
            sample_inputs, _ = batch
            break
        # Measure inference time
        inference_results = inference_metrics.measure_inference_time(
            model=model,
            inputs=sample_inputs,
            batch_sizes=[1, 4, 8, 16, 32],
            num_runs=50,
            warmup_runs=10,
            use_uncertainty=True,
        )
        # Log inference metrics
        for batch_size, metrics in inference_results.items():
            mlflow_logger.log_metrics(
                {
                    f"inference_time_bs{batch_size}_mean": metrics["mean"],
                    f"inference_time_bs{batch_size}_p95": metrics["p95"],
                    f"throughput_bs{batch_size}": metrics["throughput"],
                }
            )
        # Generate and log inference time plot
        time_fig = inference_metrics.plot_inference_times(inference_results)
        mlflow_logger.log_figure(time_fig, "visualizations/inference_times.png")
        # Add inference metrics to evaluation results
        evaluation_results["inference_performance"] = inference_results
        evaluation_results["training_time"] = training_time
    # Save model
    logger.info("Saving model...")
    model_path = os.path.join(model_dir, "final_model.keras")
    model.save(model_path)
    # Log model to MLflow
    # Log model summary
    mlflow_logger.log_model_summary(model)
    # Save evaluation results
    results_path = os.path.join(config.output_dir, "evaluation_results.json")
    with open(results_path, "w") as f:
        json.dump(evaluation_results, f, indent=2)
    # Log evaluation results as artifact
    mlflow_logger.log_artifact(results_path)
    # End MLflow run
    mlflow_logger.end_run()
    return evaluation_results


def main():
    """Main function."""
    # Parse arguments
    args = parse_args()

    # Prepare configurations
    training_config, model_config = prepare_configs(args)

    # Set GPU usage
    if args.use_gpu:
        # Check if GPU is available
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            try:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"Using GPU: {len(gpus)} GPU(s) available")
            except RuntimeError as e:
                logger.error(f"Error setting GPU memory growth: {e}")
        else:
            logger.warning("No GPU found. Using CPU instead.")
    else:
        # Disable GPU
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        logger.info("Using CPU as requested")

    # Train and evaluate model
    results = train_and_evaluate(
        config=training_config,
        model_config=model_config,
        use_gpu=args.use_gpu,
        log_performance=args.log_performance,
    )

    logger.info("Completed OOD-as-class training and evaluation")

    if "auroc" in results:
        logger.info(f"AUROC: {results['auroc']:.4f}")
    if "accuracy" in results:
        logger.info(f"Accuracy: {results['accuracy']:.4f}")
    if "fpr_at_95_tpr" in results:
        logger.info(f"FPR@95%TPR: {results['fpr_at_95_tpr']:.4f}")


if __name__ == "__main__":
    main()
