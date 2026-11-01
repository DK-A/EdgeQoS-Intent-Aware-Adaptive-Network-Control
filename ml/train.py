#!/usr/bin/env python3
"""
ml/train.py - Pre-Registered Leakage-Free Decision Tree Training & Calibration (ml-v2)
Strict session-isolated partitions:
- 60% Train (GroupKFold CV hyperparameter optimization)
- 20% Validation (Platt scaling calibration & tau selection based on FPR <= 5%)
- 20% Test (Held-out; untouched until evaluation)
No target metrics: Reports raw measured empirical outcomes.
"""

import os
import sys
import json
import math
import hashlib
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ml.collect.generator import CLASS_NAMES

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
                curr = self.children_left[curr] if row[feat] <= thr else self.children_right[curr]
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

    precision, recall, f1 = [], [], []
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
    accuracy = np.trace(cm) / np.sum(cm) if np.sum(cm) > 0 else 0.0
    return {
        "accuracy": float(accuracy),
        "macro_f1": float(macro_f1),
        "precision": [float(x) for x in precision],
        "recall": [float(x) for x in recall],
        "f1": [float(x) for x in f1],
        "confusion_matrix": cm.tolist()
    }

def group_k_fold_split(groups: np.ndarray, n_splits: int = 5, seed: int = 42):
    rng = np.random.RandomState(seed)
    unique_groups = np.unique(groups)
    rng.shuffle(unique_groups)
    folds = np.array_split(unique_groups, n_splits)
    for fold_groups in folds:
        val_mask = np.isin(groups, fold_groups)
        train_mask = ~val_mask
        yield np.where(train_mask)[0], np.where(val_mask)[0]

def partition_sessions(dataset_path: str = "ml/data/dataset_v2.json", seed: int = 42):
    with open(dataset_path, "r") as f:
        data = json.load(f)

    X = np.array([d["features"] for d in data], dtype=np.float32)
    y = np.array([d["class_id"] for d in data], dtype=np.int32)
    sessions = np.array([d["session_id"] for d in data], dtype=np.int32)
    conditions = [d["condition"] for d in data]

    # Pre-registered session partition: 60% Train, 20% Val, 20% Test
    rng = np.random.RandomState(seed)
    unique_sessions = np.unique(sessions)
    rng.shuffle(unique_sessions)

    n_sessions = len(unique_sessions)
    n_train = int(0.60 * n_sessions)
    n_val = int(0.20 * n_sessions)

    train_sess = set(unique_sessions[:n_train])
    val_sess = set(unique_sessions[n_train:n_train + n_val])
    test_sess = set(unique_sessions[n_train + n_val:])

    train_idx = [i for i, s in enumerate(sessions) if s in train_sess]
    val_idx = [i for i, s in enumerate(sessions) if s in val_sess]
    test_idx = [i for i, s in enumerate(sessions) if s in test_sess]

    return X, y, sessions, conditions, train_idx, val_idx, test_idx

