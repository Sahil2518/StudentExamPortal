"""
2PL Item Response Theory (IRT) model.

Item Response Theory models the probability that a student with ability
theta answers an item correctly, as a function of the item's difficulty
(b) and discrimination (a) parameters.

The 2PL model:
    P(correct | theta, a, b) = 1 / (1 + exp(-a * (theta - b)))

Parameters:
    a  - discrimination: how well the item separates high from low ability
         students. Higher values mean the item is more informative.
         Typical range: 0.5 to 2.5.

    b  - difficulty: the ability level at which a student has a 50%
         chance of answering correctly.
         Range follows the theta scale (usually -3 to +3).

    theta - student ability: higher values mean stronger knowledge.

This module fits a and b for each question using observed response data,
and estimates theta for each student given their response pattern.

Limitations:
    - Requires at least 5-10 responses per item for reliable estimates.
    - Students with all-correct or all-wrong response patterns have
      undefined MLEs; we use regularization priors to handle this.
    - With the current question bank (400 items, sparse student data),
      many items will have high standard errors on their estimates.
      These are clearly reported so they are not misused.
"""

import json
import warnings
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit  # stable sigmoid: 1 / (1 + exp(-x))


# Directory for saving fitted parameters
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def _two_pl_prob(theta: float, a: float, b: float) -> float:
    """
    Probability of correct response in the 2PL model.

    P = sigmoid(a * (theta - b))
    """
    return float(expit(a * (theta - b)))


def _neg_log_likelihood(
    params: np.ndarray,
    responses: np.ndarray,
    thetas: np.ndarray,
    a_prior_mean: float = 1.0,
    a_prior_std: float = 0.5,
    b_prior_std: float = 1.0,
) -> float:
    """
    Negative log-likelihood for one item's a and b parameters,
    given observed responses and student abilities.

    Includes regularizing priors:
      a ~ LogNormal(log(a_prior_mean), a_prior_std)  -> keeps a > 0
      b ~ Normal(0, b_prior_std)                     -> keeps b centered
    """

    a, b = params

    # Hard constraint: discrimination must be positive
    if a <= 0:
        return 1e10

    # Compute predicted probabilities for each student
    probs = expit(a * (thetas - b))

    # Clip to avoid log(0)
    probs = np.clip(probs, 1e-9, 1 - 1e-9)

    # Bernoulli log-likelihood
    ll = np.sum(
        responses * np.log(probs) + (1 - responses) * np.log(1 - probs)
    )

    # Log-normal prior on a: log(a) ~ Normal(log(mean), std)
    log_a_prior = -0.5 * ((np.log(a) - np.log(a_prior_mean)) / a_prior_std) ** 2

    # Normal prior on b
    b_prior = -0.5 * (b / b_prior_std) ** 2

    return -(ll + log_a_prior + b_prior)


