from typing import List, Dict
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QComboBox, QSpinBox, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QVBoxLayout, QSplitter, QRadioButton, QButtonGroup, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from models import Agent, Conversation, ShiftType, OrderStatus


class SamplingTab(QWidget):
    sampling_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)

        method_group = QGroupBox("抽样方式")
        method_layout = QVBoxLayout(method_group)

        self.radio_simple = QRadioButton("简单随机抽样")
        self.radio_stratified = QRadioButton("分层抽样（推荐）")
        self.radio_balanced = QRadioButton("按客服均衡抽样")
        self.radio_stratified.setChecked(True)
        btn_group = QButtonGroup(self)
        btn_group.addButton(self.radio_simple, 0)
        btn_group.addButton(self.radio_stratified, 1)
        btn_group.addButton(self.radio_balanced, 2)

        method_layout.addWidget(self.radio_simple)
        method_layout.addWidget(self.radio_stratified)
        method_layout.addWidget(self.radio_balanced)

        stratify_layout = QHBoxLayout()
        stratify_layout.addWidget(QLabel("分层维度:"))
        self.combo_stratify = QComboBox()
        self.combo_stratify.addItems(["客服", "店铺", "班次", "订单状态", "店铺+班次"])
        stratify_layout.addWidget(self.combo_stratify, 1)
        method_layout.addLayout(stratify_layout)

        per_layout = QHBoxLayout()
        per_layout.addWidget(QLabel("每层抽样数:"))
        self.spin_per = QSpinBox()
        self.spin_per.setRange(1, 50)
        self.spin_per.setValue(2)
        per_layout.addWidget(self.spin_per)
        method_layout.addLayout(per_layout)

        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("抽样总数:"))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 500)
        self.spin_count.setValue(30)
        count_layout.addWidget(self.spin_count)
        method_layout.addLayout(count_layout)

        left_layout.addWidget(method_group)

        filter_group = QGroupBox("筛选条件")
        filter_layout = QVBoxLayout(filter_group)

        shop_layout = QVBoxLayout()
        shop_layout.addWidget(QLabel("店铺 (多选，留空=全部:"))
        self.list_shops = QListWidget()
        self.list_shops.setSelectionMode(QListWidget.MultiSelection)
        self.list_shops.setMaximumHeight(80)
        shop_layout.addWidget(self.list_shops)
        filter_layout.addLayout(shop_layout)

        shift_layout = QVBoxLayout()
        shift_layout.addWidget(QLabel("班次:"))
        self.list_shifts = QListWidget()
        self.list_shifts.setSelectionMode(QListWidget.MultiSelection)
        self.list_shifts.setMaximumHeight(80)
        shift_layout.addWidget(self.list_shifts)
        filter_layout.addLayout(shift_layout)

        order_layout = QVBoxLayout()
        order_layout.addWidget(QLabel("订单状态:"))
        self.list_order_status = QListWidget()
        self.list_order_status.setSelectionMode(QListWidget.MultiSelection)
        self.list_order_status.setMaximumHeight(100)
        order_layout.addWidget(self.list_order_status)
        filter_layout.addLayout(order_layout)

        agent_layout = QVBoxLayout()
        agent_layout.addWidget(QLabel("指定客服 (留空=全部):"))
        self.list_agents = QListWidget()
        self.list_agents.setSelectionMode(QListWidget.MultiSelection)
        self.list_agents.setMaximumHeight(100)
        agent_layout.addWidget(self.list_agents)
        filter_layout.addLayout(agent_layout)

        left_layout.addWidget(filter_group, 1)

        btn_row = QHBoxLayout()
        self.btn_clear_filters = QPushButton("清空筛选")
        self.btn_clear_filters.clicked.connect(self._on_clear_filters)
        self.btn_sample = QPushButton("开始抽样")
        self.btn_sample.setMinimumHeight(45)
        self.btn_sample.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        self.btn_sample.clicked.connect(self._on_do_sample)
        btn_row.addWidget(self.btn_clear_filters)
        btn_row.addWidget(self.btn_sample, 2)
        left_layout.addLayout(btn_row)

        main_splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)

        result_group = QGroupBox("抽样结果")
        result_layout = QVBoxLayout(result_group)
        self.result_table = QTableWidget(0, 8)
        self.result_table.setHorizontalHeaderLabels(
            ["会话ID", "客服", "店铺", "班次", "订单状态", "消息数", "时长(分)", "客户"]
        )
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.result_table.setAlternatingRowColors(True)
        result_layout.addWidget(self.result_table)
        self.result_label = QLabel("共 0 个样本")
        self.result_label.setFont(self._bold_font())
        self.result_label.setStyleSheet("color: #FF9800;")
        result_layout.addWidget(self.result_label)
        right_layout.addWidget(result_group, 1)

        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.addWidget(main_splitter)

    def _bold_font(self):
        f = QFont()
        f.setBold(True)
        return f

    def _on_clear_filters(self):
        lw_list = [self.list_shops, self.list_shifts, self.list_order_status, self.list_agents]
        for lw in lw_list:
            for i in range(lw.count()):
                lw.item(i).setSelected(False)

    def _get_selected(self, list_widget):
        return [list_widget.item(i).text() for i in range(list_widget.count()) if list_widget.item(i).isSelected()]

    def _get_selected_data(self, list_widget, data_role):
        result = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.isSelected():
                data = item.data(data_role)
                if data is not None:
                    result.append(data)
        return result

    def _on_do_sample(self):
        selected_shops_text = self._get_selected(self.list_shops)
        shops = selected_shops_text if selected_shops_text else None

        selected_shifts = self._get_selected_data(self.list_shifts, Qt.UserRole)
        shifts = selected_shifts if selected_shifts else None

        selected_order = self._get_selected_data(self.list_order_status, Qt.UserRole)
        order_statuses = selected_order if selected_order else None

        selected_agents = self._get_selected_data(self.list_agents, Qt.UserRole)
        agent_ids = selected_agents if selected_agents else None

        if self.radio_simple.isChecked():
            method = 'simple'
        elif self.radio_stratified.isChecked():
            method = 'stratified'
        else:
            method = 'balanced'

        stratify_map = {"客服": "agent", "店铺": "shop", "班次": "shift",
                      "订单状态": "order_status", "店铺+班次": "shop_shift"}

        params = {
            'method': method,
            'count': self.spin_count.value(),
            'shops': shops,
            'shifts': shifts,
            'agent_ids': agent_ids,
            'order_statuses': order_statuses,
            'stratify_by': stratify_map.get(self.combo_stratify.currentText(), 'agent'),
            'per_stratum': self.spin_per.value(),
        }
        self.sampling_requested.emit(params)

    def update_filters(self, conversations, agents):
        self._update_shop_filter(conversations, agents)
        self._update_shift_filter(conversations, agents)
        self._update_order_status_filter(conversations)
        self._update_agent_filter(agents)

    def _update_shop_filter(self, conversations, agents):
        shops = set()
        for c in conversations:
            if c.shop:
                shops.add(c.shop)
        for a in agents:
            if a.shop:
                shops.add(a.shop)
        self.list_shops.clear()
        for s in sorted(shops):
            item = QListWidgetItem(s)
            self.list_shops.addItem(item)

    def _update_shift_filter(self, conversations, agents):
        shifts = set()
        for c in conversations:
            shifts.add(c.shift)
        for a in agents:
            shifts.add(a.shift)
        self.list_shifts.clear()
        for s in sorted(shifts, key=lambda x: x.value):
            item = QListWidgetItem(s.value)
            item.setData(Qt.UserRole, s)
            self.list_shifts.addItem(item)

    def _update_order_status_filter(self, conversations):
        statuses = set()
        for c in conversations:
            statuses.add(c.order_status)
        self.list_order_status.clear()
        for s in sorted(statuses, key=lambda x: x.value):
            item = QListWidgetItem(s.value)
            item.setData(Qt.UserRole, s)
            self.list_order_status.addItem(item)

    def _update_agent_filter(self, agents):
        self.list_agents.clear()
        for a in sorted(agents, key=lambda x: x.name):
            text = f"{a.name} ({a.shop} - {a.shift.value})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, a.agent_id)
            self.list_agents.addItem(item)

    def set_sampling_results(self, conversations: List[Conversation]):
        self.result_table.setRowCount(len(conversations))
        for row, conv in enumerate(conversations):
            self.result_table.setItem(row, 0, QTableWidgetItem(conv.conv_id))
            self.result_table.setItem(row, 1, QTableWidgetItem(conv.agent_name))
            self.result_table.setItem(row, 2, QTableWidgetItem(conv.shop))
            self.result_table.setItem(row, 3, QTableWidgetItem(conv.shift.value))
            self.result_table.setItem(row, 4, QTableWidgetItem(conv.order_status.value))
            self.result_table.setItem(row, 5, QTableWidgetItem(str(len(conv.messages))))
            duration = round(conv.duration / 60, 1) if conv.duration else 0
            self.result_table.setItem(row, 6, QTableWidgetItem(str(duration)))
            self.result_table.setItem(row, 7, QTableWidgetItem(conv.customer_nick))
        self.result_label.setText(f"共 {len(conversations)} 个样本")
