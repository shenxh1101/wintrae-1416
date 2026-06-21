from typing import List, Dict
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QTextEdit,
    QListWidget, QListWidgetItem, QCheckBox, QSpinBox, QLineEdit,
    QProgressBar, QFrame, QScrollArea, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QTextCursor

from models import Conversation, ReviewResult, RuleType
from services.review_service import AVAILABLE_LABELS


class ReviewTab(QWidget):
    submit_review_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.conversations: List[Conversation] = []
        self.results: Dict[str, ReviewResult] = {}
        self.current_conv_idx = -1
        self._init_ui()

    def _init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)

        progress_group = QGroupBox("复核进度")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("待复核: 0 / 0")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        left_layout.addWidget(progress_group)

        conv_group = QGroupBox("样本列表")
        conv_layout = QVBoxLayout(conv_group)
        self.conv_table = QTableWidget(0, 6)
        self.conv_table.setHorizontalHeaderLabels(
            ["会话ID", "客服", "系统分", "人工分", "状态", "标签"])
        self.conv_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.conv_table.setAlternatingRowColors(True)
        self.conv_table.itemSelectionChanged.connect(self._on_select_conv_row)
        conv_layout.addWidget(self.conv_table)
        left_layout.addWidget(conv_group, 1)

        nav_row = QHBoxLayout()
        self.btn_prev = QPushButton("← 上一条")
        self.btn_next = QPushButton("下一条 →")
        self.btn_prev.clicked.connect(self._on_prev)
        self.btn_next.clicked.connect(self._on_next)
        nav_row.addWidget(self.btn_prev)
        nav_row.addWidget(self.btn_next)
        left_layout.addLayout(nav_row)

        main_splitter.addWidget(left_widget)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(5, 5, 5, 5)

        info_bar = QFrame()
        info_bar.setFrameShape(QFrame.StyledPanel)
        info_layout = QHBoxLayout(info_bar)
        self.info_conv_id = QLabel("会话: -")
        self.info_agent = QLabel("客服: -")
        self.info_shop = QLabel("店铺: -")
        self.info_status = QLabel("订单状态: -")
        info_layout.addWidget(self.info_conv_id)
        info_layout.addWidget(self.info_agent)
        info_layout.addWidget(self.info_shop)
        info_layout.addWidget(self.info_status)
        center_layout.addWidget(info_bar)

        chat_group = QGroupBox("对话内容 (可右键选择关键对话)")
        chat_layout = QVBoxLayout(chat_group)
        self.chat_text = QTextEdit()
        self.chat_text.setReadOnly(True)
        self.chat_text.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_text.customContextMenuRequested.connect(self._on_chat_context_menu)
        chat_layout.addWidget(self.chat_text)
        center_layout.addWidget(chat_group, 2)

        snippet_group = QGroupBox("关键对话截取 (右键对话选择内容后添加)")
        snippet_layout = QVBoxLayout(snippet_group)
        self.snippet_list = QListWidget()
        snippet_btn_row = QHBoxLayout()
        self.btn_add_snippet = QPushButton("添加所选文本为关键对话")
        self.btn_remove_snippet = QPushButton("删除选中")
        self.btn_add_snippet.clicked.connect(self._on_add_snippet_from_selection)
        self.btn_remove_snippet.clicked.connect(self._on_remove_snippet)
        snippet_btn_row.addWidget(self.btn_add_snippet)
        snippet_btn_row.addWidget(self.btn_remove_snippet)
        snippet_layout.addWidget(self.snippet_list)
        snippet_layout.addLayout(snippet_btn_row)
        center_layout.addWidget(snippet_group, 1)

        main_splitter.addWidget(center_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)

        score_group = QGroupBox("评分")
        score_layout = QVBoxLayout(score_group)

        auto_row = QHBoxLayout()
        auto_row.addWidget(QLabel("系统评分:"))
        self.auto_score_label = QLabel("-")
        self.auto_score_label.setFont(self._bold_font())
        auto_row.addWidget(self.auto_score_label)
        auto_row.addStretch()
        score_layout.addLayout(auto_row)

        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("人工评分:"))
        self.manual_score_spin = QSpinBox()
        self.manual_score_spin.setRange(0, 100)
        self.manual_score_spin.setValue(100)
        self.manual_score_spin.setFont(self._bold_font())
        self.manual_score_spin.valueChanged.connect(self._on_score_changed)
        manual_row.addWidget(self.manual_score_spin)
        score_layout.addLayout(manual_row)

        slider_hint = QLabel("快速打分:")
        score_layout.addWidget(slider_hint)
        quick_scores_row = QHBoxLayout()
        for s in [100, 90, 80, 70, 60]:
            btn = QPushButton(f"{s}分")
            btn.clicked.connect(lambda checked, val=s: self.manual_score_spin.setValue(val))
            quick_scores_row.addWidget(btn)
        score_layout.addLayout(quick_scores_row)

        right_layout.addWidget(score_group)

        label_group = QGroupBox("标签分类")
        label_layout = QVBoxLayout(label_group)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        label_container = QWidget()
        self.label_checks_layout = QVBoxLayout(label_container)
        self.label_checkboxes = {}
        for label in AVAILABLE_LABELS:
            cb = QCheckBox(label)
            cb.stateChanged.connect(self._on_labels_changed)
            self.label_checkboxes[label] = cb
            self.label_checks_layout.addWidget(cb)
        scroll.setWidget(label_container)
        label_layout.addWidget(scroll)
        right_layout.addWidget(label_group, 1)

        excellent_row = QHBoxLayout()
        self.cb_excellent = QCheckBox("⭐ 标记为优秀案例")
        self.cb_excellent.stateChanged.connect(self._on_excellent_changed)
        excellent_row.addWidget(self.cb_excellent)
        right_layout.addLayout(excellent_row)

        notes_group = QGroupBox("复核备注")
        notes_layout = QVBoxLayout(notes_group)
        self.reviewer_input = QLineEdit()
        self.reviewer_input.setPlaceholderText("复核人姓名")
        self.reviewer_input.textChanged.connect(self._on_reviewer_changed)
        self.notes_text = QTextEdit()
        self.notes_text.setPlaceholderText("填写复核意见、改进建议...")
        self.notes_text.textChanged.connect(self._on_notes_changed)
        notes_layout.addWidget(QLabel("复核人:"))
        notes_layout.addWidget(self.reviewer_input)
        notes_layout.addWidget(QLabel("备注:"))
        notes_layout.addWidget(self.notes_text, 1)
        right_layout.addWidget(notes_group, 1)

        self.btn_submit = QPushButton("💾 保存复核结果")
        self.btn_submit.setMinimumHeight(45)
        self.btn_submit.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_submit.clicked.connect(self._on_submit)
        right_layout.addWidget(self.btn_submit)

        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 4)
        main_splitter.setStretchFactor(2, 2)

        layout = QVBoxLayout(self)
        layout.addWidget(main_splitter)

    def _bold_font(self):
        f = QFont()
        f.setBold(True)
        return f

    def _score_color(self, score):
        if score >= 90:
            return "#4CAF50"
        elif score >= 80:
            return "#FFC107"
        elif score >= 60:
            return "#FF9800"
        return "#F44336"

    def set_conversations(self, conversations: List[Conversation], results: Dict[str, ReviewResult]):
        self.conversations = conversations
        self.results = results
        self._refresh_table()
        if conversations:
            self._select_conv(0)

    def _refresh_table(self):
        self.conv_table.setRowCount(len(self.conversations))
        reviewed = 0
        for row, conv in enumerate(self.conversations):
            r = self.results.get(conv.conv_id)
            auto = r.score if r else 100
            manual = r.manual_score if r and r.manual_score is not None else None
            has_reviewed = manual is not None
            if has_reviewed:
                reviewed += 1

            auto_item = QTableWidgetItem(f"{auto:.0f}")
            auto_item.setForeground(QColor(self._score_color(auto)))
            manual_text = f"{manual:.0f}" if manual is not None else "-"
            manual_item = QTableWidgetItem(manual_text)
            if manual is not None:
                manual_item.setForeground(QColor(self._score_color(manual)))
                f = QFont()
                f.setBold(True)
                manual_item.setFont(f)

            status = "✅已复核" if has_reviewed else "⏳待复核"
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor("#4CAF50" if has_reviewed else "#FF9800"))

            labels_text = ", ".join(r.labels) if r else ""
            if r and r.is_excellent:
                labels_text = "⭐ " + labels_text

            self.conv_table.setItem(row, 0, QTableWidgetItem(conv.conv_id))
            self.conv_table.setItem(row, 1, QTableWidgetItem(conv.agent_name))
            self.conv_table.setItem(row, 2, auto_item)
            self.conv_table.setItem(row, 3, manual_item)
            self.conv_table.setItem(row, 4, status_item)
            self.conv_table.setItem(row, 5, QTableWidgetItem(labels_text))

            self.conv_table.item(row, 0).setData(Qt.UserRole, row)

        total = len(self.conversations)
        self.progress_bar.setValue(int(reviewed / max(total, 1) * 100))
        self.progress_label.setText(f"待复核: {total - reviewed} / {total}  (已完成 {reviewed})")

    def _on_select_conv_row(self):
        rows = self.conv_table.selectionModel().selectedRows()
        if rows:
            row_idx = rows[0].row()
            self._select_conv(row_idx)

    def _select_conv(self, idx: int):
        if not (0 <= idx < len(self.conversations)):
            return
        self.current_conv_idx = idx
        conv = self.conversations[idx]
        result = self.results.get(conv.conv_id)

        self.info_conv_id.setText(f"会话: {conv.conv_id}")
        self.info_agent.setText(f"客服: {conv.agent_name}")
        self.info_shop.setText(f"店铺: {conv.shop}")
        self.info_status.setText(f"订单: {conv.order_status.value}")

        self._render_chat(conv, result)

        auto = result.score if result else 100
        self.auto_score_label.setText(f"{auto:.0f}")
        self.auto_score_label.setStyleSheet(f"color: {self._score_color(auto)};")

        if result and result.manual_score is not None:
            self.manual_score_spin.setValue(int(result.manual_score))
        else:
            self.manual_score_spin.setValue(int(auto))

        for label, cb in self.label_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(result and label in result.labels)
            cb.blockSignals(False)

        self.cb_excellent.blockSignals(True)
        self.cb_excellent.setChecked(result.is_excellent if result else False)
        self.cb_excellent.blockSignals(False)

        self.snippet_list.clear()
        if result:
            for s in result.key_snippets:
                self.snippet_list.addItem(QListWidgetItem(s))

        self.reviewer_input.blockSignals(True)
        self.reviewer_input.setText(result.reviewed_by if result else "")
        self.reviewer_input.blockSignals(False)

        self.notes_text.blockSignals(True)
        self.notes_text.setPlainText(result.reviewer_notes if result else "")
        self.notes_text.blockSignals(False)

        self.conv_table.selectRow(idx)

    def _render_chat(self, conv: Conversation, result):
        self.chat_text.clear()
        cursor = self.chat_text.textCursor()

        if result:
            for v in result.violations:
                cursor.insertHtml(
                    f'<div style="background:#ffebee; color:#c62828; padding:8px; margin:5px 0; '
                    f'border-left:4px solid #c62828;">'
                    f'<b>[{v.rule_type.value}]</b> 扣{v.severity}分 - {v.description}'
                    f'</div>'
                )

        for i, msg in enumerate(conv.messages):
            if msg.is_customer:
                bg = "#e3f2fd"
                border_color = "#2196F3"
                align = "left"
                who = f"📢 客户 ({msg.sender})"
            else:
                bg = "#f1f8e9"
                border_color = "#8BC34A"
                align = "right"
                who = f"💬 客服 ({msg.sender})"
            ts = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else ""
            content_html = msg.content.replace('\n', '<br>')
            html = (
                f'<div style="background:{bg}; padding:10px; margin:6px 0; '
                f'border-radius:8px; border-left:4px solid {border_color};" '
                f'data-msg-idx="{i}">'
                f'<div style="color:#888; font-size:11px;">{who} · {ts}</div>'
                f'<div style="margin-top:4px;">{content_html}</div>'
                f'</div>'
            )
            cursor.insertHtml(html)

        self.chat_text.moveCursor(QTextCursor.Start)

    def _on_prev(self):
        if self.current_conv_idx > 0:
            self._select_conv(self.current_conv_idx - 1)

    def _on_next(self):
        if self.current_conv_idx < len(self.conversations) - 1:
            self._select_conv(self.current_conv_idx + 1)

    def _on_chat_context_menu(self, pos):
        pass

    def _on_add_snippet_from_selection(self):
        text = self.chat_text.textCursor().selectedText().strip()
        if text:
            item = QListWidgetItem(text[:300])
            item.setData(Qt.UserRole, text)
            self.snippet_list.addItem(item)
            self._mark_dirty()

    def _on_remove_snippet(self):
        for item in self.snippet_list.selectedItems():
            self.snippet_list.takeItem(self.snippet_list.row(item))
        self._mark_dirty()

    def _on_score_changed(self):
        self._mark_dirty()

    def _on_labels_changed(self):
        self._mark_dirty()

    def _on_excellent_changed(self):
        self._mark_dirty()

    def _on_notes_changed(self):
        self._mark_dirty()

    def _on_reviewer_changed(self):
        self._mark_dirty()

    def _mark_dirty(self):
        pass

    def _collect_current_snippets(self):
        snippets = []
        for i in range(self.snippet_list.count()):
            item = self.snippet_list.item(i)
            data = item.data(Qt.UserRole)
            snippets.append(data if data else item.text())
        return snippets

    def _collect_selected_labels(self):
        return [label for label, cb in self.label_checkboxes.items() if cb.isChecked()]

    def _on_submit(self):
        if self.current_conv_idx < 0 or self.current_conv_idx >= len(self.conversations):
            return
        conv = self.conversations[self.current_conv_idx]
        data = {
            'conv_id': conv.conv_id,
            'manual_score': float(self.manual_score_spin.value()),
            'labels': self._collect_selected_labels(),
            'is_excellent': self.cb_excellent.isChecked(),
            'key_snippets': self._collect_current_snippets(),
            'reviewer_notes': self.notes_text.toPlainText(),
            'reviewed_by': self.reviewer_input.text().strip(),
        }
        self.submit_review_requested.emit(data)
        self._refresh_table()