class IRTModel:
    """
    2PL Item Response Theory model.

    Fits item parameters (a, b) from a response matrix and estimates
    student ability (theta) given a response pattern.

    Usage:
        model = IRTModel()
        model.fit(response_matrix, student_ids, question_ids)
        theta = model.get_student_ability(student_responses)
        params = model.get_item_params(question_id)
        model.save()
    """

    def __init__(self):
        # Maps question_id -> {"a": float, "b": float, "se_a": float, "se_b": float}
        self.item_params: Dict[str, dict] = {}

        # Whether fit() has been called successfully
        self.is_fitted = False

    def fit(
        self,
        response_matrix: np.ndarray,
        student_ids: List[str],
        question_ids: List[str],
        max_em_iterations: int = 20,
        convergence_tol: float = 1e-4,
    ):
        """
        Estimate item parameters using Marginal Maximum Likelihood (MML)
        with an Expectation-Maximization (EM) approximation.

        Parameters
        ----------
        response_matrix : ndarray of shape (n_students, n_items)
            Binary matrix. 1 = correct, 0 = wrong, NaN = not attempted.

        student_ids : list of str
            Student identifiers corresponding to matrix rows.

        question_ids : list of str
            Question identifiers corresponding to matrix columns.

        Notes
        -----
        Items with fewer than 3 observed responses are skipped. Their
        estimated parameters are set to defaults (a=1.0, b=0.0) with
        very high standard errors to indicate unreliability.
        """

        n_students, n_items = response_matrix.shape
        print(f"IRT fit: {n_students} students, {n_items} items")

        # Step 1: Initialize student abilities from raw accuracy
        # (proportion correct, mapped to theta scale)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw_accuracy = np.nanmean(response_matrix, axis=1)

        # Map accuracy [0, 1] to theta [-3, 3], clipping extremes
        raw_accuracy = np.clip(raw_accuracy, 0.05, 0.95)
        thetas = 4 * raw_accuracy - 2  # linear: 0->-2, 0.5->0, 1->2

        # Step 2: EM iterations - alternate between estimating item params
        # (M-step) and updating student abilities (E-step)
        prev_log_lik = -np.inf

        for iteration in range(max_em_iterations):

            # M-step: fit each item's parameters given current thetas
            item_params_new = {}

            for j, qid in enumerate(question_ids):
                col = response_matrix[:, j]
                observed_mask = ~np.isnan(col)
                n_observed = observed_mask.sum()

                if n_observed < 3:
                    # Not enough data - use defaults with high uncertainty
                    item_params_new[qid] = {
                        "a": 1.0, "b": 0.0,
                        "se_a": 99.0, "se_b": 99.0,
                        "n_responses": int(n_observed),
                        "reliable": False
                    }
                    continue

                obs_responses = col[observed_mask]
                obs_thetas = thetas[observed_mask]

                result = minimize(
                    fun=_neg_log_likelihood,
                    x0=[1.0, 0.0],
                    args=(obs_responses, obs_thetas),
                    method="L-BFGS-B",
                    bounds=[(0.1, 4.0), (-4.0, 4.0)],
                    options={"maxiter": 100, "ftol": 1e-8}
                )

                a, b = result.x

                # Approximate standard errors from inverse Hessian diagonal
                # (scipy does not always provide this, so we fall back to None)
                try:
                    hess_inv = result.hess_inv.todense() if hasattr(
                        result.hess_inv, "todense"
                    ) else result.hess_inv
                    se_a = float(np.sqrt(abs(hess_inv[0, 0])))
                    se_b = float(np.sqrt(abs(hess_inv[1, 1])))
                except Exception:
                    se_a, se_b = 0.5, 0.5

                item_params_new[qid] = {
                    "a": round(float(a), 4),
                    "b": round(float(b), 4),
                    "se_a": round(se_a, 4),
                    "se_b": round(se_b, 4),
                    "n_responses": int(n_observed),
                    "reliable": n_observed >= 10
                }

            # E-step: update student abilities given new item parameters
            new_log_lik = 0.0

            for i in range(n_students):
                row = response_matrix[i, :]
                observed_mask = ~np.isnan(row)

                if observed_mask.sum() == 0:
                    continue

                obs_responses = row[observed_mask]
                obs_qids = [question_ids[j] for j in range(n_items) if observed_mask[j]]

                def neg_theta_ll(theta_val):
                    ll = 0.0
                    for resp, qid in zip(obs_responses, obs_qids):
                        params = item_params_new.get(qid, {"a": 1.0, "b": 0.0})
                        p = _two_pl_prob(theta_val[0], params["a"], params["b"])
                        p = np.clip(p, 1e-9, 1 - 1e-9)
                        ll += resp * np.log(p) + (1 - resp) * np.log(1 - p)
                    # Normal prior on theta: N(0, 1)
                    ll -= 0.5 * theta_val[0] ** 2
                    return -ll

                theta_result = minimize(
                    neg_theta_ll, x0=[thetas[i]],
                    method="L-BFGS-B", bounds=[(-4.0, 4.0)]
                )
                thetas[i] = theta_result.x[0]
                new_log_lik -= theta_result.fun

            # Check convergence
            delta = abs(new_log_lik - prev_log_lik)
            print(f"  EM iteration {iteration + 1}: log-lik = {new_log_lik:.2f} (delta={delta:.4f})")

            self.item_params = item_params_new

            if delta < convergence_tol and iteration > 0:
                print(f"  Converged after {iteration + 1} iterations.")
                break

            prev_log_lik = new_log_lik

        self.is_fitted = True
        print(f"IRT fit complete. {len(self.item_params)} items fitted.")

        # Report reliability
        reliable_count = sum(
            1 for p in self.item_params.values() if p.get("reliable", False)
        )
        print(
            f"  {reliable_count}/{len(self.item_params)} items have reliable "
            f"estimates (>=10 responses)."
        )

    def get_student_ability(
        self, student_responses: Dict[str, int]
    ) -> float:
        """
        Estimate a student's ability (theta) given their observed responses.

        Parameters
        ----------
        student_responses : dict
            Maps question_id -> 1 (correct) or 0 (wrong).
            Questions not in the dict are treated as not attempted.

        Returns
        -------
        float
            Estimated theta (ability). Range approximately -3 to +3.
            Returns 0.0 if no responses are provided.
        """

        if not student_responses or not self.is_fitted:
            return 0.0

        known_qids = [
            qid for qid in student_responses
            if qid in self.item_params
        ]

        if not known_qids:
            return 0.0

        def neg_theta_ll(theta_val):
            ll = 0.0
            for qid in known_qids:
                resp = student_responses[qid]
                params = self.item_params[qid]
                p = _two_pl_prob(theta_val[0], params["a"], params["b"])
                p = np.clip(p, 1e-9, 1 - 1e-9)
                ll += resp * np.log(p) + (1 - resp) * np.log(1 - p)
            ll -= 0.5 * theta_val[0] ** 2  # Normal(0,1) prior
            return -ll

        result = minimize(
            neg_theta_ll, x0=[0.0],
            method="L-BFGS-B", bounds=[(-4.0, 4.0)]
        )

        return round(float(result.x[0]), 4)

    def get_item_params(self, question_id: str) -> Optional[dict]:
        """
        Get the fitted parameters for a specific question.

        Returns None if the question has not been fitted.
        If reliable=False, the estimates should be treated with caution.
        """

        return self.item_params.get(question_id)

    def save(self, path: Optional[Path] = None):
        """Save fitted parameters to a JSON file."""

        if not self.is_fitted:
            raise RuntimeError("Cannot save: model has not been fitted yet.")

        save_path = path or (ARTIFACTS_DIR / "irt_params.json")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "w") as f:
            json.dump(self.item_params, f, indent=2)

        print(f"IRT parameters saved to {save_path}")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "IRTModel":
        """Load fitted parameters from a JSON file."""

        load_path = path or (ARTIFACTS_DIR / "irt_params.json")

        if not load_path.exists():
            raise FileNotFoundError(
                f"IRT params not found at {load_path}. "
                "Run IRT fitting first."
            )

        model = cls()

        with open(load_path, "r") as f:
            model.item_params = json.load(f)

        model.is_fitted = True
        return model


