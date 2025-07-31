import { ModelResultsProps } from 'types/dataModels';
import './TrainingResults.scss';

interface TrainingResultModel {
  avg_f1: number;
  avg_accuracy: number;
  combined_score: number;
  metrics: [string[], number[], number[]]; // [classes, accuracies, f1_scores]
  variant: {
    name: string;
    type: string;
    base_model: string;
    ood_method: string;
    full_model_name: string;
    confidence_scaling: boolean;
    uncertainty_strategy: string;
    human_handoff_threshold: number;
  };
  model_path: string;
}

const ModelResults: React.FC<{ models: TrainingResultModel[] }> = ({ models }) => {
  console.log(models);
  
  // Find best performing model by avg_f1
  const bestModel = models?.reduce((best, current) => 
    current.avg_f1 > best.avg_f1 ? current : best
  );

  // Sort models by avg_f1 in descending order
  const sortedModels = models?.sort((a, b) => b.avg_f1 - a.avg_f1) || [];

  // Check if there are multiple models
  const hasMultipleModels = models && models.length > 1;

  const formatScore = (score: number) => (score * 100).toFixed(2) + '%';

  const processModelMetrics = (model: TrainingResultModel) => {
    const [classes, accuracies, f1Scores] = model.metrics;
    
    return classes.map((className, index) => ({
      className: className.replace(/_/g, ' '),
      accuracy: accuracies[index],
      f1: f1Scores[index]
    }));
  };

  if (!models || models.length === 0) {
    return (
      <div className="results-wrapper">
        <p>No training results available</p>
      </div>
    );
  }

  return (
    <div className="results-wrapper">
      {hasMultipleModels && (
        <>
          <h3 className="best-model-header">
            Best Performing Model - {bestModel?.variant?.name || "N/A"}
          </h3>
          <div className="best-model-summary">
            <div className="summary-metric">
              <span className="metric-label">Average F1:</span>
              <span className="metric-value">{formatScore(bestModel?.avg_f1 || 0)}</span>
            </div>
            <div className="summary-metric">
              <span className="metric-label">Average Accuracy:</span>
              <span className="metric-value">{formatScore(bestModel?.avg_accuracy || 0)}</span>
            </div>
            <div className="summary-metric">
              <span className="metric-label">Combined Score:</span>
              <span className="metric-value">{formatScore(bestModel?.combined_score || 0)}</span>
            </div>
          </div>
        </>
      )}

      <h4 className="section-title">Training Results</h4>

      {sortedModels.map((model, idx) => {
        const processedMetrics = processModelMetrics(model);
        const isBest = hasMultipleModels && model === bestModel;
        
        return (
          <div className={`model-section ${isBest ? 'best-model' : ''}`} key={idx}>
            <div className="model-header">
              <h5 className="model-name">
                {model.variant.name}
                {/* Only show best badge when there are multiple models */}
                {hasMultipleModels && isBest && <span className="best-badge">Best</span>}
              </h5>
            </div>

            <div className="model-metrics-card">
              <div className="header-row">
                <div className="header-classes">Classes</div>
                <div className="header-metrics">
                  <div>F1 Score</div>
                  <div>Accuracy</div>
                </div>
              </div>
              <hr className="hr-divider" />
              
              {processedMetrics.map((metric, metricIdx) => (
                <div key={`${metric.className}-${metricIdx}`} className="metric-row">
                  <div className="metric-class">{metric.className}</div>
                  <div className="metric-values">
                    <div className="metric-value f1">{formatScore(metric.f1)}</div>
                    <div className="metric-value accuracy">{formatScore(metric.accuracy)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ModelResults;