import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime
import uuid

from models import Conversation, ReviewResult, Agent
from services import ImportService


@dataclass
class QualityBatch:
    batch_id: str
    batch_name: str
    created_time: str
    updated_time: str
    sampled_conv_ids: List[str] = field(default_factory=list)
    review_results: Dict[str, dict] = field(default_factory=dict)
    agents_data: List[dict] = field(default_factory=dict)
    conversations_data: List[dict] = field(default_factory=dict)
    sampling_params: Dict = field(default_factory=dict)
    note: str = ""
    rule_sets_snapshot: Dict[str, dict] = field(default_factory=dict)

    @staticmethod
    def create(batch_name: str,
               sampled_conversations: List[Conversation],
               all_conversations: List[Conversation],
               agents: List[Agent],
               review_results: Dict[str, ReviewResult],
               sampling_params: Dict = None,
               note: str = "") -> 'QualityBatch':
        from services import ConfigManager
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        batch_id = f"BATCH{datetime.now().strftime('%Y%m%d%H%M%S')}"

        conv_ids = [c.conv_id for c in sampled_conversations]

        rule_sets_snapshot = {}
        try:
            cm = ConfigManager()
            for rs in cm.get_rule_sets():
                rule_sets_snapshot[rs.rule_set_id] = {
                    'rule_set_id': rs.rule_set_id,
                    'name': rs.name,
                    'description': rs.description,
                    'shops': list(rs.shops),
                    'shifts': list(rs.shifts),
                    'reply_timeout': rs.reply_timeout,
                    'forbidden_words_count': len(rs.forbidden_words),
                    'forbidden_words_preview': rs.forbidden_words[:10],
                    'version': rs.version,
                    'is_default': rs.is_default,
                    'snapshot_time': now,
                }
        except Exception:
            pass

        review_dict = {}
        for cid, result in review_results.items():
            if cid in conv_ids:
                review_dict[cid] = {
                    'conv_id': result.conv_id,
                    'score': result.score,
                    'manual_score': result.manual_score,
                    'rule_set_id': getattr(result, 'rule_set_id', 'default'),
                    'rule_set_version': getattr(result, 'rule_set_version', '1.0'),
                    'violations': [
                        {
                            'rule_type': v.rule_type.name,
                            'rule_type_value': v.rule_type.value,
                            'description': v.description,
                            'severity': v.severity,
                            'related_message_index': v.related_message_index,
                            'evidence': v.evidence,
                        } for v in result.violations
                    ],
                    'labels': list(result.labels),
                    'is_excellent': result.is_excellent,
                    'key_snippets': list(result.key_snippets),
                    'reviewer_notes': result.reviewer_notes,
                    'reviewed_by': result.reviewed_by,
                    'review_time': result.review_time.strftime('%Y-%m-%d %H:%M:%S') if result.review_time else None,
                }

        agents_data = []
        for a in agents:
            agents_data.append({
                'agent_id': a.agent_id,
                'name': a.name,
                'shop': a.shop,
                'shift': a.shift.name,
                'shift_value': a.shift.value,
                'group': a.group,
                'join_date': a.join_date,
                'is_active': a.is_active,
            })

        conversations_data = []
        conv_map = {c.conv_id: c for c in all_conversations}
        for cid in conv_ids:
            c = conv_map.get(cid)
            if c:
                conversations_data.append({
                    'conv_id': c.conv_id,
                    'agent_id': c.agent_id,
                    'agent_name': c.agent_name,
                    'shop': c.shop,
                    'shift': c.shift.name,
                    'shift_value': c.shift.value,
                    'order_status': c.order_status.name,
                    'order_status_value': c.order_status.value,
                    'order_id': c.order_id,
                    'customer_nick': c.customer_nick,
                    'start_time': c.start_time.strftime('%Y-%m-%d %H:%M:%S') if c.start_time else None,
                    'end_time': c.end_time.strftime('%Y-%m-%d %H:%M:%S') if c.end_time else None,
                    'messages': [
                        {
                            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'sender': m.sender,
                            'sender_type': m.sender_type,
                            'content': m.content,
                            'is_customer': m.is_customer,
                        } for m in c.messages
                    ],
                    'tags': list(c.tags),
                })

        return QualityBatch(
            batch_id=batch_id,
            batch_name=batch_name,
            created_time=now,
            updated_time=now,
            sampled_conv_ids=conv_ids,
            review_results=review_dict,
            agents_data=agents_data,
            conversations_data=conversations_data,
            sampling_params=sampling_params or {},
            note=note,
            rule_sets_snapshot=rule_sets_snapshot,
        )

    def to_entities(self):
        from models import ShiftType, OrderStatus, RuleType, Message, RuleViolation
        agents = []
        for a in self.agents_data:
            agents.append(Agent(
                agent_id=a['agent_id'],
                name=a['name'],
                shop=a['shop'],
                shift=ShiftType[a['shift']],
                group=a.get('group', ''),
                join_date=a.get('join_date'),
                is_active=a.get('is_active', True),
            ))

        conversations = []
        for c in self.conversations_data:
            messages = []
            for m in c['messages']:
                try:
                    ts = datetime.strptime(m['timestamp'], '%Y-%m-%d %H:%M:%S')
                except Exception:
                    ts = datetime.now()
                messages.append(Message(
                    timestamp=ts,
                    sender=m['sender'],
                    sender_type=m['sender_type'],
                    content=m['content'],
                    is_customer=m.get('is_customer', False),
                ))
            try:
                st = datetime.strptime(c['start_time'], '%Y-%m-%d %H:%M:%S') if c.get('start_time') else None
                et = datetime.strptime(c['end_time'], '%Y-%m-%d %H:%M:%S') if c.get('end_time') else None
            except Exception:
                st = et = None

            conversations.append(Conversation(
                conv_id=c['conv_id'],
                agent_id=c['agent_id'],
                agent_name=c['agent_name'],
                shop=c['shop'],
                shift=ShiftType[c['shift']],
                order_status=OrderStatus[c['order_status']],
                order_id=c.get('order_id', ''),
                customer_nick=c.get('customer_nick', ''),
                start_time=st,
                end_time=et,
                messages=messages,
                tags=c.get('tags', []),
            ))

        review_results = {}
        for cid, r in self.review_results.items():
            violations = []
            for v in r.get('violations', []):
                try:
                    rt = RuleType[v['rule_type']]
                except Exception:
                    continue
                violations.append(RuleViolation(
                    rule_type=rt,
                    description=v.get('description', ''),
                    severity=v.get('severity', 0),
                    related_message_index=v.get('related_message_index'),
                    evidence=v.get('evidence', ''),
                ))

            try:
                rt = datetime.strptime(r['review_time'], '%Y-%m-%d %H:%M:%S') if r.get('review_time') else None
            except Exception:
                rt = None

            review_results[cid] = ReviewResult(
                conv_id=r['conv_id'],
                score=r.get('score', 100.0),
                manual_score=r.get('manual_score'),
                violations=violations,
                labels=r.get('labels', []),
                is_excellent=r.get('is_excellent', False),
                key_snippets=r.get('key_snippets', []),
                reviewer_notes=r.get('reviewer_notes', ''),
                reviewed_by=r.get('reviewed_by', ''),
                review_time=rt,
                rule_set_id=r.get('rule_set_id', 'default'),
                rule_set_version=r.get('rule_set_version', '1.0'),
            )

        return agents, conversations, review_results

    def update_with(self,
                    sampled_conversations: List = None,
                    all_conversations: List = None,
                    agents: List = None,
                    review_results: Dict = None,
                    sampling_params: Dict = None,
                    note: str = None,
                    batch_name: str = None) -> 'QualityBatch':
        from models import Conversation, Agent, ReviewResult, RuleType, Message, RuleViolation

        self.updated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if batch_name is not None:
            self.batch_name = batch_name
        if note is not None:
            self.note = note
        if sampling_params is not None:
            self.sampling_params = sampling_params

        if sampled_conversations is not None:
            self.sampled_conv_ids = [c.conv_id for c in sampled_conversations]

            if all_conversations is not None:
                conversations_data = []
                conv_map = {c.conv_id: c for c in all_conversations}
                for cid in self.sampled_conv_ids:
                    c = conv_map.get(cid)
                    if c:
                        conversations_data.append({
                            'conv_id': c.conv_id,
                            'agent_id': c.agent_id,
                            'agent_name': c.agent_name,
                            'shop': c.shop,
                            'shift': c.shift.name,
                            'shift_value': c.shift.value,
                            'order_status': c.order_status.name,
                            'order_status_value': c.order_status.value,
                            'order_id': c.order_id,
                            'customer_nick': c.customer_nick,
                            'start_time': c.start_time.strftime('%Y-%m-%d %H:%M:%S') if c.start_time else None,
                            'end_time': c.end_time.strftime('%Y-%m-%d %H:%M:%S') if c.end_time else None,
                            'messages': [
                                {
                                    'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                    'sender': m.sender,
                                    'sender_type': m.sender_type,
                                    'content': m.content,
                                    'is_customer': m.is_customer,
                                } for m in c.messages
                            ],
                            'tags': list(c.tags),
                        })
                self.conversations_data = conversations_data

            if agents is not None:
                agents_data = []
                for a in agents:
                    agents_data.append({
                        'agent_id': a.agent_id,
                        'name': a.name,
                        'shop': a.shop,
                        'shift': a.shift.name,
                        'shift_value': a.shift.value,
                        'group': a.group,
                        'join_date': a.join_date,
                        'is_active': a.is_active,
                    })
                self.agents_data = agents_data

        if review_results is not None:
            review_dict = {}
            for cid, result in review_results.items():
                if cid in self.sampled_conv_ids:
                    review_dict[cid] = {
                        'conv_id': result.conv_id,
                        'score': result.score,
                        'manual_score': result.manual_score,
                        'rule_set_id': getattr(result, 'rule_set_id', 'default'),
                        'rule_set_version': getattr(result, 'rule_set_version', '1.0'),
                        'violations': [
                            {
                                'rule_type': v.rule_type.name,
                                'rule_type_value': v.rule_type.value,
                                'description': v.description,
                                'severity': v.severity,
                                'related_message_index': v.related_message_index,
                                'evidence': v.evidence,
                            } for v in result.violations
                        ],
                        'labels': list(result.labels),
                        'is_excellent': result.is_excellent,
                        'key_snippets': list(result.key_snippets),
                        'reviewer_notes': result.reviewer_notes,
                        'reviewed_by': result.reviewed_by,
                        'review_time': result.review_time.strftime('%Y-%m-%d %H:%M:%S') if result.review_time else None,
                    }
            self.review_results = review_dict

        return self

    def get_review_progress(self):
        reviewed = sum(1 for r in self.review_results.values() if r.get('manual_score') is not None)
        total = len(self.sampled_conv_ids)
        return {
            'total': total,
            'reviewed': reviewed,
            'pending': total - reviewed,
            'progress': (reviewed / total * 100) if total > 0 else 0
        }