# ---------------------------------------------------------------------------
# Multidimensional IRT (MIRT): 3-Dimensional Ability Vector
# ---------------------------------------------------------------------------

class MultidimensionalIRT:
    """
    Multidimensional Item Response Theory (MIRT) model.

    Estimates a 3-dimensional ability vector for each student:
        theta_conceptual  - Conceptual understanding and theory recall
        theta_numerical   - Numerical computation and problem solving
        theta_analytical  - Analytical reasoning and application

    Each dimension is estimated independently using the same 2PL IRT
    framework, partitioning questions by their primary cognitive demand.

    Skill classification heuristics:
        conceptual  - questions tagged with theory, definition, principle, law, concept
        numerical   - questions with calculation, formula, compute, value, find
        analytical  - questions with analyze, apply, design, interpret, derive
        (unclassified questions contribute to all three dimensions equally)

    Usage:
        mirt = MultidimensionalIRT()
        theta_vector = mirt.estimate_theta(question_results)
        # returns {"theta_conceptual": float, "theta_numerical": float,
        #          "theta_analytical": float, "composite_theta": float}
    """

    # Keywords that indicate a question's primary cognitive dimension
    CONCEPTUAL_KEYWORDS = {
        "define", "definition", "concept", "principle", "law", "theory",
        "state", "describe", "explain", "what is", "which of", "property",
        "characteristic", "type", "classification"
    }
    NUMERICAL_KEYWORDS = {
        "calculate", "compute", "find", "value", "evaluate", "solve",
        "determine", "how much", "how many", "numerical", "formula",
        "equation", "integral", "derivative", "sum", "product"
    }
    ANALYTICAL_KEYWORDS = {
        "analyze", "analyse", "apply", "design", "interpret", "derive",
        "predict", "infer", "compare", "relate", "justify", "effect",
        "impact", "reason", "why", "how does", "consequence"
    }

    def _classify_question(self, question_text: str, skill: str = "") -> str:
        """
        Classify a question into conceptual / numerical / analytical.

        Returns 'conceptual', 'numerical', 'analytical', or 'all'
        (if no clear signal, the question contributes to all dimensions).
        """
        combined = (question_text + " " + skill).lower()

        conceptual_score = sum(1 for kw in self.CONCEPTUAL_KEYWORDS if kw in combined)
        numerical_score = sum(1 for kw in self.NUMERICAL_KEYWORDS if kw in combined)
        analytical_score = sum(1 for kw in self.ANALYTICAL_KEYWORDS if kw in combined)

        max_score = max(conceptual_score, numerical_score, analytical_score)
        if max_score == 0:
            return "all"

        if conceptual_score == max_score:
            return "conceptual"
        if numerical_score == max_score:
            return "numerical"
        return "analytical"

    def _estimate_1d_theta(
        self,
        responses: list,  # list of (is_correct: bool, difficulty: int)
    ) -> float:
        """
        Estimate scalar theta from a list of (is_correct, difficulty) pairs.

        Uses a simplified MAP estimate:
            - difficulty 1-5 maps to IRT b parameter: b = (difficulty - 3) * 0.75
            - discrimination a = 1.0 for all items (1PL fallback)
            - prior: theta ~ N(0, 1)

        Returns 0.0 if no responses are available.
        """
        if not responses:
            return 0.0

        # Convert difficulty (1-5) to IRT b scale (-1.5 to +1.5)
        def b_from_difficulty(d: int) -> float:
            return (d - 3) * 0.75

        def neg_log_posterior(theta_arr):
            theta = theta_arr[0]
            ll = 0.0
            for is_correct, difficulty in responses:
                b = b_from_difficulty(difficulty)
                # 2PL with a=1.0
                p = float(expit(1.0 * (theta - b)))
                p = max(1e-9, min(1 - 1e-9, p))
                ll += (1.0 if is_correct else 0.0) * np.log(p)
                ll += (0.0 if is_correct else 1.0) * np.log(1 - p)
            # Normal(0, 1) prior on theta
            ll -= 0.5 * theta ** 2
            return -ll

        result = minimize(
            neg_log_posterior, x0=[0.0],
            method="L-BFGS-B", bounds=[(-4.0, 4.0)]
        )
        return round(float(result.x[0]), 4)

    def estimate_theta(self, question_results: list) -> dict:
        """
        Estimate the 3D theta vector from a list of question result dicts.

        Each element of question_results should have:
            - is_correct: bool
            - difficulty: int (1-5)
            - question_text: str
            - skill: str (optional)

        Returns a dict:
            {
              "theta_conceptual": float,
              "theta_numerical": float,
              "theta_analytical": float,
              "composite_theta": float,
              "n_conceptual": int,
              "n_numerical": int,
              "n_analytical": int,
            }
        """
        conceptual_responses = []
        numerical_responses = []
        analytical_responses = []

        for qr in question_results:
            is_correct = bool(qr.get("is_correct", False))
            difficulty = int(qr.get("difficulty", 3))
            q_text = str(qr.get("question_text", ""))
            skill = str(qr.get("skill", ""))

            dimension = self._classify_question(q_text, skill)

            if dimension == "conceptual":
                conceptual_responses.append((is_correct, difficulty))
            elif dimension == "numerical":
                numerical_responses.append((is_correct, difficulty))
            elif dimension == "analytical":
                analytical_responses.append((is_correct, difficulty))
            else:  # "all" - unclassified: contribute 1/3 weight to each dimension
                conceptual_responses.append((is_correct, difficulty))
                numerical_responses.append((is_correct, difficulty))
                analytical_responses.append((is_correct, difficulty))

        theta_c = self._estimate_1d_theta(conceptual_responses)
        theta_n = self._estimate_1d_theta(numerical_responses)
        theta_a = self._estimate_1d_theta(analytical_responses)

        # Composite theta: weighted average (equal weights, could be domain-tuned)
        composite = round((theta_c + theta_n + theta_a) / 3.0, 4)

        return {
            "theta_conceptual": theta_c,
            "theta_numerical": theta_n,
            "theta_analytical": theta_a,
            "composite_theta": composite,
            "n_conceptual": len(conceptual_responses),
            "n_numerical": len(numerical_responses),
            "n_analytical": len(analytical_responses),
        }