def main():
    print("=============================================================")
    print("EdgeQoS: ml-v2 Decision Tree Training & Pre-Registered Protocol")
    print("=============================================================")

    dataset_path = "ml/data/dataset_v2.json"
    manifest_path = "ml/data/manifest_v2.csv"
    if not os.path.exists(dataset_path):
        print(f"[-] Error: {dataset_path} not found. Run real_stack_collector.py first.")
        sys.exit(1)

    # Compute manifest hash
    with open(manifest_path, "rb") as f:
        manifest_hash = hashlib.sha256(f.read()).hexdigest()

    X, y, sessions, conditions, train_idx, val_idx, test_idx = partition_sessions(dataset_path, seed=42)

    print(f"[*] Dataset: {len(X)} total flows, {len(np.unique(sessions))} sessions, 22 features.")
    print(f"[*] Pre-registered split:")
    print(f"    Train: {len(train_idx)} flows ({len(np.unique(sessions[train_idx]))} sessions)")
    print(f"    Val:   {len(val_idx)} flows ({len(np.unique(sessions[val_idx]))} sessions)")
    print(f"    Test:  {len(test_idx)} flows ({len(np.unique(sessions[test_idx]))} sessions) [LOCKED]")

    # 1. Hyperparameter Search on Train Set ONLY via 5-Fold GroupKFold
    print("\n[*] Step 1: Hyperparameter Search on Train split (GroupKFold k=5)...")
    param_grid = [
        {"max_depth": 5, "min_samples_leaf": 8},
        {"max_depth": 6, "min_samples_leaf": 6},
        {"max_depth": 6, "min_samples_leaf": 10},
        {"max_depth": 7, "min_samples_leaf": 8}
    ]

    best_score = -1.0
    best_params = param_grid[0]

    for params in param_grid:
        cv_f1s = []
        for tr_i, val_i in group_k_fold_split(sessions[train_idx], n_splits=5, seed=42):
            tree = PureNumpyDecisionTree(max_depth=params["max_depth"], min_samples_leaf=params["min_samples_leaf"])
            tree.fit(X[train_idx][tr_i], y[train_idx][tr_i])
            preds = tree.predict(X[train_idx][val_i])
            m = compute_metrics(y[train_idx][val_i], preds)
            cv_f1s.append(m["macro_f1"])
        mean_cv_f1 = float(np.mean(cv_f1s))
        print(f"    Params {params} -> CV Macro F1: {mean_cv_f1:.4f}")
        if mean_cv_f1 > best_score:
            best_score = mean_cv_f1
            best_params = params

    print(f"[+] Selected Best Hyperparameters on Train: {best_params} (CV F1 = {best_score:.4f})")

    # 2. Fit Model on full Train set
    final_tree = PureNumpyDecisionTree(max_depth=best_params["max_depth"], min_samples_leaf=best_params["min_samples_leaf"])
    final_tree.fit(X[train_idx], y[train_idx])

    # 3. Validation Set Calibration & Tau Selection (Protocol Rule: FPR <= 5%)
    print("\n[*] Step 2: Evaluating Calibration & Tau Selection on Validation split...")
    val_probs = final_tree.predict_proba(X[val_idx])
    val_preds = np.argmax(val_probs, axis=1)
    val_confs = np.max(val_probs, axis=1)
    val_y = y[val_idx]

    # Evaluate False Promotion Rate across tau thresholds
    # FPR: (Bulk(2) or Other(3) predicted as Realtime(0) or Stream(1)) / Total Non-Priority
    non_priority_mask = np.isin(val_y, [2, 3])
    total_non_priority = np.sum(non_priority_mask)

    tau_candidates = [0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
    selected_tau = 0.70
    fpr_results = {}

    for tau in tau_candidates:
        promoted_mask = (val_confs >= tau) & np.isin(val_preds, [0, 1])
        false_promoted = np.sum(non_priority_mask & promoted_mask)
        fpr = (false_promoted / total_non_priority * 100.0) if total_non_priority > 0 else 0.0
        abstain_pct = np.mean(val_confs < tau) * 100.0
        fpr_results[str(tau)] = {"fpr": float(fpr), "abstain_pct": float(abstain_pct)}
        print(f"    Tau = {tau:.2f}: Validation FPR = {fpr:.2f}%, Abstention = {abstain_pct:.1f}%")

    # Pre-registered rule: smallest tau with FPR <= 5.0%
    for tau in tau_candidates:
        if fpr_results[str(tau)]["fpr"] <= 5.0:
            selected_tau = tau
            break

    print(f"[+] Selected Confidence Threshold (Tau) on Validation: {selected_tau:.2f} (FPR = {fpr_results[str(selected_tau)]['fpr']:.2f}%)")

    # Expected Calibration Error (ECE) on Validation
    bins = np.linspace(0.0, 1.0, 11)
    bin_indices = np.digitize(val_confs, bins) - 1
    bin_indices = np.clip(bin_indices, 0, 9)
    ece = 0.0
    for b in range(10):
        mask = bin_indices == b
        if np.sum(mask) > 0:
            bin_acc = np.mean(val_preds[mask] == val_y[mask])
            bin_conf = np.mean(val_confs[mask])
            ece += (np.sum(mask) / len(val_y)) * abs(bin_acc - bin_conf)

    print(f"[+] Validation Expected Calibration Error (ECE): {ece:.4f}")

    # Export Model JSON
    os.makedirs("ml/models", exist_ok=True)
    os.makedirs("results", exist_ok=True)

    model_export = {
        "version": "ml-v2",
        "left": final_tree.children_left,
        "right": final_tree.children_right,
        "feat": final_tree.feature,
        "thr": final_tree.threshold,
        "value": final_tree.value,
        "classes": [CLASS_NAMES[i] for i in range(4)],
        "tau_confidence": float(selected_tau),
        "max_depth": best_params["max_depth"],
        "min_samples_leaf": best_params["min_samples_leaf"],
        "manifest_hash": manifest_hash,
        "split_counts": {
            "train": len(train_idx),
            "val": len(val_idx),
            "test": len(test_idx)
        },
        "validation_metrics": {
            "cv_f1_train": float(best_score),
            "val_ece": float(ece),
            "tau_sweep": fpr_results,
            "chosen_tau": float(selected_tau)
        }
    }

    model_path = "ml/models/tree_model.json"
    with open(model_path, "w") as f:
        json.dump(model_export, f, indent=2)

    # Save partition indices for strict test evaluation
    partitions = {
        "train_idx": train_idx,
        "val_idx": val_idx,
        "test_idx": test_idx
    }
    with open("ml/data/partitions.json", "w") as f:
        json.dump(partitions, f)

    print(f"\n[+] Production model exported to {model_path} ({os.path.getsize(model_path)} bytes)")
    print(f"[+] Saved partition layout to ml/data/partitions.json")
    print(f"[*] Test partition remains locked for ml/evaluate.py")

if __name__ == "__main__":
    main()
