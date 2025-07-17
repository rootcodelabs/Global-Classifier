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
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
                            <div style={{ width: "30%" }}>Classes</div>
                            <div style={{
                                display: "grid",
                                gridTemplateColumns: "repeat(4, 7rem)", // Fixed width for each column
                                gap: "1rem",
                                width: "70%",
                            }}>
                                <div>F1</div>
                                <div>Recall</div>
                                <div>Accuracy</div>
                                <div>Precision</div>
                            </div>

                        </div>
                        <hr style={{
                            border: "none",
                            borderTop: "1px solid #D1D1D1",
                            margin: 0
                        }} />
                        {Object.entries(model?.class_metrics).map(([className, metrics]) => (
                            <div key={className} style={{ padding: ".5rem 0rem" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", width: "auto" }}>
                                    <div style={{ width: "30%" }} >{className}</div>
                                    <div style={{
                                        display: "grid",
                                        gridTemplateColumns: "repeat(4, 7rem)", 
                                        gap: "1rem",
                                        width: "70%"
                                    }}>
                                        <div>{metrics.f1}</div>
                                        <div>{metrics.recall}</div>
                                        <div>{metrics.accuracy}</div>
                                        <div>{metrics.precision}</div>
                                    </div>
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