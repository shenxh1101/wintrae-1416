import json
import os
from dataclasses import dataclass, asdict, field
from typing import List


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

    @staticmethod
    def default() -> 'RuleConfig':
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
