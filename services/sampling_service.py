import random
from typing import List, Dict, Optional, Set
from collections import defaultdict

from models import Conversation, Agent, ShiftType, OrderStatus


class SamplingService:
    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)

    @staticmethod
    def _filter_conversations(
        conversations: List[Conversation],
        shops: Optional[Set[str]] = None,
        shifts: Optional[Set[ShiftType]] = None,
        agent_ids: Optional[Set[str]] = None,
        order_statuses: Optional[Set[OrderStatus]] = None
    ) -> List[Conversation]:
        result = []
        for conv in conversations:
            if shops and conv.shop not in shops:
                continue
            if shifts and conv.shift not in shifts:
                continue
            if agent_ids and conv.agent_id not in agent_ids:
                continue
            if order_statuses and conv.order_status not in order_statuses:
                continue
            result.append(conv)
        return result

    def simple_random_sample(
        self,
        conversations: List[Conversation],
        count: int,
        shops: Optional[List[str]] = None,
        shifts: Optional[List[ShiftType]] = None,
        agent_ids: Optional[List[str]] = None,
        order_statuses: Optional[List[OrderStatus]] = None
    ) -> List[Conversation]:
        filtered = self._filter_conversations(
            conversations,
            set(shops) if shops else None,
            set(shifts) if shifts else None,
            set(agent_ids) if agent_ids else None,
            set(order_statuses) if order_statuses else None
        )
        count = min(count, len(filtered))
        if count <= 0:
            return []
        return random.sample(filtered, count)

    def stratified_sample(
        self,
        conversations: List[Conversation],
        per_stratum_count: int,
        stratify_by: str = 'agent',
        shops: Optional[List[str]] = None,
        shifts: Optional[List[ShiftType]] = None,
        agent_ids: Optional[List[str]] = None,
        order_statuses: Optional[List[OrderStatus]] = None
    ) -> List[Conversation]:
        filtered = self._filter_conversations(
            conversations,
            set(shops) if shops else None,
            set(shifts) if shifts else None,
            set(agent_ids) if agent_ids else None,
            set(order_statuses) if order_statuses else None
        )

        strata_map: Dict[str, List[Conversation]] = defaultdict(list)
        for conv in filtered:
            if stratify_by == 'agent':
                key = f"{conv.agent_id}|{conv.agent_name}"
            elif stratify_by == 'shop':
                key = conv.shop
            elif stratify_by == 'shift':
                key = conv.shift.value
            elif stratify_by == 'order_status':
                key = conv.order_status.value
            elif stratify_by == 'shop_shift':
                key = f"{conv.shop}|{conv.shift.value}"
            else:
                key = conv.agent_id
            strata_map[key].append(conv)

        result = []
        for stratum_convs in strata_map.values():
            count = min(per_stratum_count, len(stratum_convs))
            if count > 0:
                result.extend(random.sample(stratum_convs, count))
        return result

    def balanced_sample(
        self,
        conversations: List[Conversation],
        total_count: int,
        agents: List[Agent],
        shops: Optional[List[str]] = None,
        shifts: Optional[List[ShiftType]] = None
    ) -> List[Conversation]:
        if not agents:
            return self.simple_random_sample(conversations, total_count, shops, shifts)

        agent_set = set(a.agent_id for a in agents)
        if shops:
            agent_set = set(a.agent_id for a in agents if a.shop in shops)
        if shifts:
            agent_set = set(a.agent_id for a in agents if a.shift in shifts)

        per_agent = max(1, total_count // max(len(agent_set), 1))
        result = self.stratified_sample(
            conversations, per_agent, 'agent', shops, shifts, list(agent_set)
        )

        while len(result) < total_count:
            remaining = [c for c in conversations
                         if c.agent_id in agent_set and c not in result]
            if shops:
                remaining = [c for c in remaining if c.shop in shops]
            if shifts:
                remaining = [c for c in remaining if c.shift in shifts]
            if not remaining:
                break
            need = total_count - len(result)
            add = min(need, len(remaining))
            result.extend(random.sample(remaining, add))

        return result[:total_count]

    def get_available_filters(self, conversations: List[Conversation], agents: List[Agent]):
        shops = set()
        shifts = set()
        order_statuses = set()
        agent_map = {}

        for conv in conversations:
            shops.add(conv.shop)
            shifts.add(conv.shift)
            order_statuses.add(conv.order_status)

        for agent in agents:
            key = f"{agent.agent_id}|{agent.name}"
            agent_map[key] = agent
            shops.add(agent.shop)
            shifts.add(agent.shift)

        return {
            'shops': sorted(list(shops)),
            'shifts': sorted(list(shifts), key=lambda s: s.value),
            'order_statuses': sorted(list(order_statuses), key=lambda o: o.value),
            'agents': sorted(agent_map.items(), key=lambda x: x[1].name)
        }
