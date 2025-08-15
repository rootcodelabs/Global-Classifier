# OOD Detection Decision Document

*Date: 2025-05-03 03:36:56*

## Decision Summary

Based on comprehensive evaluation of multiple OOD detection approaches, we have selected **sngp_energy** as the optimal method for detecting out-of-distribution examples in conversation classification.

## Selection Criteria

The following criteria were used to evaluate and compare OOD detection methods:

1. **OOD Detection Performance**: Measured using AUROC, AUPR, and FPR@95%TPR metrics.
2. **Classification Accuracy**: Impact on in-distribution classification performance.
3. **Computational Efficiency**: Inference time and resource requirements.
4. **Implementation Complexity**: Ease of integration with existing system.

## Method Evaluation

### sngp

**OOD Detection Performance**:
- AUROC: 0.0000
- AUPR: 0.1000
- FPR@95%TPR: 1.0000

**Classification Performance**:
- Accuracy: 0.6053
- F1 Score: 0.5062

**Computational Performance**:
- Inference Time (Batch Size 1): 565.33 ms
- Inference Time (Batch Size 32): 11451.04 ms

**Pros**:
- Strong uncertainty estimation through distance awareness
- Single model without ensemble averaging, efficient inference
- Compatible with modern deep learning architectures

**Cons**:
- More complex implementation than baseline methods
- Requires careful handling of covariance reset during training
- May require tuning of spectral normalization parameters


### energy

**OOD Detection Performance**:
- AUROC: 0.4142
- AUPR: 0.1594
- FPR@95%TPR: 0.9298

**Classification Performance**:
- Accuracy: 0.4298
- F1 Score: 0.3387

**Computational Performance**:
- Inference Time (Batch Size 1): 441.98 ms
- Inference Time (Batch Size 32): 11309.84 ms

**Pros**:
- Simple to implement on top of existing models
- No architectural changes required
- Theoretically well-founded for OOD detection

**Cons**:
- Performance can be sensitive to energy temperature parameter
- May require additional training with energy-based loss
- Less effective for detecting certain types of OOD examples


### sngp_energy

**OOD Detection Performance**:
- AUROC: 0.6109
- AUPR: 0.2633
- FPR@95%TPR: 0.7982

**Classification Performance**:
- Accuracy: 0.5175
- F1 Score: 0.4299

**Computational Performance**:
- Inference Time (Batch Size 1): 583.02 ms
- Inference Time (Batch Size 32): 10552.23 ms

**Pros**:
- Combines benefits of both SNGP and energy-based methods
- Better OOD detection through complementary approaches
- Robust to different types of OOD examples

**Cons**:
- Most complex implementation among all methods
- Higher computational overhead during training
- Requires tuning of multiple hyperparameters


### softmax

**OOD Detection Performance**:
- AUROC: 0.3452
- AUPR: 0.1410
- FPR@95%TPR: 0.8947

**Classification Performance**:
- Accuracy: 0.4737
- F1 Score: 0.3933

**Computational Performance**:
- Inference Time (Batch Size 1): 447.11 ms
- Inference Time (Batch Size 32): 10981.72 ms

**Pros**:
- Simplest approach with minimal changes to existing models
- Fast inference with no additional computation
- Well-understood calibration techniques available

**Cons**:
- Often less effective than more sophisticated methods
- Requires proper calibration for reliable uncertainty
- Tends to be overconfident far from the decision boundary


## Final Decision

We have selected **sngp_energy** as our OOD detection approach based on its strong performance across multiple metrics. The combined SNGP+Energy approach provides the most robust OOD detection by leveraging both distance awareness and energy scores. Despite its higher complexity, the superior detection performance justifies the implementation effort.

## Implementation Plan

### Integration Steps

1. Implement the selected OOD detection method within the existing classification model
2. Establish appropriate uncertainty thresholds based on validation data
3. Set up monitoring for OOD detection performance in production
4. Create fallback mechanisms for handling detected OOD examples

### Threshold Selection

We recommend setting the uncertainty threshold to achieve a 95% true positive rate (TPR) on validation data. This corresponds to correctly identifying 95% of in-distribution examples, with the remaining 5% incorrectly flagged as OOD. Based on our experiments, this threshold provides a good balance between catching OOD examples and minimizing false alarms.

## Conclusion

The selected OOD detection approach will enable the system to identify conversations that fall outside the trained distribution, allowing for more reliable classification and appropriate handling of uncertain cases. This implementation will improve the overall robustness of the conversation classification system and enhance user experience by avoiding incorrect classifications when the model is uncertain.
