"""
Contextual Bandit for adaptive question selection using Thompson Sampling.

The bandit maintains Beta distribution parameters (alpha, beta) per
(skill, difficulty_bucket) pair, representing the belief about the
expected reward from selecting a question in that category.

Reward signal (proxy for learning gain):
  reward = p_correct * (1 - p_correct) * 4
  
This reward peaks at p_correct = 0.5 (Zone of Proximal Development).

Coverage bonus for unpracticed skills:
  bonus = 0.1 * max(0, 3 - skill_attempt_count) / 3

Status: IMPLEMENTED AND INTEGRATED
"""

import math
import random
import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ThompsonSamplingBandit:
    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self._arms: Dict[str, Dict[str, float]] = {}
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta
    
    def _arm_key(self, skill: str, difficulty: int) -> str:
        if difficulty <= 2:
            bucket = "easy"
        elif difficulty == 3:
            bucket = "medium"
        else:
            bucket = "hard"
        return f"{skill}::{bucket}"
    
    def sample_theta(self, db: Session, skill: str, difficulty: int) -> float:
        key = self._arm_key(skill, difficulty)
        from app.models.bandit_state import BanditState
        arm_state = db.query(BanditState).filter(BanditState.arm_key == key).first()
        alpha = arm_state.alpha if arm_state else self._prior_alpha
        beta = arm_state.beta if arm_state else self._prior_beta
        return random.betavariate(alpha, beta)
    
    def update(self, db: Session, skill: str, difficulty: int, was_correct: bool, attempt_id: Any, auto_commit: bool = True):
        key = self._arm_key(skill, difficulty)
        from app.models.bandit_state import BanditState
        from app.models.bandit_update import BanditUpdate
        import uuid
        
        if isinstance(attempt_id, str):
            attempt_id = uuid.UUID(attempt_id)
        
        # 1. Idempotency Check: Did we already process this attempt?
        existing_update = db.query(BanditUpdate).filter(BanditUpdate.question_attempt_id == attempt_id).first()
        if existing_update:
            logger.info(f"Bandit already updated for attempt {attempt_id}, skipping.")
            return

        # 2. Concurrency Control: Lock the specific arm row for update
        arm_state = db.query(BanditState).filter(BanditState.arm_key == key).with_for_update().first()
        
        if not arm_state:
            arm_state = BanditState(arm_key=key, alpha=self._prior_alpha, beta=self._prior_beta)
            db.add(arm_state)
            
        if was_correct:
            arm_state.alpha += 1.0
        else:
            arm_state.beta += 1.0
            
        # 3. Create the ledger record
        new_update = BanditUpdate(
            question_attempt_id=attempt_id,
            arm_key=key,
            outcome="correct" if was_correct else "incorrect"
        )
        db.add(new_update)
            
        if auto_commit: db.commit()
    
    def select_question(
        self,
        db: Session,
        eligible_questions: List[Any],
        student_context: Dict,
        answered_question_ids: set,
    ) -> Optional[Any]:
        
        if not eligible_questions:
            return None
        
        best_question = None
        best_score = -float("inf")
        
        skill_attempt_counts = student_context.get("skill_attempt_counts", {})
        p_correct_estimates = student_context.get("p_correct_estimates", {})
        
        for question in eligible_questions:
            q_id = str(question.id)
            
            if q_id in answered_question_ids:
                continue
            
            skill = question.skill or "unknown"
            difficulty = question.difficulty or 3
            
            p_correct = p_correct_estimates.get(q_id, 0.5)
            theta = self.sample_theta(db, skill, difficulty)
            
            zpd_reward = p_correct * (1.0 - p_correct) * 4.0
            
            skill_count = skill_attempt_counts.get(skill, 0)
            coverage_bonus = 0.1 * max(0, 3 - skill_count) / 3.0
            
            score = (zpd_reward * theta) + coverage_bonus
            
            if score > best_score:
                best_score = score
                best_question = question
        
        return best_question
    
    def get_state(self) -> Dict:
        return {"arms": self._arms, "prior_alpha": self._prior_alpha, "prior_beta": self._prior_beta}
    
    def load_state(self, state: Dict):
        self._arms = state.get("arms", {})
        self._prior_alpha = state.get("prior_alpha", 1.0)
        self._prior_beta = state.get("prior_beta", 1.0)


_global_bandit = ThompsonSamplingBandit()

def get_bandit() -> ThompsonSamplingBandit:
    return _global_bandit
