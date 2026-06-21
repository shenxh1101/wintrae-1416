from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QPushButton, QTabWidget, QWidget, QTextEdit, QMessageBox, QGroupBox,
    QFormLayout, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from services import ConfigManager, RuleConfig, RuleEngine, ReportService


class RuleConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("质检规则配置")
        self.setMinimumSize(700, 600)
        self.config_manager = ConfigManager()
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("质检规则参数配置")
        header.setFont(self._bold_font(14))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        hint = QLabel("修改后点击保存，新配置将立即生效并在下次打开工具时自动加载")
        hint.setStyleSheet("color: #666;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self._create_basic_tab()
        self._create_words_tab()
        self._create_threshold_tab()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.Reset
        )
        buttons.button(QDialogButtonBox.Save).setText("💾 保存配置")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.Reset).setText("↺ 恢复默认")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self._on_reset)
        layout.addWidget(buttons)

    def _bold_font(self, size=10):
        f = QFont()
        f.setBold(True)
        f.setPointSize(size)
        return f

    def _create_basic_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        timeout_group = QGroupBox("超时回复设置")
        t_layout = QFormLayout(timeout_group)
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(30, 600)
        self.spin_timeout.setSuffix(" 秒")
        self.spin_timeout.setSingleStep(10)
        self.spin_timeout.setToolTip("客户发送消息后，客服超过此秒数未回复即判定为超时")
        t_layout.addRow("超时阈值:", self.spin_timeout)
        layout.addWidget(timeout_group)

        greeting_group = QGroupBox("礼貌称呼识别模式（正则表达式，一行一个）")
        g_layout = QVBoxLayout(greeting_group)
        self.text_greeting = QTextEdit()
        self.text_greeting.setPlaceholderText("例如：\n亲[，,\\s]\n您好\n你好\n亲爱的\n尊敬的客户")
        g_layout.addWidget(self.text_greeting)
        layout.addWidget(greeting_group, 1)

        self.tabs.addTab(tab, "基础设置")

    def _create_words_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        forbidden_group = QGroupBox("禁用话术（一行一个，检测到即扣分）")
        f_layout = QVBoxLayout(forbidden_group)
        self.text_forbidden = QTextEdit()
        self.text_forbidden.setPlaceholderText("例如：\n不知道\n不清楚\n关我什么事\n随便投诉\n滚")
        f_layout.addWidget(self.text_forbidden)
        layout.addWidget(forbidden_group, 1)

        vague_group = QGroupBox("模糊承诺词（一行一个，累计2次以上扣分）")
        v_layout = QVBoxLayout(vague_group)
        self.text_vague = QTextEdit()
        self.text_vague.setPlaceholderText("例如：\n大概\n可能\n差不多\n尽快\n稍后\n不确定")
        v_layout.addWidget(self.text_vague)
        layout.addWidget(vague_group, 1)

        solution_group = QGroupBox("解决方案关键词（一行一个，用于判断是否给出解决方案）")
        s_layout = QVBoxLayout(solution_group)
        self.text_solution = QTextEdit()
        self.text_solution.setPlaceholderText("例如：\n可以\n帮您\n建议\n申请\n退款\n换货\n补偿")
        s_layout.addWidget(self.text_solution)
        layout.addWidget(solution_group, 1)

        self.tabs.addTab(tab, "关键词配置")

    def _create_threshold_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.spin_pass_threshold = QDoubleSpinBox()
        self.spin_pass_threshold.setRange(0, 100)
        self.spin_pass_threshold.setSuffix(" 分")
        self.spin_pass_threshold.setDecimals(1)
        self.spin_pass_threshold.setSingleStep(0.5)
        self.spin_pass_threshold.setToolTip("得分高于此值判定为合格")
        layout.addRow("合格分数线:", self.spin_pass_threshold)

        self.spin_attention_threshold = QDoubleSpinBox()
        self.spin_attention_threshold.setRange(0, 100)
        self.spin_attention_threshold.setSuffix(" 分")
        self.spin_attention_threshold.setDecimals(1)
        self.spin_attention_threshold.setSingleStep(0.5)
        self.spin_attention_threshold.setToolTip("得分低于此值需重点关注")
        layout.addRow("预警分数线:", self.spin_attention_threshold)

        self.spin_min_samples = QSpinBox()
        self.spin_min_samples.setRange(1, 20)
        self.spin_min_samples.setSuffix(" 个样本")
        self.spin_min_samples.setToolTip("判定待培训所需的最少样本数")
        layout.addRow("培训判定最小样本:", self.spin_min_samples)

        self.spin_pass_rate = QDoubleSpinBox()
        self.spin_pass_rate.setRange(0.1, 1.0)
        self.spin_pass_rate.setDecimals(2)
        self.spin_pass_rate.setSingleStep(0.05)
        self.spin_pass_rate.setToolTip("合格率低于此值进入待培训名单")
        layout.addRow("培训判定合格率:", self.spin_pass_rate)

        hint = QLabel(
            "评分说明：\n"
            "- 超时回复：每次扣5分，最高30分\n"
            "- 未称呼客户：扣10分\n"
            "- 承诺模糊：每2处扣3分，最高20分\n"
            "- 禁用话术：每处扣15分，最高50分\n"
            "- 未给解决方案：扣15分"
        )
        hint.setStyleSheet("background-color: #fff3e0; padding: 10px; border-radius: 5px;")
        layout.addRow(hint)

        self.tabs.addTab(tab, "阈值设置")

    def _load_config(self):
        cfg = self.config_manager.get_config()
        self.spin_timeout.setValue(cfg.reply_timeout)
        self.text_greeting.setPlainText("\n".join(cfg.greeting_patterns))
        self.text_forbidden.setPlainText("\n".join(cfg.forbidden_words))
        self.text_vague.setPlainText("\n".join(cfg.vague_phrases))
        self.text_solution.setPlainText("\n".join(cfg.solution_keywords))
        self.spin_pass_threshold.setValue(cfg.score_threshold_pass)
        self.spin_attention_threshold.setValue(cfg.score_threshold_attention)
        self.spin_min_samples.setValue(cfg.min_samples_for_training)
        self.spin_pass_rate.setValue(cfg.pass_rate_for_training)

    def _collect_config(self) -> RuleConfig:
        def parse_lines(text):
            return [line.strip() for line in text.split('\n') if line.strip()]

        return RuleConfig(
            reply_timeout=self.spin_timeout.value(),
            forbidden_words=parse_lines(self.text_forbidden.toPlainText()),
            greeting_patterns=parse_lines(self.text_greeting.toPlainText()),
            vague_phrases=parse_lines(self.text_vague.toPlainText()),
            solution_keywords=parse_lines(self.text_solution.toPlainText()),
            score_threshold_pass=self.spin_pass_threshold.value(),
            score_threshold_attention=self.spin_attention_threshold.value(),
            min_samples_for_training=self.spin_min_samples.value(),
            pass_rate_for_training=self.spin_pass_rate.value(),
        )

    def _on_save(self):
        try:
            new_config = self._collect_config()
            if not new_config.greeting_patterns:
                QMessageBox.warning(self, "提示", "礼貌称呼模式不能为空")
                return
            success = self.config_manager.update_config(new_config)
            if success:
                QMessageBox.information(self, "成功",
                    "配置已保存！\n\n后续规则检查和报告生成将使用新配置。\n\n"
                    f"配置文件路径:\n{self.config_manager.get_config_path()}")
                self.accept()
            else:
                QMessageBox.critical(self, "失败", "配置保存失败，请检查文件权限。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置时出错: {str(e)}")

    def _on_reset(self):
        reply = QMessageBox.question(self, "确认",
            "确定要恢复为默认配置吗？\n当前所有自定义设置将丢失。",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.config_manager.reset_to_default()
            self._load_config()
            QMessageBox.information(self, "已恢复", "已恢复为默认配置。")
