from typing import List, Dict
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QTextEdit,
    QListWidget, QListWidgetItem, QCheckBox, QSpinBox, QLineEdit,
    QProgressBar, QFrame, QScrollArea, QDialog, QDialogButtonBox,
    QComboBox, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QTextCursor

from models import Conversation, ReviewResult, RuleType
from services.review_service import AVAILABLE_LABELS


class ReviewTab(QWidget):
    submit_review_requested = pyqtSignal(dict)
    batch_update_requested = pyqtSignal(list, dict)

    def __init__(self):
        super().__init__()
        self.conversations: List[Conversation] = []
        self.results: Dict[str, ReviewResult] = {}
        self.filtered_conversations: List[Conversation] = []
        self.current_conv_idx = -1
        self._init_ui()

    def _init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)

        filter_group = QGroupBox("筛选条件")
        filter_layout = QVBoxLayout(filter_group)

        filter_row1 = QHBoxLayout()
        filter_row1.addWidget(QLabel("客服:"))
        self.filter_agent = QComboBox()
        self.filter_agent.addItem("全部客服")
        self.filter_agent.currentIndexChanged.connect(self._apply_filters)
        filter_row1.addWidget(self.filter_agent, 1)

        filter_row1.addWidget(QLabel("状态:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems(["全部", "待复核", "已复核"])
        self.filter_status.currentIndexChanged.connect(self._apply_filters)
        filter_row1.addWidget(self.filter_status, 1)
        filter_layout.addLayout(filter_row1)

        filter_row2 = QHBoxLayout()
        filter_row2.addWidget(QLabel("问题类型:"))
        self.filter_problem = QComboBox()
        self.filter_problem.addItem("全部问题")
        for rt in RuleType:
            self.filter_problem.addItem(rt.value)
        self.filter_problem.currentIndexChanged.connect(self._apply_filters)
        filter_row2.addWidget(self.filter_problem, 1)

        self.btn_clear_filter = QPushButton("清除筛选")
        self.btn_clear_filter.clicked.connect(self._clear_filters)
        filter_row2.addWidget(self.btn_clear_filter)
        filter_layout.addLayout(filter_row2)

        left_layout.addWidget(filter_group)

        progress_group = QGroupBox("复核进度")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("待复核: 0 / 0")
        self.filtered_label = QLabel("")
        self.filtered_label.setStyleSheet("color: #666; font-size: 11px;")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.filtered_label)
        left_layout.addWidget(progress_group)

        batch_group = QGroupBox("批量操作")
        batch_layout = QVBoxLayout(batch_group)

        batch_row = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_select_none = QPushButton("取消")
        self.btn_select_none.clicked.connect(self._select_none)
        batch_row.addWidget(self.btn_select_all)
        batch_row.addWidget(self.btn_select_none)
        batch_layout.addLayout(batch_row)

        batch_row2 = QHBoxLayout()
        self.btn_batch_label = QPushButton("🏷️ 批量打标签")
        self.btn_batch_label.clicked.connect(self._on_batch_label)
        self.btn_batch_training = QPushButton("⚠️ 批量标记需培训")
        self.btn_batch_training.clicked.connect(self._on_batch_training)
        batch_row2.addWidget(self.btn_batch_label)
        batch_row2.addWidget(self.btn_batch_training)
        batch_layout.addLayout(batch_row2)

        left_layout.addWidget(batch_group)

        conv_group = QGroupBox("样本列表 (可多选)")
        conv_layout = QVBoxLayout(conv_group)
        self.conv_table = QTableWidget(0, 7)
        self.conv_table.setHorizontalHeaderLabels(
            ["☑️", "会话ID", "客服", "系统分", "人工分", "状态", "标签"])
        self.conv_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.conv_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.conv_table.setAlternatingRowColors(True)
        self.conv_table.setSelectionMode(QTableWidget.ExtendedSelection)
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
        self.filtered_conversations = list(conversations)

        self.filter_agent.blockSignals(True)
        self.filter_agent.clear()
        self.filter_agent.addItem("全部客服")
        agents = sorted(set(c.agent_name for c in conversations))
        for agent in agents:
            self.filter_agent.addItem(agent)
        self.filter_agent.blockSignals(False)

        self._refresh_table()
        if conversations:
            self._select_conv(0)

    def _refresh_table(self):
        conversations = self.filtered_conversations
        self.conv_table.setRowCount(len(conversations))
        reviewed = 0
        for row, conv in enumerate(conversations):
            r = self.results.get(conv.conv_id)
            auto = r.score if r else 100
            manual = r.manual_score if r and r.manual_score is not None else None
            has_reviewed = manual is not None
            if has_reviewed:
                reviewed += 1

            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Unchecked)
            self.conv_table.setItem(row, 0, checkbox_item)

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

            self.conv_table.setItem(row, 1, QTableWidgetItem(conv.conv_id))
            self.conv_table.setItem(row, 2, QTableWidgetItem(conv.agent_name))
            self.conv_table.setItem(row, 3, auto_item)
            self.conv_table.setItem(row, 4, manual_item)
            self.conv_table.setItem(row, 5, status_item)
            self.conv_table.setItem(row, 6, QTableWidgetItem(labels_text))

            self.conv_table.item(row, 1).setData(Qt.UserRole, row)

        total = len(self.conversations)
        self.progress_bar.setValue(int(reviewed / max(total, 1) * 100))
        self.progress_label.setText(f"待复核: {total - reviewed} / {total}  (已完成 {reviewed})")

        if len(self.filtered_conversations) != len(self.conversations):
            self.filtered_label.setText(f"筛选后显示: {len(self.filtered_conversations)} 条")
        else:
            self.filtered_label.setText("")

    def _on_select_conv_row(self):
        rows = self.conv_table.selectionModel().selectedRows()
        if rows:
            row_idx = rows[0].row()
            self._select_conv(row_idx)

    def _select_conv(self, idx: int):
        if not (0 <= idx < len(self.filtered_conversations)):
            return
        self.current_conv_idx = idx
        conv = self.filtered_conversations[idx]
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
        if self.current_conv_idx < len(self.filtered_conversations) - 1:
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
        if self.current_conv_idx < 0 or self.current_conv_idx >= len(self.filtered_conversations):
            return
        conv = self.filtered_conversations[self.current_conv_idx]
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

    def _apply_filters(self):
        agent_filter = self.filter_agent.currentText()
        status_filter = self.filter_status.currentText()
        problem_filter = self.filter_problem.currentText()

        filtered = []
        for conv in self.conversations:
            if agent_filter != "全部客服" and conv.agent_name != agent_filter:
                continue

            r = self.results.get(conv.conv_id)
            has_manual = r and r.manual_score is not None
            if status_filter == "已复核" and not has_manual:
                continue
            if status_filter == "待复核" and has_manual:
                continue

            if problem_filter != "全部问题" and r:
                has_problem = any(v.rule_type.value == problem_filter for v in r.violations)
                if not has_problem:
                    continue

            filtered.append(conv)

        self.filtered_conversations = filtered
        self._refresh_table()
        if filtered:
            self._select_conv(0)

    def _clear_filters(self):
        self.filter_agent.blockSignals(True)
        self.filter_agent.setCurrentIndex(0)
        self.filter_agent.blockSignals(False)
        self.filter_status.blockSignals(True)
        self.filter_status.setCurrentIndex(0)
        self.filter_status.blockSignals(False)
        self.filter_problem.blockSignals(True)
        self.filter_problem.setCurrentIndex(0)
        self.filter_problem.blockSignals(False)
        self.filtered_conversations = list(self.conversations)
        self._refresh_table()

    def _select_all(self):
        for row in range(self.conv_table.rowCount()):
            item = self.conv_table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)

    def _select_none(self):
        for row in range(self.conv_table.rowCount()):
            item = self.conv_table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)

    def _get_selected_conv_ids(self) -> List[str]:
        selected = []
        for row in range(self.conv_table.rowCount()):
            item = self.conv_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                conv = self.filtered_conversations[row]
                selected.append(conv.conv_id)
        return selected

    def _on_batch_label(self):
        selected = self._get_selected_conv_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要批量操作的会话。")
            return

        label, ok = QInputDialog.getItem(
            self, "批量打标签", "选择要添加的标签:",
            AVAILABLE_LABELS, 0, False
        )
        if ok and label:
            for cid in selected:
                r = self.results.get(cid)
                if r and label not in r.labels:
                    r.labels.append(label)
            self.batch_update_requested.emit(selected, {'add_label': label})
            self._refresh_table()
            QMessageBox.information(self, "操作完成", f"已为 {len(selected)} 个会话添加标签: {label}")

    def _on_batch_training(self):
        selected = self._get_selected_conv_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要批量操作的会话。")
            return

        confirm = QMessageBox.question(
            self, "确认", f"确定要将 {len(selected)} 个会话的客服标记为需培训吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            training_label = "需培训"
            if training_label in AVAILABLE_LABELS:
                for cid in selected:
                    r = self.results.get(cid)
                    if r and training_label not in r.labels:
                        r.labels.append(training_label)
            self.batch_update_requested.emit(selected, {'mark_training': True})
            self._refresh_table()
            QMessageBox.information(self, "操作完成", f"已标记 {len(selected)} 个会话为需培训。")
