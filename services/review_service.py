from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

from models import Conversation, ReviewResult, Agent


AVAILABLE_LABELS = [
    "服务态度好", "响应速度快", "专业度高", "沟通清晰",
    "问题解决彻底", "客户体验佳", "同理心强", "引导下单",
    "响应慢", "态度敷衍", "专业知识不足", "沟通效率低",
    "情绪化应对", "流程不熟", "承诺未兑现", "信息不准确",
    "需要跟进", "升级处理", "特殊案例",
]


class ReviewService:
    def __init__(self):
        self.results: Dict[str, ReviewResult] = {}
        self.available_labels = AVAILABLE_LABELS

    def initialize_review(self, conv_id: str, auto_violations=None, auto_score: float = 100.0):
        if conv_id not in self.results:
            self.results[conv_id] = ReviewResult(
                conv_id=conv_id,
                score=auto_score,
                violations=auto_violations or []
            )
        return self.results[conv_id]

    def update_score(self, conv_id: str, manual_score: float):
        if conv_id in self.results:
            self.results[conv_id].manual_score = manual_score
            self.results[conv_id].review_time = datetime.now()

    def add_label(self, conv_id: str, label: str):
        if conv_id in self.results:
            if label not in self.results[conv_id].labels:
                self.results[conv_id].labels.append(label)

    def remove_label(self, conv_id: str, label: str):
        if conv_id in self.results:
            if label in self.results[conv_id].labels:
                self.results[conv_id].labels.remove(label)

    def set_labels(self, conv_id: str, labels: List[str]):
        if conv_id in self.results:
            self.results[conv_id].labels = labels

    def toggle_excellent(self, conv_id: str, is_excellent: bool):
        if conv_id in self.results:
            self.results[conv_id].is_excellent = is_excellent

    def add_key_snippet(self, conv_id: str, snippet: str):
        if conv_id in self.results and snippet:
            self.results[conv_id].key_snippets.append(snippet)

    def remove_key_snippet(self, conv_id: str, index: int):
        if conv_id in self.results:
            if 0 <= index < len(self.results[conv_id].key_snippets):
                del self.results[conv_id].key_snippets[index]

    def set_reviewer_notes(self, conv_id: str, notes: str):
        if conv_id in self.results:
            self.results[conv_id].reviewer_notes = notes

    def set_reviewer(self, conv_id: str, reviewer: str):
        if conv_id in self.results:
            self.results[conv_id].reviewed_by = reviewer
            self.results[conv_id].review_time = datetime.now()

    def get_review(self, conv_id: str) -> Optional[ReviewResult]:
        return self.results.get(conv_id)

    def get_all_reviews(self) -> Dict[str, ReviewResult]:
        return self.results

    def get_review_progress(self, sampled_conv_ids: List[str]) -> Dict:
        total = len(sampled_conv_ids)
        reviewed = sum(1 for cid in sampled_conv_ids
                       if self.results.get(cid) and self.results[cid].manual_score is not None)
        return {
            'total': total,
            'reviewed': reviewed,
            'pending': total - reviewed,
            'progress': (reviewed / total * 100) if total > 0 else 0
        }

    def get_reviews_by_agent(self, conversations: List[Conversation]) -> Dict[str, List[ReviewResult]]:
        result = defaultdict(list)
        conv_map = {c.conv_id: c for c in conversations}
        for conv_id, review in self.results.items():
            conv = conv_map.get(conv_id)
            if conv:
                result[conv.agent_name].append(review)
        return dict(result)
