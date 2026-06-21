from typing import Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QPushButton, QTabWidget, QWidget, QTextEdit, QMessageBox, QGroupBox,
    QFormLayout, QDialogButtonBox, QListWidget, QListWidgetItem, QSplitter,
    QLineEdit, QCheckBox, QInputDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from services import ConfigManager, RuleConfig, RuleEngine, ReportService
from models import RuleSet
from datetime import datetime


class RuleConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("质检规则配置")
        self.setMinimumSize(1000, 650)
        self.config_manager = ConfigManager()
        self.current_rule_set: Optional[RuleSet] = None
        self._init_ui()
        self._refresh_rule_set_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("质检规则参数配置")
        header.setFont(self._bold_font(14))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        hint = QLabel("支持多套规则集，可按店铺、班次匹配不同规则。修改后点击保存，新配置立即生效。")
        hint.setStyleSheet("color: #666;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(5, 5, 5, 5)

        list_title = QLabel("规则集列表:")
        list_title.setFont(self._bold_font())
        left_layout.addWidget(list_title)

        self.rule_set_list = QListWidget()
        self.rule_set_list.itemSelectionChanged.connect(self._on_select_rule_set)
        left_layout.addWidget(self.rule_set_list, 1)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("➕ 新增")
        self.btn_add.clicked.connect(self._on_add_rule_set)
        self.btn_edit = QPushButton("✏️ 编辑属性")
        self.btn_edit.clicked.connect(self._on_edit_rule_set_meta)
        self.btn_delete = QPushButton("🗑️ 删除")
        self.btn_delete.setStyleSheet("color: #f44336;")
        self.btn_delete.clicked.connect(self._on_delete_rule_set)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_delete)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(5, 5, 5, 5)

        self.rs_info = QLabel("请在左侧选择或新增一个规则集")
        self.rs_info.setStyleSheet("background-color: #e3f2fd; padding: 8px; border-radius: 4px;")
        right_layout.addWidget(self.rs_info)

        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs, 1)

        self._create_basic_tab()
        self._create_words_tab()
        self._create_threshold_tab()

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.Reset
        )
        buttons.button(QDialogButtonBox.Save).setText("💾 保存当前规则集")
        buttons.button(QDialogButtonBox.Cancel).setText("关闭")
        buttons.button(QDialogButtonBox.Reset).setText("↺ 恢复默认规则集")
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

    def _refresh_rule_set_list(self):
        self.rule_set_list.clear()
        for rs in self.config_manager.get_rule_sets():
            label = f"{rs.name} (v{rs.version})"
            if rs.is_default:
                label += "  ⭐默认"
            if rs.shops or rs.shifts:
                scope = []
                if rs.shops:
                    scope.append(f"店铺:{','.join(rs.shops[:2])}{'...' if len(rs.shops) > 2 else ''}")
                if rs.shifts:
                    scope.append(f"班次:{','.join(rs.shifts[:2])}{'...' if len(rs.shifts) > 2 else ''}")
                label += f"  [{';'.join(scope)}]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, rs.rule_set_id)
            self.rule_set_list.addItem(item)

        if self.rule_set_list.count() > 0:
            self.rule_set_list.setCurrentRow(0)

    def _on_select_rule_set(self):
        rows = self.rule_set_list.selectedItems()
        if not rows:
            return
        rs_id = rows[0].data(Qt.UserRole)
        self.current_rule_set = self.config_manager.get_rule_set(rs_id)
        if self.current_rule_set:
            self._load_rule_set_to_ui()

    def _load_rule_set_to_ui(self):
        rs = self.current_rule_set
        default_tag = " ⭐默认规则集" if rs.is_default else ""
        scope = ""
        if rs.shops:
            scope += f"适用店铺: {', '.join(rs.shops)}  "
        else:
            scope += "适用店铺: 全部  "
        if rs.shifts:
            scope += f"适用班次: {', '.join(rs.shifts)}"
        else:
            scope += "适用班次: 全部"
        self.rs_info.setText(
            f"📌 <b>{rs.name}</b> (v{rs.version}){default_tag}<br>"
            f"更新时间: {rs.updated_time or rs.created_time}<br>"
            f"{scope}<br>"
            f"描述: {rs.description or '无'}"
        )

        self.spin_timeout.setValue(rs.reply_timeout)
        self.text_greeting.setPlainText("\n".join(rs.greeting_patterns))
        self.text_forbidden.setPlainText("\n".join(rs.forbidden_words))
        self.text_vague.setPlainText("\n".join(rs.vague_phrases))
        self.text_solution.setPlainText("\n".join(rs.solution_keywords))

        cfg = self.config_manager.get_config()
        self.spin_pass_threshold.setValue(cfg.score_threshold_pass)
        self.spin_attention_threshold.setValue(cfg.score_threshold_attention)
        self.spin_min_samples.setValue(cfg.min_samples_for_training)
        self.spin_pass_rate.setValue(cfg.pass_rate_for_training)

    def _collect_current_rule_set(self) -> Optional[RuleSet]:
        if not self.current_rule_set:
            return None

        def parse_lines(text):
            return [line.strip() for line in text.split('\n') if line.strip()]

        greeting = parse_lines(self.text_greeting.toPlainText())
        if not greeting:
            QMessageBox.warning(self, "提示", "礼貌称呼模式不能为空")
            return None

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return RuleSet(
            rule_set_id=self.current_rule_set.rule_set_id,
            name=self.current_rule_set.name,
            description=self.current_rule_set.description,
            shops=list(self.current_rule_set.shops),
            shifts=list(self.current_rule_set.shifts),
            reply_timeout=self.spin_timeout.value(),
            forbidden_words=parse_lines(self.text_forbidden.toPlainText()),
            greeting_patterns=greeting,
            vague_phrases=parse_lines(self.text_vague.toPlainText()),
            solution_keywords=parse_lines(self.text_solution.toPlainText()),
            is_default=self.current_rule_set.is_default,
            version=self.current_rule_set.version,
            created_time=self.current_rule_set.created_time,
            updated_time=now,
        )

    def _on_add_rule_set(self):
        name, ok = QInputDialog.getText(self, "新增规则集", "请输入规则集名称:")
        if not ok or not name.strip():
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rs_id = f"rs_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        default_rs = self.config_manager.get_default_rule_set()

        new_rs = RuleSet(
            rule_set_id=rs_id,
            name=name.strip(),
            description="",
            shops=[],
            shifts=[],
            reply_timeout=default_rs.reply_timeout,
            forbidden_words=list(default_rs.forbidden_words),
            greeting_patterns=list(default_rs.greeting_patterns),
            vague_phrases=list(default_rs.vague_phrases),
            solution_keywords=list(default_rs.solution_keywords),
            is_default=False,
            version="1.0",
            created_time=now,
            updated_time=now,
        )

        shops_text, ok = QInputDialog.getText(self, "适用店铺设置",
            "请输入适用的店铺名称（多个用逗号分隔，留空表示全部）:")
        if ok and shops_text.strip():
            new_rs.shops = [s.strip() for s in shops_text.split(',') if s.strip()]

        shifts_text, ok = QInputDialog.getText(self, "适用班次设置",
            "请输入适用的班次（如:早班,晚班,留空表示全部）:")
        if ok and shifts_text.strip():
            new_rs.shifts = [s.strip() for s in shifts_text.split(',') if s.strip()]

        desc, ok = QInputDialog.getText(self, "规则集描述", "请输入规则集描述（可选）:")
        if ok:
            new_rs.description = desc.strip()

        success = self.config_manager.add_rule_set(new_rs)
        if success:
            self._refresh_rule_set_list()
            for i in range(self.rule_set_list.count()):
                if self.rule_set_list.item(i).data(Qt.UserRole) == rs_id:
                    self.rule_set_list.setCurrentRow(i)
                    break
            QMessageBox.information(self, "成功", f"规则集 [{name}] 已创建。请在右侧修改参数后点击保存。")
        else:
            QMessageBox.critical(self, "失败", "创建规则集失败。")

    def _on_edit_rule_set_meta(self):
        if not self.current_rule_set:
            QMessageBox.warning(self, "提示", "请先选择一个规则集。")
            return

        if self.current_rule_set.is_default:
            QMessageBox.information(self, "提示", "默认规则集的属性不可编辑，请修改参数或新建规则集。")
            return

        name, ok = QInputDialog.getText(self, "编辑规则集",
            "规则集名称:", QLineEdit.Normal, self.current_rule_set.name)
        if not ok or not name.strip():
            return

        rs = self.current_rule_set
        rs.name = name.strip()

        shops_text, ok = QInputDialog.getText(self, "适用店铺设置",
            "请输入适用的店铺名称（多个用逗号分隔，留空表示全部）:",
            QLineEdit.Normal, ','.join(rs.shops))
        if ok:
            rs.shops = [s.strip() for s in shops_text.split(',') if s.strip()] if shops_text.strip() else []

        shifts_text, ok = QInputDialog.getText(self, "适用班次设置",
            "请输入适用的班次（如:早班,晚班,留空表示全部）:",
            QLineEdit.Normal, ','.join(rs.shifts))
        if ok:
            rs.shifts = [s.strip() for s in shifts_text.split(',') if s.strip()] if shifts_text.strip() else []

        desc, ok = QInputDialog.getText(self, "规则集描述",
            "请输入规则集描述（可选）:", QLineEdit.Normal, rs.description or "")
        if ok:
            rs.description = desc.strip()

        rs.updated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success = self.config_manager.update_rule_set(rs.rule_set_id, rs)
        if success:
            self._refresh_rule_set_list()
            self._load_rule_set_to_ui()
            QMessageBox.information(self, "成功", "规则集属性已更新。")
        else:
            QMessageBox.critical(self, "失败", "更新规则集属性失败。")

    def _on_delete_rule_set(self):
        if not self.current_rule_set:
            QMessageBox.warning(self, "提示", "请先选择一个规则集。")
            return
        if self.current_rule_set.is_default:
            QMessageBox.warning(self, "提示", "默认规则集不可删除。")
            return

        reply = QMessageBox.question(self, "确认删除",
            f"确定要删除规则集 [{self.current_rule_set.name}] 吗？\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success = self.config_manager.delete_rule_set(self.current_rule_set.rule_set_id)
            if success:
                self.current_rule_set = None
                self._refresh_rule_set_list()
                QMessageBox.information(self, "已删除", "规则集已删除。")
            else:
                QMessageBox.critical(self, "失败", "删除规则集失败。")

    def _on_save(self):
        if not self.current_rule_set:
            QMessageBox.warning(self, "提示", "请先选择或新增一个规则集。")
            return
        try:
            new_rs = self._collect_current_rule_set()
            if not new_rs:
                return

            def parse_lines(text):
                return [line.strip() for line in text.split('\n') if line.strip()]

            cfg = self.config_manager.get_config()
            cfg.score_threshold_pass = self.spin_pass_threshold.value()
            cfg.score_threshold_attention = self.spin_attention_threshold.value()
            cfg.min_samples_for_training = self.spin_min_samples.value()
            cfg.pass_rate_for_training = self.spin_pass_rate.value()

            ok1 = self.config_manager.update_rule_set(new_rs.rule_set_id, new_rs)
            ok2 = self.config_manager.update_config(cfg)
            if ok1 and ok2:
                self._refresh_rule_set_list()
                self._load_rule_set_to_ui()
                QMessageBox.information(self, "成功",
                    f"规则集 [{new_rs.name}] 已保存！\n\n"
                    f"后续规则检查时，匹配店铺/班次的会话将自动套用此规则集。\n\n"
                    f"配置文件路径:\n{self.config_manager.get_config_path()}")
            else:
                QMessageBox.critical(self, "失败", "配置保存失败，请检查文件权限。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置时出错: {str(e)}")

    def _on_reset(self):
        reply = QMessageBox.question(self, "确认",
            "确定要将当前规则集恢复为系统默认参数吗？\n（不会影响店铺/班次匹配设置）",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            default_rs = self.config_manager.get_default_rule_set()
            if self.current_rule_set and not self.current_rule_set.is_default:
                self.current_rule_set.reply_timeout = default_rs.reply_timeout
                self.current_rule_set.forbidden_words = list(default_rs.forbidden_words)
                self.current_rule_set.greeting_patterns = list(default_rs.greeting_patterns)
                self.current_rule_set.vague_phrases = list(default_rs.vague_phrases)
                self.current_rule_set.solution_keywords = list(default_rs.solution_keywords)
                self._load_rule_set_to_ui()
                QMessageBox.information(self, "已恢复",
                    "已将当前规则集参数恢复为默认值，点击保存按钮生效。")
            else:
                self.config_manager.reset_to_default()
                self._refresh_rule_set_list()
                QMessageBox.information(self, "已恢复", "已恢复为默认配置。")
