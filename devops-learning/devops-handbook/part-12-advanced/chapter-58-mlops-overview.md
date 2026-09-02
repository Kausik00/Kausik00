# Chapter 58: MLOps Overview for DevOps Engineers

*DevOps Handbook — Pages 282–286 of this PDF edition*
---

## 58.1 Why DevOps engineers need MLOps

Machine learning systems are **software systems**—they require versioning, testing, deployment, monitoring, and incident response. Unlike traditional apps, ML adds **data**, **models**, and **non-deterministic behavior**. **MLOps** (Machine Learning Operations) applies DevOps principles to the ML lifecycle.

DevOps engineers increasingly support data science teams—or operate ML platforms. Understanding MLOps prevents treating models as "black box scripts" outside standard engineering practices.

ML system components:

```
Data sources → Feature pipeline → Training → Model registry →
  Deployment → Inference service → Monitoring (data + model drift)
```

---

## 58.2 ML lifecycle vs traditional SDLC

| Traditional app | ML system |
|-----------------|-----------|
| Code is primary artifact | Code + data + model weights |
| Tests verify logic | Tests verify data schema, model metrics |
| Deploy binary/container | Deploy model version + feature pipeline |
| Monitor errors/latency | Monitor + data drift + model performance |
| Rollback = previous release | Rollback = previous model + feature schema |

**Technical debt in ML** accumulates silently—training-serving skew, stale features, label leakage—requiring explicit governance.

---

## 58.3 Key MLOps concepts

| Concept | Definition |
|---------|------------|
| **Feature store** | Centralized, versioned features for training and serving |
| **Model registry** | Versioned model artifacts with metadata and stage (staging/prod) |
| **Experiment tracking** | Log params, metrics, artifacts per training run |
| **Training pipeline** | Automated, reproducible training workflow |
| **Serving** | Real-time (REST/gRPC) or batch inference |
| **Data validation** | Schema and statistical checks on input data |
| **Model monitoring** | Drift detection, performance decay alerts |

Tools landscape:

| Category | Tools |
|----------|-------|
| Experiment tracking | MLflow, Weights & Biases, Neptune |
| Orchestration | Kubeflow, Metaflow, Airflow, Argo Workflows |
| Feature store | Feast, Tecton, SageMaker Feature Store |
| Model registry | MLflow Model Registry, SageMaker, Vertex AI |
| Serving | KServe, Seldon Core, TorchServe, Triton |
| Monitoring | Evidently AI, WhyLabs, Arize |

---

## 58.4 Reproducible training pipeline

Training must be **reproducible**: same data snapshot + code + hyperparameters = same model (within stochastic variance).

MLflow training example:

```python
import mlflow
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

with mlflow.start_run():
    mlflow.log_param("n_estimators", 100)
    mlflow.log_param("max_depth", 10)

    model = RandomForestClassifier(n_estimators=100, max_depth=10)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    accuracy = accuracy_score(y_test, preds)
    mlflow.log_metric("accuracy", accuracy)

    mlflow.sklearn.log_model(model, "model")
```

Pipeline orchestration (Kubeflow Pipelines):

```python
@dsl.pipeline(name="Training pipeline")
def training_pipeline(data_path: str):
    validate_op = validate_data(data_path)
    train_op = train_model(validate_op.outputs["validated_data"])
    evaluate_op = evaluate_model(train_op.outputs["model"])
    with dsl.Condition(evaluate_op.outputs["accuracy"] > 0.85):
        deploy_op = register_model(train_op.outputs["model"])
```

CI for ML:

- Unit tests on feature engineering functions
- Data validation on sample datasets (Great Expectations)
- Model performance threshold gates before registry promotion

---

## 58.5 Model deployment patterns

| Pattern | Description |
|---------|-------------|
| **Embedded model** | Model loaded in app process (sklearn pickle, ONNX) |
| **Model server** | Separate inference service (Triton, TF Serving) |
| **Sidecar** | Model container alongside app pod in K8s |
| **Serverless** | Lambda/Cloud Functions for low-traffic inference |
| **Batch** | Scheduled jobs scoring datasets offline |

