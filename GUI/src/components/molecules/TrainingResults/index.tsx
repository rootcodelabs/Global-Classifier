import './TrainingResults.scss';

export type ClassMetrics = {
  f1: number;
  recall: number;
  accuracy: number;
  precision: number;
};

export type ModelPerformance = {
  model_type: string;
  class_metrics: {
    [className: string]: ClassMetrics;
  };
};

export type ModelResultsProps = {
  models: ModelPerformance[];
};

const ModelResults: React.FC<ModelResultsProps> = ({ models }) => {
    return (
        <div className="results-wrapper">
            <h3 className="best-model-header">
                Best Performing Model - {models?.[0]?.model_type || "N/A"}
            </h3>
            <h4 className="section-title">Training Results</h4>

            {models?.map((model, idx) => (
                <div className="model-section" key={idx}>
                    <h5 className="model-name">{model.model_type}</h5>

                    <div style={{ border: "1px solid #E6E6E6", padding: "1rem", borderRadius: "5px" }}>
                        <div className="header-row">
                            <div className="header-classes">Classes</div>
                            <div className="header-metrics">
                                <div>F1</div>
                                <div>Recall</div>
                                <div>Accuracy</div>
                                <div>Precision</div>
                            </div>
                        </div>
                        <hr className="hr-divider" />
                        {Object.entries(model?.class_metrics).map(([className, metrics]) => (
                            <div key={className} className="metric-row">
                                <div className="metric-class">{className}</div>
                                <div className="metric-values">
                                    <div>{metrics.f1}</div>
                                    <div>{metrics.recall}</div>
                                    <div>{metrics.accuracy}</div>
                                    <div>{metrics.precision}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
};

export default ModelResults;