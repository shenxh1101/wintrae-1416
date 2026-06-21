import re
from typing import List, Tuple, Dict, Any
from datetime import timedelta

from models import Conversation, Message, RuleViolation, RuleType, RuleSet
from services.config_manager import ConfigManager


class RuleEngine:
    def __init__(self, config: dict = None):
        self.config_manager = ConfigManager()
        if config:
            self.reply_timeout = config.get('reply_timeout', 180)
            self.forbidden_words = config.get('forbidden_words', [
                '不知道', '不清楚', '不是我的问题', '关我什么事',
                '你自己看', '随便你', '不可能', '绝对不行',
                '我们不负责', '你投诉吧', '随便投诉',
                '神经病', '脑子有病', '滚', '傻逼', '白痴', '笨蛋',
            ])
            self.greeting_patterns = config.get('greeting_patterns', [
                r'亲[，,\s]', r'您好', r'你好', r'亲亲', r'亲~',
                r'亲爱的', r'尊敬的客户', r'尊敬的顾客',
            ])
            self.vague_phrases = config.get('vague_phrases', [
                '大概', '可能', '差不多', '应该', '也许', '尽量',
                '尽快', '稍后', '过会儿', '有时间', '有空',
                '说不定', '估计', '预计', '不确定',
            ])
            self.solution_keywords = config.get('solution_keywords', [
                '可以', '帮您', '为您', '建议', '推荐',
                '申请', '处理', '解决', '安排', '补偿',
                '退款', '退货', '换货', '补发', '赠送',
                '优惠', '折扣', '减免',
            ])
            self._current_rule_set = None
        else:
            self.reload_config()
            self._current_rule_set = None

    def reload_config(self):
        cfg = self.config_manager.get_config()
        self.reply_timeout = cfg.reply_timeout
        self.forbidden_words = list(cfg.forbidden_words)
        self.greeting_patterns = list(cfg.greeting_patterns)
        self.vague_phrases = list(cfg.vague_phrases)
        self.solution_keywords = list(cfg.solution_keywords)
        self._current_rule_set = None

    def _get_rule_set_for_conversation(self, conversation: Conversation) -> RuleSet:
        return self.config_manager.get_rule_set_for_conversation(
            conversation.shop,
            conversation.shift.value
        )

    def _apply_rule_set(self, rule_set: RuleSet):
        self._current_rule_set = rule_set
        self.reply_timeout = rule_set.reply_timeout
        self.forbidden_words = list(rule_set.forbidden_words)
        self.greeting_patterns = list(rule_set.greeting_patterns)
        self.vague_phrases = list(rule_set.vague_phrases)
        self.solution_keywords = list(rule_set.solution_keywords)

    def check_all(self, conversation: Conversation) -> Tuple[List[RuleViolation], RuleSet]:
        rule_set = self._get_rule_set_for_conversation(conversation)
        self._apply_rule_set(rule_set)

        violations = []
        violations.extend(self._check_timeout_reply(conversation))
        violations.extend(self._check_no_greeting(conversation))
        violations.extend(self._check_vague_promise(conversation))
        violations.extend(self._check_forbidden_words(conversation))
        violations.extend(self._check_no_solution(conversation))
        return violations, rule_set

    def check_all_with_meta(self, conversation: Conversation) -> Dict[str, Any]:
        violations, rule_set = self.check_all(conversation)
        score = self.calculate_score(violations)
        return {
            'violations': violations,
            'score': score,
            'rule_set_id': rule_set.rule_set_id,
            'rule_set_name': rule_set.name,
            'rule_set_version': rule_set.version,
        }

    def calculate_score(self, violations: List[RuleViolation]) -> float:
        score = 100.0
        for v in violations:
            score -= v.severity
        return max(0.0, min(100.0, score))

    def _check_timeout_reply(self, conversation: Conversation) -> List[RuleViolation]:
        violations = []
        messages = conversation.messages
        if len(messages) < 2:
            return violations

        timeout_count = 0
        last_customer_time = None
        last_evidence_idx = -1

        for i, msg in enumerate(messages):
            if msg.is_customer:
                last_customer_time = msg.timestamp
            elif last_customer_time and not msg.is_customer:
                delta = (msg.timestamp - last_customer_time).total_seconds()
                if delta > self.reply_timeout:
                    timeout_count += 1
                    last_evidence_idx = i
                last_customer_time = None

        if timeout_count > 0:
            severity = min(5 * timeout_count, 30)
            evidence = ""
            if 0 <= last_evidence_idx < len(messages):
                prev_idx = max(0, last_evidence_idx - 1)
                evidence = f"客户消息: {messages[prev_idx].content[:50]}\n客服回复: {messages[last_evidence_idx].content[:50]}"
            violations.append(RuleViolation(
                rule_type=RuleType.TIMEOUT_REPLY,
                description=f"检测到 {timeout_count} 次超时回复（阈值: {self.reply_timeout}秒，规则集: {self._current_rule_set.name if self._current_rule_set else '默认'}）",
                severity=severity,
                related_message_index=last_evidence_idx if last_evidence_idx >= 0 else None,
                evidence=evidence
            ))
        return violations

    def _check_no_greeting(self, conversation: Conversation) -> List[RuleViolation]:
        violations = []
        agent_messages = [m for m in conversation.messages if not m.is_customer]
        if not agent_messages:
            return violations

        first_few = agent_messages[:min(3, len(agent_messages))]
        has_greeting = False
        for msg in first_few:
            content = msg.content
            for pattern in self.greeting_patterns:
                if re.search(pattern, content):
                    has_greeting = True
                    break
            if has_greeting:
                break

        if not has_greeting and len(conversation.messages) >= 2:
            violations.append(RuleViolation(
                rule_type=RuleType.NO_GREETING,
                description="前3条客服消息中未检测到礼貌称呼（如：亲、您好、亲爱的等）",
                severity=10,
                related_message_index=conversation.messages.index(agent_messages[0]) if agent_messages[0] in conversation.messages else None,
                evidence=f"客服首条消息: {agent_messages[0].content[:80]}"
            ))
        return violations

    def _check_vague_promise(self, conversation: Conversation) -> List[RuleViolation]:
        violations = []
        agent_messages = [(i, m) for i, m in enumerate(conversation.messages) if not m.is_customer]

        vague_count = 0
        last_idx = -1
        evidences = []

        for idx, msg in agent_messages:
            found_phrases = []
            for phrase in self.vague_phrases:
                if phrase in msg.content:
                    vague_count += 1
                    found_phrases.append(phrase)
                    last_idx = idx
            if found_phrases:
                evidences.append(f"[{', '.join(found_phrases)}] {msg.content[:60]}")

        if vague_count >= 2:
            severity = min(3 * vague_count, 20)
            violations.append(RuleViolation(
                rule_type=RuleType.VAGUE_PROMISE,
                description=f"检测到 {vague_count} 处模糊承诺用词（如：大概、可能、尽快等）",
                severity=severity,
                related_message_index=last_idx if last_idx >= 0 else None,
                evidence="\n".join(evidences[:3])
            ))
        return violations

    def _check_forbidden_words(self, conversation: Conversation) -> List[RuleViolation]:
        violations = []
        agent_messages = [(i, m) for i, m in enumerate(conversation.messages) if not m.is_customer]

        forbidden_found = []
        last_idx = -1

        for idx, msg in agent_messages:
            for word in self.forbidden_words:
                if word in msg.content:
                    forbidden_found.append((idx, word, msg.content[:60]))
                    last_idx = idx

        if forbidden_found:
            severity = min(15 * len(forbidden_found), 50)
            unique_words = list(set(w for _, w, _ in forbidden_found))
            evidence = "\n".join(
                [f"第{i+1}条消息 - [{word}]: {content}" for i, word, content in forbidden_found[:5]]
            )
            violations.append(RuleViolation(
                rule_type=RuleType.FORBIDDEN_WORDS,
                description=f"检测到禁用话术: {', '.join(unique_words)}",
                severity=severity,
                related_message_index=last_idx if last_idx >= 0 else None,
                evidence=evidence
            ))
        return violations

    def _check_no_solution(self, conversation: Conversation) -> List[RuleViolation]:
        violations = []
        customer_messages = [m for m in conversation.messages if m.is_customer]
        agent_messages = [m for m in conversation.messages if not m.is_customer]

        if len(customer_messages) == 0 or len(agent_messages) == 0:
            return violations

        question_keywords = ['?', '？', '怎么办', '怎么弄', '怎么处理', '为什么',
                            '怎么回事', '怎么解决', '可以吗', '能不能', '能不能帮']
        has_question = False
        for msg in customer_messages:
            for kw in question_keywords:
                if kw in msg.content:
                    has_question = True
                    break
            if has_question:
                break

        if not has_question:
            return violations

        last_agent_msgs = agent_messages[-min(5, len(agent_messages)):]
        has_solution = False
        for msg in last_agent_msgs:
            for kw in self.solution_keywords:
                if kw in msg.content:
                    has_solution = True
                    break
            if has_solution:
                break

        if not has_solution and len(agent_messages) >= 2:
            last_idx = conversation.messages.index(agent_messages[-1])
            violations.append(RuleViolation(
                rule_type=RuleType.NO_SOLUTION,
                description="客户提出问题后，客服未给出明确解决方案或行动建议",
                severity=15,
                related_message_index=last_idx,
                evidence=f"客服结尾消息: {agent_messages[-1].content[:80]}"
            ))
        return violations
