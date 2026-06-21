import json
import os
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional
from datetime import datetime
from models import RuleSet


DEFAULT_CONFIG = {
    'reply_timeout': 180,
    'forbidden_words': [
        '不知道', '不清楚', '不是我的问题', '关我什么事',
        '你自己看', '随便你', '不可能', '绝对不行',
        '我们不负责', '你投诉吧', '随便投诉',
        '神经病', '脑子有病', '滚', '傻逼', '白痴', '笨蛋',
    ],
    'greeting_patterns': [
        r'亲[，,\s]', r'您好', r'你好', r'亲亲', r'亲~',
        r'亲爱的', r'尊敬的客户', r'尊敬的顾客',
    ],
    'vague_phrases': [
        '大概', '可能', '差不多', '应该', '也许', '尽量',
        '尽快', '稍后', '过会儿', '有时间', '有空',
        '说不定', '估计', '预计', '不确定',
    ],
    'solution_keywords': [
        '可以', '帮您', '为您', '建议', '推荐',
        '申请', '处理', '解决', '安排', '补偿',
        '退款', '退货', '换货', '补发', '赠送',
        '优惠', '折扣', '减免',
    ],
    'score_threshold_pass': 80.0,
    'score_threshold_attention': 70.0,
    'min_samples_for_training': 2,
    'pass_rate_for_training': 0.6,
}


def _get_default_rule_set() -> RuleSet:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return RuleSet(
        rule_set_id="default",
        name="默认规则集",
        description="系统默认规则配置，适用于所有店铺和班次",
        shops=[],
        shifts=[],
        reply_timeout=DEFAULT_CONFIG['reply_timeout'],
        forbidden_words=list(DEFAULT_CONFIG['forbidden_words']),
        greeting_patterns=list(DEFAULT_CONFIG['greeting_patterns']),
        vague_phrases=list(DEFAULT_CONFIG['vague_phrases']),
        solution_keywords=list(DEFAULT_CONFIG['solution_keywords']),
        is_default=True,
        version="1.0",
        created_time=now,
        updated_time=now,
    )


@dataclass
class RuleConfig:
    reply_timeout: int = 180
    forbidden_words: List[str] = field(default_factory=list)
    greeting_patterns: List[str] = field(default_factory=list)
    vague_phrases: List[str] = field(default_factory=list)
    solution_keywords: List[str] = field(default_factory=list)
    score_threshold_pass: float = 80.0
    score_threshold_attention: float = 70.0
    min_samples_for_training: int = 2
    pass_rate_for_training: float = 0.6
    rule_sets: List[Dict] = field(default_factory=list)
    active_rule_set_id: str = "default"

    @staticmethod
    def default() -> 'RuleConfig':
        default_rs = _get_default_rule_set()
        return RuleConfig(
            reply_timeout=DEFAULT_CONFIG['reply_timeout'],
            forbidden_words=list(DEFAULT_CONFIG['forbidden_words']),
            greeting_patterns=list(DEFAULT_CONFIG['greeting_patterns']),
            vague_phrases=list(DEFAULT_CONFIG['vague_phrases']),
            solution_keywords=list(DEFAULT_CONFIG['solution_keywords']),
            score_threshold_pass=DEFAULT_CONFIG['score_threshold_pass'],
            score_threshold_attention=DEFAULT_CONFIG['score_threshold_attention'],
            min_samples_for_training=DEFAULT_CONFIG['min_samples_for_training'],
            pass_rate_for_training=DEFAULT_CONFIG['pass_rate_for_training'],
            rule_sets=[asdict(default_rs)],
            active_rule_set_id="default",
        )


class ConfigManager:
    _instance = None
    _config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'rule_config.json'
    )

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def __init__(self):
        pass

    def _load(self):
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'rule_sets' not in data or not data['rule_sets']:
                    data['rule_sets'] = [asdict(_get_default_rule_set())]
                    data['active_rule_set_id'] = 'default'
                self.config = RuleConfig(**data)
            except Exception as e:
                print(f"加载配置失败，使用默认配置: {e}")
                self.config = RuleConfig.default()
        else:
            self.config = RuleConfig.default()
            self._save()

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.config), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def get_config(self) -> RuleConfig:
        return self.config

    def update_config(self, new_config: RuleConfig) -> bool:
        self.config = new_config
        return self._save()

    def reset_to_default(self) -> bool:
        self.config = RuleConfig.default()
        return self._save()

    def get_config_path(self) -> str:
        return self._config_path

    def get_rule_sets(self) -> List[RuleSet]:
        return [RuleSet(**rs) for rs in self.config.rule_sets]

    def get_rule_set(self, rule_set_id: str) -> Optional[RuleSet]:
        for rs in self.config.rule_sets:
            if rs.get('rule_set_id') == rule_set_id:
                return RuleSet(**rs)
        return None

    def get_default_rule_set(self) -> RuleSet:
        for rs in self.config.rule_sets:
            if rs.get('is_default'):
                return RuleSet(**rs)
        return RuleSet(**(self.config.rule_sets[0])) if self.config.rule_sets else _get_default_rule_set()

    def get_rule_set_for_conversation(self, shop: str, shift: str) -> RuleSet:
        non_default_sets = []
        default_set = None
        for rs in self.config.rule_sets:
            rule_set = RuleSet(**rs)
            if rule_set.is_default:
                default_set = rule_set
            else:
                non_default_sets.append(rule_set)

        non_default_sets.sort(key=lambda r: (
            0 if r.shops else 1,
            0 if r.shifts else 1,
            len(r.shops) + len(r.shifts)
        ))

        for rule_set in non_default_sets:
            if rule_set.matches(shop, shift):
                return rule_set

        return default_set if default_set else _get_default_rule_set()

    def add_rule_set(self, rule_set: RuleSet) -> bool:
        for i, rs in enumerate(self.config.rule_sets):
            if rs.get('rule_set_id') == rule_set.rule_set_id:
                self.config.rule_sets[i] = asdict(rule_set)
                return self._save()
        self.config.rule_sets.append(asdict(rule_set))
        return self._save()

    def update_rule_set(self, rule_set_id: str, rule_set: RuleSet) -> bool:
        for i, rs in enumerate(self.config.rule_sets):
            if rs.get('rule_set_id') == rule_set_id:
                old_version = rs.get('version', '1.0')
                try:
                    parts = old_version.split('.')
                    major = int(parts[0])
                    minor = int(parts[1]) + 1 if len(parts) > 1 else 1
                    if minor >= 10:
                        major += 1
                        minor = 0
                    rule_set.version = f"{major}.{minor}"
                except Exception:
                    rule_set.version = "1.1"
                rule_set.updated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if rule_set.is_default:
                    for other_rs in self.config.rule_sets:
                        other_rs['is_default'] = False
                self.config.rule_sets[i] = asdict(rule_set)
                return self._save()
        return False

    def delete_rule_set(self, rule_set_id: str) -> bool:
        if rule_set_id == 'default':
            return False
        self.config.rule_sets = [
            rs for rs in self.config.rule_sets
            if rs.get('rule_set_id') != rule_set_id
        ]
        return self._save()

    def set_active_rule_set(self, rule_set_id: str) -> bool:
        for rs in self.config.rule_sets:
            if rs.get('rule_set_id') == rule_set_id:
                self.config.active_rule_set_id = rule_set_id
                return self._save()
        return False
