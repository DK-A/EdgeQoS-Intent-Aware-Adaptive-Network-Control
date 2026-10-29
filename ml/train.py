"""
ml/train.py - Leakage-Free Decision Tree Training with GroupKFold
Tata Elxsi TELIPORT S4 · Problem Statement 3
Pure-NumPy implementation ensuring zero external dependencies.
Trains pruned decision tree on Zero-DPI features, evaluates calibration,
and exports standalone arrays to JSON.
"""

import json
import os
import math
import numpy as np
from ml.collect.generator import generate_dataset, CLASS_NAMES

class PureNumpyDecisionTree:
    def __init__(self, max_depth: int = 6, min_samples_leaf: int = 8):
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.children_left = []
        self.children_right = []
        self.feature = []
        self.threshold = []
        self.value = []
        self.n_classes = 4

    def fit(self, X: np.ndarray, y: np.ndarray, n_classes: int = 4):
        self.n_classes = n_classes
        self.children_left = []
        self.children_right = []
        self.feature = []
        self.threshold = []
        self.value = []

        def gini(y_sub):
            if len(y_sub) == 0:
                return 0.0
            counts = np.bincount(y_sub, minlength=self.n_classes)
            probs = counts / len(y_sub)
            return 1.0 - np.sum(probs ** 2)

        def build(X_sub, y_sub, depth):
            counts = np.bincount(y_sub, minlength=self.n_classes).tolist()
            if depth >= self.max_depth or len(y_sub) < 2 * self.min_samples_leaf or gini(y_sub) < 1e-6:
                node_idx = len(self.feature)
                self.children_left.append(-1)
                self.children_right.append(-1)
                self.feature.append(-2)
                self.threshold.append(-2.0)
                self.value.append(counts)
                return node_idx

            best_gain = -1.0
            best_feat = -1
            best_thr = 0.0
            current_gini = gini(y_sub)
            n = len(y_sub)

            # Evaluate split candidates across features
            for feat in range(X_sub.shape[1]):
                vals = np.unique(X_sub[:, feat])
                if len(vals) <= 1:
                    continue
                thrs = (vals[:-1] + vals[1:]) / 2.0
                if len(thrs) > 25:
                    thrs = np.percentile(thrs, np.linspace(5, 95, 20))

                for thr in thrs:
                    left_mask = X_sub[:, feat] <= thr
                    right_mask = ~left_mask
                    n_l, n_r = np.sum(left_mask), np.sum(right_mask)
                    if n_l < self.min_samples_leaf or n_r < self.min_samples_leaf:
                        continue
                    gain = current_gini - (n_l / n) * gini(y_sub[left_mask]) - (n_r / n) * gini(y_sub[right_mask])
                    if gain > best_gain:
                        best_gain = gain
                        best_feat = feat
                        best_thr = thr

            if best_gain <= 0.0:
                node_idx = len(self.feature)
                self.children_left.append(-1)
                self.children_right.append(-1)
                self.feature.append(-2)
                self.threshold.append(-2.0)
                self.value.append(counts)
                return node_idx

            node_idx = len(self.feature)
            self.children_left.append(-1)
            self.children_right.append(-1)
            self.feature.append(best_feat)
            self.threshold.append(float(best_thr))
            self.value.append(counts)

            left_mask = X_sub[:, best_feat] <= best_thr
            right_mask = ~left_mask

            left_child = build(X_sub[left_mask], y_sub[left_mask], depth + 1)
            self.children_left[node_idx] = left_child

            right_child = build(X_sub[right_mask], y_sub[right_mask], depth + 1)
            self.children_right[node_idx] = right_child

            return node_idx

        build(X, y, 0)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        probs = []
        for row in X:
            curr = 0
            while self.children_left[curr] != -1:
                feat = self.feature[curr]
                thr = self.threshold[curr]
                if row[feat] <= thr:
                    curr = self.children_left[curr]
                else:
                    curr = self.children_right[curr]
            v = np.array(self.value[curr], dtype=float)
            s = np.sum(v)
            probs.append(v / s if s > 0 else np.ones(self.n_classes) / self.n_classes)
        return np.array(probs)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)

def compute_metrics(y_true, y_pred, n_classes=4):
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1

    precision = []
    recall = []
    f1 = []
    for c in range(n_classes):
        tp = cm[c, c]
        fp = np.sum(cm[:, c]) - tp
        fn = np.sum(cm[c, :]) - tp
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        precision.append(p)
        recall.append(r)
        f1.append(f)

    macro_f1 = np.mean(f1)
    accuracy = np.trace(cm) / np.sum(cm)
    return {
        "accuracy": float(accuracy),
        "macro_f1": float(macro_f1),
        "per_class_precision": [float(x) for x in precision],
        "per_class_recall": [float(x) for x in recall],
        "per_class_f1": [float(x) for x in f1],
        "confusion_matrix": cm.tolist()
    }

