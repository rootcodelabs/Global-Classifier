# Agency Classification Model Decision

## Summary

This document outlines our final decision regarding the selection of base models for the agency classification task. After thorough evaluation of EstBERT and XLM-RoBERTa on synthetic agency conversation data, we have determined the most suitable model(s) for implementation.

## Evaluation Criteria

Our model selection was based on these key criteria:

1. **Classification Performance**: Accuracy, precision, recall, F1 score, and ROC/AUC metrics
2. **Inference Performance**: Response time, throughput, and resource efficiency
3. **CPU Compatibility**: Performance on CPU-only environments
4. **Multilingual Capability**: Ability to handle Estonian language content
5. **Implementation Complexity**: Ease of deployment and maintenance

## Decision

Based on comprehensive evaluations documented in ANALYSIS.md, we have decided to use:

**XLM-RoBERTa** as our primary classifier model.

### Rationale

* **Classification Performance**: 
  XLM-RoBERTa achieved superior performance with 83.33% accuracy, 82.82% F1 score, and 98.08% ROC AUC compared to EstBERT's 81.58% accuracy, 81.61% F1 score, and 96.53% ROC AUC. The model demonstrated exceptional precision (84.73%) and strong recall across all three agency classes, with particularly excellent performance on Class 0 (Tarbijakaitse) achieving 95.12% recall.

* **Inference Efficiency**: 
  While XLM-RoBERTa has slightly higher computational requirements due to its multilingual architecture, the performance gains justify the additional resource usage. The model maintains reasonable inference speeds for production deployment scenarios.

* **CPU Deployment Viability**: 
  XLM-RoBERTa performs well on CPU-only environments, making it suitable for deployment in resource-constrained scenarios while maintaining high accuracy levels.

* **Language Handling**: 
  As a multilingual model, XLM-RoBERTa demonstrates excellent capability in handling Estonian language nuances and conversation patterns, outperforming the Estonian-specific EstBERT model in overall metrics.

* **Additional Factors**: 
  The model's robustness across different conversation types and its ability to achieve near-perfect ROC AUC (98.08%) indicate strong generalization capabilities for real-world deployment.

## Implementation Details

The selected model will be implemented with the following configuration:

* Base model: FacebookAI/xlm-roberta-base
* Fine-tuning approach: Standard transformer fine-tuning with cross-entropy loss
* Maximum sequence length: 512 tokens
* Preprocessing steps: Text normalization, tokenization, padding/truncation to max length
* Inference optimization: Batch processing for multiple requests, CPU-optimized inference

## Alternative Considerations

We also considered the following alternatives:

* **EstBERT (tartuNLP/EstBERT)**: 
  This Estonian-specific model was considered due to its specialized training on Estonian text. While it achieved strong performance (81.58% accuracy), it was not selected because XLM-RoBERTa outperformed it in all key metrics while providing multilingual capabilities for potential future expansion.

* **Standard XLM Model**: 
  The original XLM architecture was initially considered but dropped during development due to implementation complexity and the superior performance of XLM-RoBERTa for classification tasks.

## Performance Guarantees

The selected model is expected to meet the following minimum performance guarantees:

* Accuracy: ≥ 83%
* F1 Score: ≥ 82%
* Inference time: ≤ 2000 ms per request on CPU
* Memory footprint: ≤ 1500 MB

## Future Improvements

While the current model meets our requirements, we have identified potential areas for future improvement:

1. **Data Augmentation**: Expanding the synthetic dataset with more diverse conversation patterns and edge cases
2. **Model Optimization**: Implementing model distillation or quantization techniques to reduce inference time and memory usage
3. **Real-world Validation**: Testing the model on actual agency conversations to validate performance on non-synthetic data

## Conclusion

XLM-RoBERTa provides the optimal balance of accuracy and performance for our agency classification needs. Its performance on synthetic data demonstrates that it is suitable for the production environment, and we are confident it will meet the requirements for inter-class classification on agency conversations. The model's 83.33% accuracy and 98.08% ROC AUC indicate excellent discriminative capability for Estonian agency conversation routing.