from typing import List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QTextEdit,
    QSplitter, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from models import Agent, Conversation


class ImportTab(QWidget):
    import_agents_requested = pyqtSignal(str)
    import_conversations_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        file_buttons = QGroupBox("文件导入")
        btn_layout = QHBoxLayout(file_buttons)

        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_title = QLabel("① 导入客服名单")
        left_title.setFont(self._bold_font())
        left_desc = QLabel("支持Excel(.xlsx/.xls)或CSV文件\n必需列：客服ID、客服姓名、店铺、班次\n可选列：组别、入职日期、是否在职")
        left_desc.setWordWrap(True)
        left_desc.setStyleSheet("color: #666;")
        self.btn_import_agents = QPushButton("选择客服名单文件...")
        self.btn_import_agents.setMinimumHeight(40)
        self.btn_import_agents.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_import_agents.clicked.connect(self._on_select_agents_file)
        left_layout.addWidget(left_title)
        left_layout.addWidget(left_desc)
        left_layout.addWidget(self.btn_import_agents)

        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_title = QLabel("② 导入当日会话文件")
        right_title.setFont(self._bold_font())
        right_desc = QLabel("支持Excel(.xlsx/.xls)或CSV文件\n必需列：会话ID、客服ID、消息内容\n推荐列：消息时间、发送者、店铺、班次、订单状态、订单号、客户昵称")
        right_desc.setWordWrap(True)
        right_desc.setStyleSheet("color: #666;")
        self.btn_import_conversations = QPushButton("选择会话文件...")
        self.btn_import_conversations.setMinimumHeight(40)
        self.btn_import_conversations.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.btn_import_conversations.clicked.connect(self._on_select_conversations_file)
        right_layout.addWidget(right_title)
        right_layout.addWidget(right_desc)
        right_layout.addWidget(self.btn_import_conversations)

        btn_layout.addWidget(left_frame, 1)
        btn_layout.addWidget(right_frame, 1)
        layout.addWidget(file_buttons)

        splitter = QSplitter(Qt.Vertical)

        agents_group = QGroupBox("客服名单预览")
        agents_layout = QVBoxLayout(agents_group)
        self.agents_table = QTableWidget(0, 6)
        self.agents_table.setHorizontalHeaderLabels(
            ["客服ID", "姓名", "店铺", "班次", "组别", "状态"]
        )
        self.agents_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.agents_table.setAlternatingRowColors(True)
        self.agents_count_label = QLabel("共 0 条记录")
        al = QHBoxLayout()
        al.addWidget(self.agents_count_label)
        agents_layout.addWidget(self.agents_table)
        agents_layout.addLayout(al)
        splitter.addWidget(agents_group)

        conv_group = QGroupBox("会话文件预览")
        conv_layout = QVBoxLayout(conv_group)
        self.conv_table = QTableWidget(0, 7)
        self.conv_table.setHorizontalHeaderLabels(
            ["会话ID", "客服", "店铺", "班次", "订单状态", "消息数", "时长(分钟)"]
        )
        self.conv_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.conv_table.setAlternatingRowColors(True)
        self.conv_count_label = QLabel("共 0 个会话")
        cl = QHBoxLayout()
        cl.addWidget(self.conv_count_label)
        conv_layout.addWidget(self.conv_table)
        conv_layout.addLayout(cl)
        splitter.addWidget(conv_group)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.errors_text = QTextEdit()
        self.errors_text.setReadOnly(True)
        self.errors_text.setPlaceholderText("导入错误/警告信息将显示在这里...")
        self.errors_text.setStyleSheet("color: #d32f2f; background-color: #fff3e0;")
        self.errors_text.setMaximumHeight(100)
        layout.addWidget(self.errors_text)

    def _bold_font(self) -> QFont:
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        return f

    def _on_select_agents_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择客服名单文件", "",
            "Excel/CSV文件 (*.xlsx *.xls *.csv);;所有文件 (*.*)"
        )
        if file_path:
            self.import_agents_requested.emit(file_path)

    def _on_select_conversations_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择会话文件", "",
            "Excel/CSV文件 (*.xlsx *.xls *.csv);;所有文件 (*.*)"
        )
        if file_path:
            self.import_conversations_requested.emit(file_path)

    def set_agents_data(self, agents: List[Agent], errors: List[str]):
        self.agents_table.setRowCount(len(agents))
        for row, agent in enumerate(agents):
            self.agents_table.setItem(row, 0, QTableWidgetItem(agent.agent_id))
            self.agents_table.setItem(row, 1, QTableWidgetItem(agent.name))
            self.agents_table.setItem(row, 2, QTableWidgetItem(agent.shop))
            self.agents_table.setItem(row, 3, QTableWidgetItem(agent.shift.value))
            self.agents_table.setItem(row, 4, QTableWidgetItem(agent.group))
            status_item = QTableWidgetItem("在职" if agent.is_active else "离职")
            status_item.setForeground(QColor("#4CAF50" if agent.is_active else "#9E9E9E"))
            self.agents_table.setItem(row, 5, status_item)
        self.agents_count_label.setText(f"共 {len(agents)} 条记录")
        if errors:
            self.errors_text.append("=== 客服名单导入警告 ===")
            self.errors_text.append("\n".join(errors))

    def set_conversations_data(self, conversations: List[Conversation], errors: List[str]):
        self.conv_table.setRowCount(len(conversations))
        for row, conv in enumerate(conversations):
            self.conv_table.setItem(row, 0, QTableWidgetItem(conv.conv_id))
            self.conv_table.setItem(row, 1, QTableWidgetItem(conv.agent_name))
            self.conv_table.setItem(row, 2, QTableWidgetItem(conv.shop))
            self.conv_table.setItem(row, 3, QTableWidgetItem(conv.shift.value))
            self.conv_table.setItem(row, 4, QTableWidgetItem(conv.order_status.value))
            self.conv_table.setItem(row, 5, QTableWidgetItem(str(len(conv.messages))))
            duration = round(conv.duration / 60, 1) if conv.duration else 0
            self.conv_table.setItem(row, 6, QTableWidgetItem(str(duration)))
        self.conv_count_label.setText(f"共 {len(conversations)} 个会话")
        if errors:
            self.errors_text.append("\n=== 会话导入警告 ===")
            self.errors_text.append("\n".join(errors))
