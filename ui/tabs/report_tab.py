from typing import List, Dict
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QTextEdit,
    QFrame, QListWidget, QListWidgetItem, QSizePolicy, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from models import Conversation, ReviewResult, QualityReport


class ReportTab(QWidget):
    generate_report_requested = pyqtSignal(bool)
    export_report_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.report: QualityReport = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QFrame()
        top_bar.setFrameShape(QFrame.StyledPanel)
        top_bar.setStyleSheet("background-color: #f5f5f5;")
        top_layout = QVBoxLayout(top_bar)

        mode_row = QHBoxLayout()
        mode_label = QLabel("报告口径:")
        mode_label.setFont(self._bold_font())
        self.radio_auto = QRadioButton("🤖 仅自动规则 (全部用系统分)")
        self.radio_manual = QRadioButton("👤 人工复核优先 (无人工分时用系统分)")
        self.radio_manual.setChecked(True)
        self.btn_generate = QPushButton("📊 生成质检报告")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.setStyleSheet("background-color: #673AB7; color: white; font-weight: bold;")
        self.btn_generate.clicked.connect(self._on_generate_clicked)

        self.btn_export = QPushButton("📥 导出Excel报告")
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setStyleSheet("background-color: #009688; color: white; font-weight: bold;")
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_export.setEnabled(False)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_auto, 0)
        self.mode_group.addButton(self.radio_manual, 1)

        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.radio_auto)
        mode_row.addWidget(self.radio_manual)
        mode_row.addStretch()
        mode_row.addWidget(self.btn_generate)
        mode_row.addWidget(self.btn_export)
        top_layout.addLayout(mode_row)

        info_row = QHBoxLayout()
        self.summary_status = QLabel("等待生成报告...")
        self.summary_status.setFont(self._bold_font(12))
        self.mode_hint = QLabel("")
        self.mode_hint.setStyleSheet("color: #666;")
        info_row.addWidget(self.summary_status)
        info_row.addStretch()
        info_row.addWidget(self.mode_hint)
        top_layout.addLayout(info_row)

        layout.addWidget(top_bar)

        self.radio_auto.toggled.connect(self._on_mode_changed)
        self.radio_manual.toggled.connect(self._on_mode_changed)
        self._update_mode_hint()

        splitter = QSplitter(Qt.Horizontal)

        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)

        overview_group = QGroupBox("报告概览")
        overview_layout = QVBoxLayout(overview_group)
        self.overview_table = QTableWidget(0, 2)
        self.overview_table.horizontalHeader().setVisible(False)
        self.overview_table.verticalHeader().setVisible(False)
        self.overview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.overview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.overview_table.setAlternatingRowColors(True)
        overview_layout.addWidget(self.overview_table)
        left_layout.addWidget(overview_group)

        score_group = QGroupBox("个人得分排名")
        score_layout = QVBoxLayout(score_group)
        self.score_table = QTableWidget(0, 3)
        self.score_table.setHorizontalHeaderLabels(["客服", "平均分", "等级"])
        self.score_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.score_table.setAlternatingRowColors(True)
        score_layout.addWidget(self.score_table)
        left_layout.addWidget(score_group, 1)

        splitter.addWidget(left_column)

        center_column = QWidget()
        center_layout = QVBoxLayout(center_column)
        center_layout.setContentsMargins(0, 0, 0, 0)

        problem_group = QGroupBox("常见问题统计")
        problem_layout = QVBoxLayout(problem_group)
        self.problem_table = QTableWidget(0, 3)
        self.problem_table.setHorizontalHeaderLabels(["问题类型", "次数", "占比"])
        self.problem_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.problem_table.setAlternatingRowColors(True)
        problem_layout.addWidget(self.problem_table)
        center_layout.addWidget(problem_group, 1)

        training_group = QGroupBox("待培训名单")
        training_layout = QVBoxLayout(training_group)
        self.training_list = QListWidget()
        self.training_list.setStyleSheet("""
            QListWidget::item { padding: 8px; border-bottom: 1px solid #ffccbc; }
            QListWidget::item:selected { background-color: #ff7043; color: white; }
        """)
        training_layout.addWidget(self.training_list)
        center_layout.addWidget(training_group, 1)

        splitter.addWidget(center_column)

        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)

        excellent_group = QGroupBox("优秀案例")
        excellent_layout = QVBoxLayout(excellent_group)
        self.excellent_list = QListWidget()
        self.excellent_list.setStyleSheet("""
            QListWidget::item { padding: 8px; border-bottom: 1px solid #c8e6c9; }
            QListWidget::item:selected { background-color: #66bb6a; color: white; }
        """)
        excellent_layout.addWidget(self.excellent_list)
        right_layout.addWidget(excellent_group, 1)

        rect_group = QGroupBox("整改清单")
        rect_layout = QVBoxLayout(rect_group)
        self.rect_table = QTableWidget(0, 5)
        self.rect_table.setHorizontalHeaderLabels(["客服", "得分", "主要问题", "整改建议", "备注"])
        self.rect_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rect_table.setAlternatingRowColors(True)
        rect_layout.addWidget(self.rect_table)
        right_layout.addWidget(rect_group, 2)

        splitter.addWidget(right_column)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)

        layout.addWidget(splitter, 1)

        preview_group = QGroupBox("报告文字预览 (可复制)")
        preview_layout = QVBoxLayout(preview_group)
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setMaximumHeight(150)
        self.report_text.setStyleSheet("font-family: 'Courier New', monospace; font-size: 11px;")
        preview_layout.addWidget(self.report_text)
        layout.addWidget(preview_group)

    def _bold_font(self, size=10):
        f = QFont()
        f.setBold(True)
        f.setPointSize(size)
        return f

    def _score_color(self, score):
        if score >= 90:
            return QColor("#4CAF50"), "优秀"
        elif score >= 80:
            return QColor("#8BC34A"), "良好"
        elif score >= 70:
            return QColor("#FFC107"), "合格"
        elif score >= 60:
            return QColor("#FF9800"), "待改进"
        return QColor("#F44336"), "不合格"

    def set_sampling_summary(self, conversations, results):
        total = len(conversations)
        reviewed = sum(1 for r in results.values() if r.manual_score is not None)
        self.summary_status.setText(
            f"抽样数: {total} | 已复核: {reviewed} | 待复核: {total - reviewed}"
        )

    def _update_mode_hint(self):
        if self.radio_auto.isChecked():
            self.mode_hint.setText(
                "当前: 自动规则口径 - 所有样本使用系统评分，"
                "无需人工复核即可生成完整报告"
            )
        else:
            self.mode_hint.setText(
                "当前: 人工复核优先 - 已复核样本用人工分，"
                "未复核样本自动用系统分补充，确保数据完整"
            )

    def _on_mode_changed(self):
        self._update_mode_hint()

    def _on_generate_clicked(self):
        prefer_manual = not self.radio_auto.isChecked()
        self.generate_report_requested.emit(prefer_manual)

    def _on_export_clicked(self):
        mode = "自动规则" if self.radio_auto.isChecked() else "人工优先"
        today = datetime.now().strftime("%Y%m%d")
        default_name = f"质检报告_{today}_{mode}.xlsx"
        self.export_report_requested.emit(default_name)

    def set_report(self, report: QualityReport):
        self.report = report
        self.btn_export.setEnabled(True)

        overview_data = [
            ("报告日期", report.report_date),
            ("报告口径", getattr(report, 'report_mode', '人工复核口径')),
            ("抽样总数", str(report.total_sampled)),
            ("已复核数量", str(report.total_reviewed)),
            ("未复核数量", str(report.total_sampled - report.total_reviewed)),
            ("整体平均分", f"{report.avg_score} 分"),
            ("参与评分配人数", str(len(report.agent_scores))),
            ("合格率(≥80分)",
             f"{round(sum(1 for s in report.agent_scores.values() if s >= 80) / max(len(report.agent_scores), 1) * 100, 1)}%"
             ),
            ("需培训人数", str(len(report.training_list))),
            ("优秀案例数", str(len(report.excellent_cases))),
            ("整改项数", str(len(report.rectification_items))),
        ]
        self.overview_table.setRowCount(len(overview_data))
        for r, (k, v) in enumerate(overview_data):
            key_item = QTableWidgetItem(k)
            key_item.setFont(self._bold_font())
            self.overview_table.setItem(r, 0, key_item)
            self.overview_table.setItem(r, 1, QTableWidgetItem(v))

        sorted_scores = sorted(report.agent_scores.items(), key=lambda x: x[1], reverse=True)
        self.score_table.setRowCount(len(sorted_scores))
        for r, (name, score) in enumerate(sorted_scores):
            color, grade = self._score_color(score)
            name_item = QTableWidgetItem(f"{'🥇' if r==0 else '🥈' if r==1 else '🥉' if r==2 else str(r+1)+'. '}{name}")
            score_item = QTableWidgetItem(f"{score:.1f}")
            grade_item = QTableWidgetItem(grade)
            score_item.setForeground(color)
            grade_item.setForeground(color)
            f = QFont()
            f.setBold(True)
            score_item.setFont(f)
            self.score_table.setItem(r, 0, name_item)
            self.score_table.setItem(r, 1, score_item)
            self.score_table.setItem(r, 2, grade_item)

        sorted_problems = sorted(report.problem_counts.items(), key=lambda x: x[1], reverse=True)
        total_issues = sum(c for p, c in sorted_problems if not p.startswith("标签:"))
        self.problem_table.setRowCount(len(sorted_problems))
        for r, (name, count) in enumerate(sorted_problems):
            name_item = QTableWidgetItem(name)
            if name.startswith("标签:"):
                name_item.setForeground(QColor("#673AB7"))
            self.problem_table.setItem(r, 0, name_item)
            self.problem_table.setItem(r, 1, QTableWidgetItem(str(count)))
            pct = f"{count / max(total_issues, 1) * 100:.1f}%" if not name.startswith("标签:") else "-"
            self.problem_table.setItem(r, 2, QTableWidgetItem(pct))

        self.training_list.clear()
        if report.training_list:
            for name in report.training_list:
                item = QListWidgetItem(f"⚠️  {name}")
                item.setForeground(QColor("#E65100"))
                self.training_list.addItem(item)
        else:
            item = QListWidgetItem("✅ 暂无需培训的客服")
            item.setForeground(QColor("#4CAF50"))
            self.training_list.addItem(item)

        self.excellent_list.clear()
        if report.excellent_cases:
            for case in report.excellent_cases:
                self.excellent_list.addItem(QListWidgetItem("⭐ " + case))
        else:
            item = QListWidgetItem("暂无标记的优秀案例")
            item.setForeground(QColor("#999"))
            self.excellent_list.addItem(item)

        self.rect_table.setRowCount(len(report.rectification_items))
        for r, item in enumerate(report.rectification_items):
            score = item['得分']
            color, _ = self._score_color(score)
            score_item = QTableWidgetItem(str(score))
            score_item.setForeground(color)
            score_item.setFont(self._bold_font())
            self.rect_table.setItem(r, 0, QTableWidgetItem(item['客服']))
            self.rect_table.setItem(r, 1, score_item)
            self.rect_table.setItem(r, 2, QTableWidgetItem(item['主要问题']))
            self.rect_table.setItem(r, 3, QTableWidgetItem(item['整改建议']))
            self.rect_table.setItem(r, 4, QTableWidgetItem(item['复核备注']))

        from services.report_service import ReportService
        text = ReportService().get_problem_summary_text(report)
        self.report_text.setPlainText(text)