class BatchManager:
    _instance = None
    _batches_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'batches'
    )
    _index_file = os.path.join(_batches_dir, 'batch_index.json')

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        os.makedirs(self._batches_dir, exist_ok=True)
        self._load_index()

    def _load_index(self):
        if os.path.exists(self._index_file):
            try:
                with open(self._index_file, 'r', encoding='utf-8') as f:
                    self._index = json.load(f)
            except Exception:
                self._index = []
        else:
            self._index = []

    def _save_index(self):
        try:
            with open(self._index_file, 'w', encoding='utf-8') as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def list_batches(self) -> List[Dict]:
        return sorted(self._index, key=lambda x: x['created_time'], reverse=True)

    def save_batch(self, batch: QualityBatch) -> bool:
        try:
            file_path = os.path.join(self._batches_dir, f'{batch.batch_id}.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(batch), f, ensure_ascii=False, indent=2)

            existing = next((b for b in self._index if b['batch_id'] == batch.batch_id), None)
            index_entry = {
                'batch_id': batch.batch_id,
                'batch_name': batch.batch_name,
                'created_time': batch.created_time,
                'updated_time': batch.updated_time,
                'sample_count': len(batch.sampled_conv_ids),
                'reviewed_count': sum(1 for r in batch.review_results.values()
                                     if r.get('manual_score') is not None),
                'note': batch.note,
            }
            if existing:
                existing.update(index_entry)
            else:
                self._index.append(index_entry)
            self._save_index()
            return True
        except Exception as e:
            print(f"保存批次失败: {e}")
            return False

    def load_batch(self, batch_id: str) -> Optional[QualityBatch]:
        file_path = os.path.join(self._batches_dir, f'{batch_id}.json')
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return QualityBatch(**data)
        except Exception as e:
            print(f"加载批次失败: {e}")
            return None

    def update_batch_reviews(self, batch_id: str,
                             review_results: Dict[str, ReviewResult]) -> bool:
        batch = self.load_batch(batch_id)
        if not batch:
            return False

        for cid, result in review_results.items():
            if cid in batch.sampled_conv_ids:
                batch.review_results[cid] = {
                    'conv_id': result.conv_id,
                    'score': result.score,
                    'manual_score': result.manual_score,
                    'rule_set_id': getattr(result, 'rule_set_id', 'default'),
                    'rule_set_version': getattr(result, 'rule_set_version', '1.0'),
                    'violations': [
                        {
                            'rule_type': v.rule_type.name,
                            'rule_type_value': v.rule_type.value,
                            'description': v.description,
                            'severity': v.severity,
                            'related_message_index': v.related_message_index,
                            'evidence': v.evidence,
                        } for v in result.violations
                    ],
                    'labels': list(result.labels),
                    'is_excellent': result.is_excellent,
                    'key_snippets': list(result.key_snippets),
                    'reviewer_notes': result.reviewer_notes,
                    'reviewed_by': result.reviewed_by,
                    'review_time': result.review_time.strftime('%Y-%m-%d %H:%M:%S') if result.review_time else None,
                }

        batch.updated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.save_batch(batch)

    def delete_batch(self, batch_id: str) -> bool:
        file_path = os.path.join(self._batches_dir, f'{batch_id}.json')
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            self._index = [b for b in self._index if b['batch_id'] != batch_id]
            self._save_index()
            return True
        except Exception:
            return False

    def get_batches_dir(self) -> str:
        return self._batches_dir
