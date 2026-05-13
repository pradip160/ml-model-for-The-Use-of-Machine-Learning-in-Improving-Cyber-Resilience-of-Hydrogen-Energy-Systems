# Machine Learning for Cyber Resilience of Hydrogen Energy Systems

This project package contains a distinction-level bachelor final-year project artefact and report focused on the use of machine learning to support cyber resilience in hydrogen energy systems.

## What is included

- A full final report in DOCX and PDF format.
- A reproducible synthetic hydrogen ICS-style dataset generator.
- A model-training and evaluation pipeline.
- Three detection approaches:
  - Logistic Regression
  - Random Forest
  - Isolation Forest
- Four attack scenarios:
  - False data injection
  - Denial-of-service-like network degradation
  - Actuator spoofing
  - Stealthy sensor drift
- Stronger evaluation artefacts:
  - Holdout performance metrics
  - Three-fold stratified cross-validation
  - Per-attack recall analysis
  - Permutation feature importance
  - Confusion matrix, ROC curve, precision-recall curve, and attack timeline

## Scope note

The dataset is **synthetic** and designed for educational demonstration. The reported results show that the machine-learning pipeline works on a controlled hydrogen-inspired cyber-physical scenario. They are **not** evidence of production performance in a real hydrogen facility.

## Reproduce the artefact

```bash
python code/generate_synthetic_hydrogen_ics_data.py --output data/hydrogen_ics_synthetic.csv
python code/train_hydrogen_anomaly_model.py --input data/hydrogen_ics_synthetic.csv --output-dir outputs
```

## Key output files

- `outputs/model_metrics.csv`
- `outputs/model_metrics.json`
- `outputs/cross_validation_metrics.csv`
- `outputs/per_attack_recall.csv`
- `outputs/feature_importance.csv`
- `outputs/classification_report.txt`
- `outputs/confusion_matrix.png`
- `outputs/roc_curve.png`
- `outputs/precision_recall_curve.png`
- `outputs/feature_importance.png`
- `outputs/attack_timeline.png`

## Report files

- `docs/Hydrogen_Cyber_Resilience_Final_Project_Report.docx`
- `docs/Hydrogen_Cyber_Resilience_Final_Project_Report.pdf`

## Suggested next research extension

Replace the synthetic dataset with a real ICS benchmark or a hydrogen-domain digital-twin dataset, then repeat the same experimental protocol. The most academically meaningful next step would be to evaluate subtle, low-amplitude attack scenarios under more realistic operational noise and temporal dependencies.