KServe InferenceService:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: fraud-detector
spec:
  predictor:
    sklearn:
      storageUri: s3://models/fraud-detector/v3
      resources:
        requests:
          cpu: "500m"
          memory: "512Mi"
        limits:
          cpu: "1"
          memory: "1Gi"
```

**Canary model rollout**: route 5% traffic to new model version; compare prediction latency and business KPI before full promotion—same patterns as Chapter 41.

---

## 58.6 Feature stores and training-serving skew

**Training-serving skew** — Features computed differently in training vs production—silent accuracy degradation.

Feature store solves:

- **Single definition** — Feature logic defined once
- **Point-in-time correctness** — Training uses historical feature values as they existed
- **Online/offline serving** — Same features for batch training and real-time inference

Feast example:

```python
from feast import FeatureStore

store = FeatureStore(repo_path=".")

# Training: historical features
training_df = store.get_historical_features(
    entity_df=entity_df,
    features=["customer_features:avg_order_value"],
).to_df()

# Serving: online features
features = store.get_online_features(
    features=["customer_features:avg_order_value"],
    entity_rows=[{"customer_id": 12345}],
).to_dict()
```

DevOps role: operate Feast infrastructure, monitor feature pipeline latency, integrate with data warehouse connectors.

---

## 58.7 Monitoring ML in production

Monitor four layers:

| Layer | Signals |
|-------|---------|
| **Infrastructure** | CPU/GPU, memory, request rate (standard observability) |
| **Service** | Latency, errors, throughput |
| **Data** | Input distribution drift, missing features, schema violations |
| **Model** | Prediction distribution drift, accuracy on labeled feedback |

Evidently drift report (conceptual):

```python
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset

report = Report(metrics=[DataDriftPreset()])
report.run(reference_data=training_sample, current_data=production_sample)
report.save_html("drift_report.html")
```

Alert when:

- Feature drift exceeds statistical threshold
- Model accuracy on holdout feedback drops
- Inference latency SLO breached

Retrain triggers: scheduled (weekly) + event-driven (drift alert).

---

## 58.8 Governance and responsible ML

- **Model cards** — Document intended use, limitations, bias evaluation
- **Lineage** — Track data sources, transformations, model dependencies
- **Access control** — Sensitive training data restricted
- **Audit** — Who promoted model to production
- **Rollback** — Previous model version in registry ready to deploy

Regulatory contexts (credit, healthcare) require explainability (SHAP, LIME) and audit trails—integrate with compliance automation (Chapter 54).

---

## 58.9 DevOps + MLOps collaboration

| DevOps provides | Data science provides |
|-----------------|----------------------|
| K8s, CI/CD, observability | Models, features, metrics |
| GPU node pools, autoscaling | Training job requirements |
| Secrets, networking | Data access patterns |
| SLOs, on-call for serving | Model performance thresholds |

Platform golden path for ML: "Deploy sklearn model from registry to KServe with monitoring"—Backstage template scaffolds InferenceService + Grafana dashboard.

---

## 58.10 Chapter summary

- MLOps extends DevOps to data, training, model registry, serving, and drift monitoring.
- Reproducible pipelines, experiment tracking, and feature stores reduce training-serving skew.
- Deploy models like services—with canaries, SLOs, and rollback via model registry.
- DevOps engineers operate ML infrastructure; data scientists own model quality—collaborate via platform golden paths.

---

## 🧪 Lab 58.1 — MLflow end-to-end

1. Train simple sklearn model; log to local MLflow.
2. Register model; promote to Staging.
3. Serve model via `mlflow models serve`; send test predictions.

---

## 🧪 Lab 58.2 — Model monitoring dashboard

1. Collect week of inference inputs (CSV).
2. Run Evidently drift report against training baseline.
3. Document retrain trigger policy based on drift score.

---

## Review questions

1. How does an ML system differ from a traditional application in terms of artifacts?
2. What is training-serving skew, and how do feature stores help?
3. Name three components of an MLOps platform stack.
4. Compare real-time and batch inference deployment patterns.
5. What should ML monitoring cover beyond standard RED metrics?
6. How do canary deployments apply to model rollouts?
7. What is a model registry, and why version models?

---

*Continue: Chapter 59 — Capstone Production System Design*
