import numpy as np
from src.metrics import evaluate_detector, compute_eer

# Generate synthetic calibration set of impersonation-probability scores
np.random.seed(42)
n_samples = 1000
# Negative class (Human): scores clustered around 0.2
y_neg = np.zeros(n_samples)
scores_neg = np.random.normal(0.2, 0.15, n_samples)

# Positive class (AI): scores clustered around 0.8
y_pos = np.ones(n_samples)
scores_pos = np.random.normal(0.8, 0.15, n_samples)

y_true = np.concatenate([y_neg, y_pos])
y_scores = np.concatenate([scores_neg, scores_pos])
y_scores = np.clip(y_scores, 0, 1)

eer_res = compute_eer(y_true, y_scores)
print(f"EER Threshold: {eer_res.threshold:.4f}")
print(f"EER: {eer_res.eer:.4f}")