def group_k_fold_split(groups: np.ndarray, n_splits: int = 5):
    unique_groups = np.unique(groups)
    np.random.shuffle(unique_groups)
    folds = np.array_split(unique_groups, n_splits)
    for fold_groups in folds:
        val_mask = np.isin(groups, fold_groups)
        train_mask = ~val_mask
        yield np.where(train_mask)[0], np.where(val_mask)[0]

def main():
    print("=============================================================")
    print("EdgeQoS: Zero-DPI Pruned Decision Tree Training & Evaluation")
    print("=============================================================")
    X_list, y_list, groups_list = generate_dataset(n_samples_per_class=600, random_seed=42)
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    groups = np.array(groups_list, dtype=np.int32)

    print(f"[*] Dataset: {X.shape[0]} total flows, {X.shape[1]} features, 4 classes.")
    print(f"[*] Cross-Validation: GroupKFold (k=5) partitioned across {len(np.unique(groups))} unique sessions.")

    fold = 1
    cv_metrics = []
    for train_idx, val_idx in group_k_fold_split(groups, n_splits=5):
        tree = PureNumpyDecisionTree(max_depth=6, min_samples_leaf=8)
        tree.fit(X[train_idx], y[train_idx])
        preds = tree.predict(X[val_idx])
        m = compute_metrics(y[val_idx], preds)
        cv_metrics.append(m["macro_f1"])
        print(f"  Fold {fold}: Macro-F1 = {m['macro_f1']:.4f}, Accuracy = {m['accuracy']*100:.2f}%")
        fold += 1

    mean_f1 = float(np.mean(cv_metrics))
    std_f1 = float(np.std(cv_metrics))
    print(f"[+] GroupKFold Cross-Validation Result: Mean Macro-F1 = {mean_f1:.4f} (+- {std_f1:.4f})")

    # Fit final model on full dataset
    final_tree = PureNumpyDecisionTree(max_depth=6, min_samples_leaf=8)
    final_tree.fit(X, y)

    # Evaluate full model metrics & ECE calibration
    probas = final_tree.predict_proba(X)
    top_probas = np.max(probas, axis=1)
    preds = np.argmax(probas, axis=1)
    full_metrics = compute_metrics(y, preds)

    # Compute Expected Calibration Error (ECE) across 10 bins
    bins = np.linspace(0.0, 1.0, 11)
    bin_indices = np.digitize(top_probas, bins) - 1
    bin_indices = np.clip(bin_indices, 0, 9)
    ece = 0.0
    for b in range(10):
        mask = bin_indices == b
        if np.sum(mask) > 0:
            bin_acc = np.mean(preds[mask] == y[mask])
            bin_conf = np.mean(top_probas[mask])
            ece += (np.sum(mask) / len(y)) * abs(bin_acc - bin_conf)

    print(f"[+] Expected Calibration Error (ECE): {ece:.4f}")
    print(f"[+] Class F1s: Realtime={full_metrics['per_class_f1'][0]:.4f}, "
          f"Stream={full_metrics['per_class_f1'][1]:.4f}, "
          f"Bulk={full_metrics['per_class_f1'][2]:.4f}, "
          f"Other={full_metrics['per_class_f1'][3]:.4f}")

    # Export pure arrays to JSON
    model_export = {
        "left": final_tree.children_left,
        "right": final_tree.children_right,
        "feat": final_tree.feature,
        "thr": final_tree.threshold,
        "value": final_tree.value,
        "classes": [CLASS_NAMES[i] for i in range(4)],
        "tau_confidence": 0.85,
        "max_depth": 6,
        "n_features": 22,
        "metrics": {
            "cv_macro_f1_mean": mean_f1,
            "cv_macro_f1_std": std_f1,
            "ece": float(ece),
            "full_metrics": full_metrics
        }
    }

    os.makedirs("ml/models", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    with open("ml/models/tree_model.json", "w") as f:
        json.dump(model_export, f, indent=2)

    with open("results/ml_eval_report.json", "w") as f:
        json.dump(model_export["metrics"], f, indent=2)

    print(f"[+] Production model saved to ml/models/tree_model.json ({os.path.getsize('ml/models/tree_model.json')} bytes)")
    print(f"[+] Evaluation report saved to results/ml_eval_report.json")

if __name__ == "__main__":
    main()
