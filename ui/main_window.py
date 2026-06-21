from typing import List, Dict
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStatusBar, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from models import Agent, Conversation, ReviewResult, QualityReport
from services import ImportService, SamplingService, RuleEngine, ReviewService, ReportService

from ui.tabs.import_tab import ImportTab
from ui.tabs.sampling_tab import SamplingTab
from ui.tabs.rule_check_tab import RuleCheckTab
from ui.tabs.review_tab import ReviewTab
from ui.tabs.report_tab import ReportTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电商客服聊天质检系统")
        self.setMinimumSize(1200, 800)

        self.agents: List[Agent] = []
        self.all_conversations: List[Conversation] = []
        self.sampled_conversations: List[Conversation] = []
        self.review_results: Dict[str, ReviewResult] = {}
        self.current_report: QualityReport = None

        self.import_service = ImportService()
        self.sampling_service = SamplingService()
        self.rule_engine = RuleEngine()
        self.review_service = ReviewService()
        self.report_service = ReportService()

        self._init_ui()
        self._connect_signals()
        self._update_status()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("电商客服每日聊天质检工具")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("账号导入 → 会话抽样 → 规则检查 → 人工复核 → 报告导出")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs, 1)

        self.import_tab = ImportTab()
        self.sampling_tab = SamplingTab()
        self.rule_check_tab = RuleCheckTab()
        self.review_tab = ReviewTab()
        self.report_tab = ReportTab()

        self.tabs.addTab(self.import_tab, "① 账号导入")
        self.tabs.addTab(self.sampling_tab, "② 会话抽样")
        self.tabs.addTab(self.rule_check_tab, "③ 规则检查")
        self.tabs.addTab(self.review_tab, "④ 人工复核")
        self.tabs.addTab(self.report_tab, "⑤ 报告窗口")

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

    def _connect_signals(self):
        self.import_tab.import_agents_requested.connect(self._on_import_agents)
        self.import_tab.import_conversations_requested.connect(self._on_import_conversations)
        self.sampling_tab.sampling_requested.connect(self._on_sampling_requested)
        self.rule_check_tab.run_check_requested.connect(self._on_run_rule_check)
        self.review_tab.submit_review_requested.connect(self._on_submit_review)
        self.report_tab.generate_report_requested.connect(self._on_generate_report)
        self.report_tab.export_report_requested.connect(self._on_export_report)

    def _update_status(self):
        msg = f"客服数: {len(self.agents)} | 总会话数: {len(self.all_conversations)} | 抽样数: {len(self.sampled_conversations)} | 已复核: {sum(1 for r in self.review_results.values() if r.manual_score is not None)}"
        self.statusBar.showMessage(msg)

    def _on_import_agents(self, file_path):
        try:
            agents, errors = self.import_service.import_agents(file_path)
            self.agents.extend(agents)
            self.import_tab.set_agents_data(self.agents, errors)
            self.sampling_tab.update_filters(self.all_conversations, self.agents)
            self._update_status()
            if errors:
                QMessageBox.warning(self, "导入完成（含警告）",
                                    f"成功导入 {len(agents)} 条客服记录，{len(errors)} 条异常。\n详细信息请查看导入结果表格。")
            else:
                QMessageBox.information(self, "导入成功", f"成功导入 {len(agents)} 条客服记录。")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def _on_import_conversations(self, file_path):
        try:
            conversations, errors = self.import_service.import_conversations(file_path)
            self.all_conversations.extend(conversations)
            self.import_tab.set_conversations_data(self.all_conversations, errors)
            self.sampling_tab.update_filters(self.all_conversations, self.agents)
            self._update_status()
            if errors:
                QMessageBox.warning(self, "导入完成（含警告）",
                                    f"成功导入 {len(conversations)} 个会话，{len(errors)} 条异常。\n详细信息请查看导入结果表格。")
            else:
                QMessageBox.information(self, "导入成功", f"成功导入 {len(conversations)} 个会话。")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def _on_sampling_requested(self, params):
        try:
            if not self.all_conversations:
                QMessageBox.warning(self, "提示", "请先导入会话文件。")
                return

            method = params.get('method', 'simple')
            count = params.get('count', 20)
            shops = params.get('shops')
            shifts = params.get('shifts')
            agent_ids = params.get('agent_ids')
            order_statuses = params.get('order_statuses')
            stratify_by = params.get('stratify_by', 'agent')
            per_stratum = params.get('per_stratum', 2)

            if method == 'simple':
                self.sampled_conversations = self.sampling_service.simple_random_sample(
                    self.all_conversations, count, shops, shifts, agent_ids, order_statuses
                )
            elif method == 'stratified':
                self.sampled_conversations = self.sampling_service.stratified_sample(
                    self.all_conversations, per_stratum, stratify_by,
                    shops, shifts, agent_ids, order_statuses
                )
            elif method == 'balanced':
                self.sampled_conversations = self.sampling_service.balanced_sample(
                    self.all_conversations, count, self.agents, shops, shifts
                )
            else:
                self.sampled_conversations = []

            self.sampling_tab.set_sampling_results(self.sampled_conversations)
            self.rule_check_tab.set_conversations(self.sampled_conversations)
            self.review_tab.set_conversations(self.sampled_conversations, self.review_results)
            self.report_tab.set_sampling_summary(self.sampled_conversations, self.review_results)
            self._update_status()
            QMessageBox.information(self, "抽样完成", f"共抽取 {len(self.sampled_conversations)} 个会话样本。")
        except Exception as e:
            QMessageBox.critical(self, "抽样失败", str(e))

    def _on_run_rule_check(self):
        try:
            if not self.sampled_conversations:
                QMessageBox.warning(self, "提示", "请先完成会话抽样。")
                return

            for conv in self.sampled_conversations:
                violations = self.rule_engine.check_all(conv)
                auto_score = self.rule_engine.calculate_score(violations)
                self.review_service.initialize_review(conv.conv_id, violations, auto_score)
                self.review_results[conv.conv_id] = self.review_service.get_review(conv.conv_id)

            self.rule_check_tab.set_check_results(self.sampled_conversations, self.review_results)
            self.review_tab.set_conversations(self.sampled_conversations, self.review_results)
            self.report_tab.set_sampling_summary(self.sampled_conversations, self.review_results)
            self._update_status()
            QMessageBox.information(self, "检查完成",
                                    f"已完成 {len(self.sampled_conversations)} 个会话的自动规则检查。")
        except Exception as e:
            QMessageBox.critical(self, "检查失败", str(e))

    def _on_submit_review(self, review_data):
        try:
            conv_id = review_data['conv_id']
            self.review_service.initialize_review(conv_id)

            if 'manual_score' in review_data:
                self.review_service.update_score(conv_id, review_data['manual_score'])
            if 'labels' in review_data:
                self.review_service.set_labels(conv_id, review_data['labels'])
            if 'is_excellent' in review_data:
                self.review_service.toggle_excellent(conv_id, review_data['is_excellent'])
            if 'key_snippets' in review_data:
                review = self.review_service.get_review(conv_id)
                if review:
                    review.key_snippets = review_data['key_snippets']
            if 'reviewer_notes' in review_data:
                self.review_service.set_reviewer_notes(conv_id, review_data['reviewer_notes'])
            if 'reviewed_by' in review_data:
                self.review_service.set_reviewer(conv_id, review_data['reviewed_by'])

            self.review_results[conv_id] = self.review_service.get_review(conv_id)
            self.report_tab.set_sampling_summary(self.sampled_conversations, self.review_results)
            self._update_status()
        except Exception as e:
            QMessageBox.critical(self, "提交失败", str(e))

    def _on_generate_report(self):
        try:
            if not self.sampled_conversations:
                QMessageBox.warning(self, "提示", "请先完成会话抽样。")
                return

            reviewed_count = sum(1 for r in self.review_results.values() if r.manual_score is not None)
            if reviewed_count == 0:
                reply = QMessageBox.question(self, "确认",
                    "尚未有任何人工复核记录，是否仅基于系统自动评分生成报告？",
                    QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return

            self.current_report = self.report_service.generate_report(
                self.sampled_conversations, self.review_results, self.agents
            )
            self.report_tab.set_report(self.current_report)
        except Exception as e:
            QMessageBox.critical(self, "生成失败", str(e))

    def _on_export_report(self, default_name: str):
        try:
            if self.current_report is None:
                QMessageBox.warning(self, "提示", "请先生成报告。")
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出质检报告", default_name,
                "Excel文件 (*.xlsx);;所有文件 (*.*)"
            )
            if file_path:
                if not file_path.endswith('.xlsx'):
                    file_path += '.xlsx'
                success = self.report_service.export_to_excel(
                    self.current_report, file_path,
                    self.sampled_conversations, self.review_results
                )
                if success:
                    QMessageBox.information(self, "导出成功", f"报告已导出至:\n{file_path}")
                else:
                    QMessageBox.critical(self, "导出失败", "报告导出过程中出现错误。")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
