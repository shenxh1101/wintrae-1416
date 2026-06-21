from typing import List, Dict
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStatusBar, QMessageBox, QFileDialog, QMenuBar, QAction,
    QToolBar, QDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon

from models import Agent, Conversation, ReviewResult, QualityReport
from services import (
    ImportService, SamplingService, RuleEngine, ReviewService, ReportService,
    ConfigManager, BatchManager, QualityBatch
)

from ui.tabs.import_tab import ImportTab
from ui.tabs.sampling_tab import SamplingTab
from ui.tabs.rule_check_tab import RuleCheckTab
from ui.tabs.review_tab import ReviewTab
from ui.tabs.report_tab import ReportTab
from ui.rule_config_dialog import RuleConfigDialog
from ui.batch_manager_dialog import BatchManagerDialog


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
        self._create_menu_bar()
        self._create_tool_bar()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 5, 10, 10)

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

    def _create_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&文件")

        action_import_agents = QAction("导入客服名单...", self)
        action_import_agents.setShortcut("Ctrl+O")
        action_import_agents.triggered.connect(self._on_menu_import_agents)
        file_menu.addAction(action_import_agents)

        action_import_conv = QAction("导入会话文件...", self)
        action_import_conv.setShortcut("Ctrl+I")
        action_import_conv.triggered.connect(self._on_menu_import_conversations)
        file_menu.addAction(action_import_conv)

        file_menu.addSeparator()

        action_save_batch = QAction("💾 保存当前质检批次...", self)
        action_save_batch.setShortcut("Ctrl+S")
        action_save_batch.triggered.connect(self._on_save_batch)
        file_menu.addAction(action_save_batch)

        action_load_batch = QAction("📂 加载历史批次...", self)
        action_load_batch.setShortcut("Ctrl+L")
        action_load_batch.triggered.connect(self._on_load_batch)
        file_menu.addAction(action_load_batch)

        file_menu.addSeparator()

        action_manage_batches = QAction("📋 批次管理...", self)
        action_manage_batches.triggered.connect(self._on_manage_batches)
        file_menu.addAction(action_manage_batches)

        file_menu.addSeparator()

        action_exit = QAction("退出", self)
        action_exit.setShortcut("Ctrl+Q")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        tools_menu = menubar.addMenu("&工具")

        action_rule_config = QAction("⚙️ 质检规则配置...", self)
        action_rule_config.setShortcut("F2")
        action_rule_config.triggered.connect(self._on_rule_config)
        tools_menu.addAction(action_rule_config)

        tools_menu.addSeparator()

        action_reload_config = QAction("🔄 重新加载配置", self)
        action_reload_config.triggered.connect(self._on_reload_config)
        tools_menu.addAction(action_reload_config)

        help_menu = menubar.addMenu("&帮助")

        action_about = QAction("关于", self)
        action_about.triggered.connect(self._on_about)
        help_menu.addAction(action_about)

    def _create_tool_bar(self):
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        action_save = QAction("💾 保存批次", self)
        action_save.triggered.connect(self._on_save_batch)
        toolbar.addAction(action_save)

        action_load = QAction("📂 加载批次", self)
        action_load.triggered.connect(self._on_load_batch)
        toolbar.addAction(action_load)

        toolbar.addSeparator()

        action_config = QAction("⚙️ 规则配置", self)
        action_config.triggered.connect(self._on_rule_config)
        toolbar.addAction(action_config)

        toolbar.addSeparator()

        self.toolbar_info = QLabel("  就绪")
        self.toolbar_info.setStyleSheet("color: #666;")
        toolbar.addWidget(self.toolbar_info)

    def _connect_signals(self):
        self.import_tab.import_agents_requested.connect(self._on_import_agents)
        self.import_tab.import_conversations_requested.connect(self._on_import_conversations)
        self.sampling_tab.sampling_requested.connect(self._on_sampling_requested)
        self.rule_check_tab.run_check_requested.connect(self._on_run_rule_check)
        self.review_tab.submit_review_requested.connect(self._on_submit_review)
        self.review_tab.batch_update_requested.connect(self._on_batch_update)
        self.report_tab.generate_report_requested.connect(self._on_generate_report)
        self.report_tab.export_report_requested.connect(self._on_export_report)
        self.current_batch_id: str = None

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

            rule_set_usage = {}
            for conv in self.sampled_conversations:
                violations, rule_set = self.rule_engine.check_all(conv)
                auto_score = self.rule_engine.calculate_score(violations)
                self.review_service.initialize_review(conv.conv_id, violations, auto_score)

                review = self.review_service.get_review(conv.conv_id)
                if review:
                    review.rule_set_id = rule_set.rule_set_id
                    review.rule_set_version = rule_set.version

                self.review_results[conv.conv_id] = self.review_service.get_review(conv.conv_id)

                rs_key = f"{rule_set.name} (v{rule_set.version})"
                if rs_key not in rule_set_usage:
                    rule_set_usage[rs_key] = 0
                rule_set_usage[rs_key] += 1

            self.rule_check_tab.set_check_results(self.sampled_conversations, self.review_results)
            self.review_tab.set_conversations(self.sampled_conversations, self.review_results)
            self.report_tab.set_sampling_summary(self.sampled_conversations, self.review_results)
            self._update_status()

            usage_text = "\n".join([f"  {k}: {v}个样本" for k, v in rule_set_usage.items()])
            QMessageBox.information(self, "检查完成",
                                    f"已完成 {len(self.sampled_conversations)} 个会话的自动规则检查。\n\n规则集使用情况:\n{usage_text}")
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

            if self.current_batch_id:
                from services import BatchManager
                bm = BatchManager()
                success = bm.update_batch_reviews(self.current_batch_id, self.review_results)
                if success:
                    reviewed = sum(1 for r in self.review_results.values() if r.manual_score is not None)
                    total = len(self.sampled_conversations)
                    self.toolbar_info.setText(f"  批次进度已更新: {reviewed}/{total} ({int(reviewed/max(total,1)*100)}%)")
        except Exception as e:
            QMessageBox.critical(self, "提交失败", str(e))

    def _on_batch_update(self, conv_ids: List[str], update_data: dict):
        try:
            for cid in conv_ids:
                if 'add_label' in update_data:
                    self.review_service.add_label(cid, update_data['add_label'])
                if 'mark_training' in update_data:
                    self.review_service.add_label(cid, '需培训')
                self.review_results[cid] = self.review_service.get_review(cid)

            self.report_tab.set_sampling_summary(self.sampled_conversations, self.review_results)
            self._update_status()

            if self.current_batch_id:
                from services import BatchManager
                bm = BatchManager()
                bm.update_batch_reviews(self.current_batch_id, self.review_results)

            self.review_tab.set_conversations(self.sampled_conversations, self.review_results)
            self.rule_check_tab.set_check_results(self.sampled_conversations, self.review_results)
        except Exception as e:
            QMessageBox.critical(self, "批量操作失败", str(e))

    def _on_generate_report(self, prefer_manual: bool = True):
        try:
            if not self.sampled_conversations:
                QMessageBox.warning(self, "提示", "请先完成会话抽样。")
                return

            mode_text = "人工复核优先" if prefer_manual else "仅自动规则"
            self.toolbar_info.setText(f"  正在生成{mode_text}报告...")

            self.current_report = self.report_service.generate_report(
                self.sampled_conversations, self.review_results, self.agents,
                prefer_manual_score=prefer_manual
            )
            self.report_tab.set_report(self.current_report)

            cfg = ConfigManager().get_config()
            reviewed_count = sum(1 for r in self.review_results.values() if r.manual_score is not None)
            if reviewed_count < len(self.sampled_conversations) and prefer_manual:
                QMessageBox.information(self, "报告生成完成",
                    f"报告已生成（{mode_text}口径）。\n\n"
                    f"已复核: {reviewed_count}/{len(self.sampled_conversations)}\n"
                    f"未复核样本已自动使用系统评分补充，确保报告数据完整。\n\n"
                    f"合格分数线: {cfg.score_threshold_pass}分\n"
                    f"预警分数线: {cfg.score_threshold_attention}分")
            else:
                QMessageBox.information(self, "报告生成完成",
                    f"报告已生成（{mode_text}口径）。")

            self.toolbar_info.setText(f"  报告已生成: {mode_text}")
        except Exception as e:
            self.toolbar_info.setText("  报告生成失败")
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

    def _get_current_batch_data(self) -> dict:
        return {
            'sampled_conversations': self.sampled_conversations,
            'all_conversations': self.all_conversations,
            'agents': self.agents,
            'review_results': self.review_results,
            'sampling_params': {},
        }

    def _on_menu_import_agents(self):
        self.tabs.setCurrentIndex(0)
        self.import_tab._on_select_agents_file()

    def _on_menu_import_conversations(self):
        self.tabs.setCurrentIndex(0)
        self.import_tab._on_select_conversations_file()

    def _on_save_batch(self):
        if not self.sampled_conversations:
            QMessageBox.warning(self, "提示", "请先完成会话抽样，再保存批次。")
            return

        batch_data = self._get_current_batch_data()
        dialog = BatchManagerDialog(self, batch_data)
        dialog.batch_saved.connect(self._on_batch_saved)
        dialog.exec_()

    def _on_load_batch(self):
        dialog = BatchManagerDialog(self, self._get_current_batch_data())
        dialog.batch_loaded.connect(self._on_batch_loaded)
        dialog.exec_()

    def _on_manage_batches(self):
        dialog = BatchManagerDialog(self, self._get_current_batch_data())
        dialog.batch_loaded.connect(self._on_batch_loaded)
        dialog.batch_saved.connect(self._on_batch_saved)
        dialog.exec_()

    def _on_batch_saved(self, batch):
        self.current_batch_id = batch.batch_id
        self.toolbar_info.setText(f"  批次已保存: {batch.batch_name}")
        self._update_status()

    def _on_batch_loaded(self, batch: QualityBatch):
        try:
            agents, conversations, review_results = batch.to_entities()

            sampled_ids = set(batch.sampled_conv_ids)
            self.agents = agents
            self.all_conversations = conversations
            self.sampled_conversations = [c for c in conversations if c.conv_id in sampled_ids]
            self.review_results = review_results
            self.current_batch_id = batch.batch_id

            self.import_tab.set_agents_data(self.agents, [])
            self.import_tab.set_conversations_data(self.all_conversations, [])
            self.sampling_tab.update_filters(self.all_conversations, self.agents)
            self.sampling_tab.set_sampling_results(self.sampled_conversations)
            self.rule_check_tab.set_conversations(self.sampled_conversations)

            if self.review_results:
                self.rule_check_tab.set_check_results(
                    self.sampled_conversations, self.review_results
                )

            for cid, result in self.review_results.items():
                self.review_service.results[cid] = result

            self.review_tab.set_conversations(self.sampled_conversations, self.review_results)
            self.report_tab.set_sampling_summary(self.sampled_conversations, self.review_results)

            self._update_status()
            self.toolbar_info.setText(f"  批次已加载: {batch.batch_name}")
            self.tabs.setCurrentIndex(3)

            progress = batch.get_review_progress()
            QMessageBox.information(self, "批次加载成功",
                f"已成功加载批次: {batch.batch_name}\n\n"
                f"样本数: {progress['total']}\n"
                f"已复核: {progress['reviewed']}\n"
                f"待复核: {progress['pending']}\n"
                f"完成进度: {progress['progress']:.1f}%")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"批次加载失败: {str(e)}")

    def _on_rule_config(self):
        dialog = RuleConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.rule_engine.reload_config()
            self.report_service._reload_config()
            self.toolbar_info.setText("  规则配置已更新")
            QMessageBox.information(self, "配置已更新",
                "质检规则配置已更新。\n\n"
                "后续规则检查和报告生成将使用新配置。\n"
                "如需对已有样本重新检查，请回到「规则检查」页面重新执行检查。")

    def _on_reload_config(self):
        try:
            self.rule_engine.reload_config()
            self.report_service._reload_config()
            self.toolbar_info.setText("  配置已重新加载")
            QMessageBox.information(self, "已刷新", "规则配置已从文件重新加载。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重新加载配置失败: {str(e)}")

    def _on_about(self):
        cfg_path = ConfigManager().get_config_path()
        batch_dir = BatchManager().get_batches_dir()
        QMessageBox.information(self, "关于",
            "电商客服聊天质检系统 v2.0\n\n"
            "功能模块:\n"
            "① 账号导入 - 支持Excel/CSV格式\n"
            "② 会话抽样 - 多维筛选与三种抽样方式\n"
            "③ 规则检查 - 5大质检规则自动识别\n"
            "④ 人工复核 - 逐条打分、标签、优秀案例\n"
            "⑤ 报告窗口 - 两种口径完整报告导出\n\n"
            "新增功能:\n"
            "• 角色识别优化 - 优先按角色列判断\n"
            "• 规则配置自定义 - 可调整所有参数\n"
            "• 质检批次管理 - 保存加载继续复核\n"
            "• 双口径报告 - 自动/人工均可生成\n\n"
            f"配置文件: {cfg_path}\n"
            f"批次目录: {batch_dir}")

