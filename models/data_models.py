from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class ShiftType(Enum):
    MORNING = "早班"
    AFTERNOON = "中班"
    NIGHT = "晚班"
    ALL = "全天"


class OrderStatus(Enum):
    PENDING_PAYMENT = "待付款"
    PENDING_SHIPMENT = "待发货"
    SHIPPED = "已发货"
    COMPLETED = "已完成"
    REFUNDING = "退款中"
    REFUNDED = "已退款"
    CANCELED = "已取消"


@dataclass
class Agent:
    agent_id: str
    name: str
    shop: str
    shift: ShiftType
    group: str = ""
    join_date: Optional[str] = None
    is_active: bool = True


@dataclass
class Message:
    timestamp: datetime
    sender: str
    sender_type: str
    content: str
    is_customer: bool = False


@dataclass
class Conversation:
    conv_id: str
    agent_id: str
    agent_name: str
    shop: str
    shift: ShiftType
    order_status: OrderStatus
    order_id: str = ""
    customer_nick: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    messages: List[Message] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0


class RuleType(Enum):
    TIMEOUT_REPLY = "超时回复"
    NO_GREETING = "未称呼客户"
    VAGUE_PROMISE = "承诺模糊"
    FORBIDDEN_WORDS = "禁用话术"
    NO_SOLUTION = "未给解决方案"


@dataclass
class RuleViolation:
    rule_type: RuleType
    description: str
    severity: int
    related_message_index: Optional[int] = None
    evidence: str = ""


@dataclass
class ReviewResult:
    conv_id: str
    score: float = 100.0
    manual_score: Optional[float] = None
    violations: List[RuleViolation] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    is_excellent: bool = False
    key_snippets: List[str] = field(default_factory=list)
    reviewer_notes: str = ""
    reviewed_by: str = ""
    review_time: Optional[datetime] = None


@dataclass
class QualityReport:
    report_date: str
    total_sampled: int = 0
    total_reviewed: int = 0
    avg_score: float = 0.0
    agent_scores: Dict[str, float] = field(default_factory=dict)
    problem_counts: Dict[str, int] = field(default_factory=dict)
    training_list: List[str] = field(default_factory=list)
    excellent_cases: List[str] = field(default_factory=list)
    rectification_items: List[Dict] = field(default_factory=dict)
    report_mode: str = "人工复核口径"
    final_score_map: Dict[str, float] = field(default_factory=dict)
