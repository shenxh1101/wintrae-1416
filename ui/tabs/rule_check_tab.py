from typing import List, Dict
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTextEdit, QListWidget, QListWidgetItem, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from models import Conversation, ReviewResult, RuleType


class RuleCheckTab(QWidget):
    run_check_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.conversations: List[Conversation] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.summary_label = QLabel("待检查样本: 0 个会话")
        self.summary_label.setFont(self._bold_font())
        self.btn_run_check = QPushButton("执行自动规则检查")
        self.btn_run_check.setMinimumHeight(40)
        self.btn_run_check.setMinimumWidth(200)
        self.btn_run_check.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        self.btn_run_check.clicked.connect(lambda: self.run_check_requested.emit())
        top_bar.addWidget(self.summary_label)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_run_check)
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Horizontal)

        left_group = QGroupBox("规则检查结果汇总")
        left_layout = QVBoxLayout(left_group)
        self.summary_table = QTableWidget(0, 7)
        self.summary_table.setHorizontalHeaderLabels(
            ["会话ID", "客服", "系统评分", "违规项数", "超时回复", "禁用话术", "其他问题"])
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.itemSelectionChanged.connect(self._on_select_conv)
        left_layout.addWidget(self.summary_table)
        splitter.addWidget(left_group)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        detail_group = QGroupBox("详细违规信息")
        detail_layout = QVBoxLayout(detail_group)
        self.violation_list = QListWidget()
        detail_layout.addWidget(self.violation_list)
        right_layout.addWidget(detail_group, 1)

        chat_group = QGroupBox("违规证据/证据对话")
        chat_layout = QVBoxLayout(chat_group)
        self.evidence_text = QTextEdit()
        self.evidence_text.setReadOnly(True)
        chat_layout.addWidget(self.evidence_text)
        right_layout.addWidget(chat_group, 1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        legend = QLabel("检查规则: 超时回复(>180秒) | 未称呼客户 | 承诺模糊 | 禁用话术 | 未给解决方案")
        legend.setStyleSheet("color: #888;")
        legend.setAlignment(Qt.AlignCenter)
        layout.addWidget(legend)

    def _bold_font(self):
        f = QFont()
        f.setBold(True)
        return f

    def set_conversations(self, conversations: List[Conversation]):
        self.conversations = conversations
        self.summary_label.setText(f"待检查样本: {len(conversations)} 个会话")

    def _score_color(self, score: float) -> QColor:
        if score >= 90:
            return QColor("#4CAF50")
        elif score >= 80:
            return QColor("#FFC107")
        elif score >= 60:
            return QColor("#FF9800")
        else:
            return QColor("#F44336")

    def set_check_results(self, conversations: List[Conversation], results: Dict[str, ReviewResult]):
        self.conversations = conversations
        self.summary_table.setRowCount(len(conversations))

        for row, conv in enumerate(conversations):
            result = results.get(conv.conv_id)
            score = result.score if result else 100
            violations = result.violations if result else []

            score_item = QTableWidgetItem(f"{score:.0f}")
            score_item.setForeground(self._score_color(score))
            f = QFont()
            f.setBold(True)
            score_item.setFont(f)

            self.summary_table.setItem(row, 0, QTableWidgetItem(conv.conv_id))
            self.summary_table.setItem(row, 1, QTableWidgetItem(conv.agent_name))
            self.summary_table.setItem(row, 2, score_item)

            vcount_item = QTableWidgetItem(str(len(violations)))
            if len(violations) > 0:
                vcount_item.setForeground(QColor("#F44336"))
            self.summary_table.setItem(row, 3, vcount_item)

            has_timeout = any(v.rule_type == RuleType.TIMEOUT_REPLY for v in violations)
            has_forbidden = any(v.rule_type == RuleType.FORBIDDEN_WORDS for v in violations)

            self.summary_table.setItem(row, 4, QTableWidgetItem("⚠是" if has_timeout else ""))
            self.summary_table.setItem(row, 5, QTableWidgetItem("⚠是" if has_forbidden else ""))

            other = "，".join([
                v.rule_type.value for v in violations
                if v.rule_type not in [RuleType.TIMEOUT_REPLY, RuleType.FORBIDDEN_WORDS]
            ])
            self.summary_table.setItem(row, 6, QTableWidgetItem(other))

            self.summary_table.item(row, 0).setData(Qt.UserRole, conv.conv_id)

        avg_score = sum(results[c.conv_id].score for c in conversations) / max(len(conversations), 1)
        self.summary_label.setText(
            f"检查完成: {len(conversations)} 个会话 | 平均得分: {avg_score:.1f}"
        )

        self._current_results = results

    def _on_select_conv(self):
        rows = self.summary_table.selectionModel().selectedRows()
        if not rows or not hasattr(self, '_current_results'):
            return
        row = rows[0].row()
        conv_id_item = self.summary_table.item(row, 0)
        if conv_id_item is None:
            return
        conv_id = conv_id_item.data(Qt.UserRole)
        if not conv_id:
            return

        result = self._current_results.get(conv_id)
        conv = next((c for c in self.conversations if c.conv_id == conv_id), None)

        self.violation_list.clear()
        self.evidence_text.clear()

        if not result:
            return

        try:
            self.violation_list.itemClicked.disconnect()
        except Exception:
            pass
        for v in result.violations:
            item_text = f"[{v.rule_type.value}] (扣分:{v.severity}) - {v.description}"
            item = QListWidgetItem(item_text)
            item.setToolTip(v.evidence or "")
            item.setData(Qt.UserRole, v.evidence)
            if v.related_message_index is not None:
                item.setData(Qt.UserRole + 1, (conv, v.related_message_index))
            self.violation_list.addItem(item)

        self.violation_list.itemClicked.connect(self._on_select_violation)

    def _on_select_violation(self, item):
        evidence = item.data(Qt.UserRole)
        if evidence:
            self.evidence_text.setPlainText(evidence)

        conv_msg_data = item.data(Qt.UserRole + 1)
        if conv_msg_data:
            conv, msg_idx = conv_msg_data
            if conv and 0 <= msg_idx < len(conv.messages):
                start = max(0, msg_idx - 2)
                end = min(len(conv.messages), msg_idx + 3)
                context_msgs = conv.messages[start:end]
                lines = ["=== 相关对话上下文 ==="]
                for i, m in enumerate(context_msgs):
                    who = "📢 客户" if m.is_customer else "💬 客服"
                    lines.append(f"[{m.timestamp.strftime('%H:%M:%S')}] {who}")
                    lines.append(m.content)
                    lines.append("-" * 40)
                if evidence:
                    lines.insert(1, f"\n违规证据:\n{evidence}\n")
                self.evidence_text.setPlainText("\n".join(lines))
