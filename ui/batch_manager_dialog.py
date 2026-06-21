from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit, QDialogButtonBox,
    QInputDialog, QSplitter, QWidget, QFrame, QProgressBar, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from services import BatchManager, QualityBatch


class BatchManagerDialog(QDialog):
    batch_loaded = pyqtSignal(object)
    batch_saved = pyqtSignal(object)

    def __init__(self, parent=None, current_data=None):
        super().__init__(parent)
        self.setWindowTitle("质检批次管理")
        self.setMinimumSize(900, 500)
        self.batch_manager = BatchManager()
        self.current_data = current_data
        self._init_ui()
        self._refresh_batch_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("质检批次管理")
        title.setFont(self._bold_font(14))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(5, 5, 5, 5)

        save_bar = QFrame()
        save_bar.setFrameShape(QFrame.StyledPanel)
        save_layout = QHBoxLayout(save_bar)
        save_layout.addWidget(QLabel("批次名称:"))
        self.edit_batch_name = QLineEdit()
        self.edit_batch_name.setPlaceholderText("例如：2026-06-22 早班质检")
        save_layout.addWidget(self.edit_batch_name, 1)
        self.btn_save_batch = QPushButton("💾 保存当前批次")
        self.btn_save_batch.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_save_batch.clicked.connect(self._on_save_current_batch)
        save_layout.addWidget(self.btn_save_batch)
        left_layout.addWidget(save_bar)

        list_label = QLabel("历史批次（双击加载继续复核）:")
        list_label.setFont(self._bold_font())
        left_layout.addWidget(list_label)

        self.batch_table = QTableWidget(0, 7)
        self.batch_table.setHorizontalHeaderLabels(
            ["批次ID", "批次名称", "创建时间", "更新时间", "样本数", "已复核", "进度"]
        )
        self.batch_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.batch_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.batch_table.doubleClicked.connect(self._on_load_selected)
        left_layout.addWidget(self.batch_table, 1)

        btn_row = QHBoxLayout()
        self.btn_load = QPushButton("📂 加载选中批次")
        self.btn_load.clicked.connect(self._on_load_selected)
        self.btn_delete = QPushButton("🗑️ 删除批次")
        self.btn_delete.setStyleSheet("background-color: #f44336; color: white;")
        self.btn_delete.clicked.connect(self._on_delete_batch)
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_delete)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(5, 5, 5, 5)

        info_group = QFrame()
        info_group.setFrameShape(QFrame.StyledPanel)
        info_layout = QVBoxLayout(info_group)
        info_title = QLabel("选中批次详情")
        info_title.setFont(self._bold_font())
        info_layout.addWidget(info_title)
        self.detail_label = QLabel("请在左侧选择一个批次查看详情")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #666; padding: 10px;")
        info_layout.addWidget(self.detail_label)
        right_layout.addWidget(info_group)

        help_text = QLabel(
            "💡 使用说明：\n\n"
            "1. 抽样完成后，输入批次名称并点击保存\n"
            "2. 保存后，所有抽样数据和复核进度都会被持久化\n"
            "3. 下次打开工具时，双击历史批次可以继续之前的复核工作\n"
            "4. 已复核和未复核的样本会有明确的状态标记\n"
            "5. 批次数据保存在程序目录下的 batches 文件夹中"
        )
        help_text.setStyleSheet(
            "background-color: #e3f2fd; padding: 15px; border-radius: 8px;"
            "border-left: 4px solid #2196F3;"
        )
        help_text.setWordWrap(True)
        right_layout.addWidget(help_text, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.batch_table.itemSelectionChanged.connect(self._on_select_batch)

    def _bold_font(self, size=10):
        f = QFont()
        f.setBold(True)
        f.setPointSize(size)
        return f

    def _refresh_batch_list(self):
        batches = self.batch_manager.list_batches()
        self.batch_table.setRowCount(len(batches))
        for row, batch in enumerate(batches):
            progress_bar_widget = QWidget()
            progress_layout = QHBoxLayout(progress_bar_widget)
            progress_layout.setContentsMargins(2, 2, 2, 2)
            progress = QProgressBar()
            total = batch.get('sample_count', 0)
            reviewed = batch.get('reviewed_count', 0)
            pct = int(reviewed / total * 100) if total > 0 else 0
            progress.setValue(pct)
            progress.setFormat(f"{reviewed}/{total} ({pct}%)")
            progress.setMaximumHeight(20)
            if pct == 100:
                progress.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
            elif pct > 0:
                progress.setStyleSheet("QProgressBar::chunk { background-color: #FF9800; }")
            progress_layout.addWidget(progress)

            self.batch_table.setItem(row, 0, QTableWidgetItem(batch['batch_id']))
            self.batch_table.setItem(row, 1, QTableWidgetItem(batch['batch_name']))
            self.batch_table.setItem(row, 2, QTableWidgetItem(batch['created_time']))
            self.batch_table.setItem(row, 3, QTableWidgetItem(batch['updated_time']))
            self.batch_table.setItem(row, 4, QTableWidgetItem(str(batch.get('sample_count', 0))))
            self.batch_table.setItem(row, 5, QTableWidgetItem(str(batch.get('reviewed_count', 0))))
            self.batch_table.setCellWidget(row, 6, progress_bar_widget)

            for col in range(7):
                item = self.batch_table.item(row, col)
                if item:
                    item.setData(Qt.UserRole, batch['batch_id'])

        if not self.current_data:
            self.btn_save_batch.setEnabled(False)
            self.edit_batch_name.setEnabled(False)
            self.edit_batch_name.setPlaceholderText("请先完成抽样操作后再保存批次")

    def _on_save_current_batch(self):
        if not self.current_data:
            QMessageBox.warning(self, "提示", "当前没有可保存的质检批次数据。\n请先完成会话抽样。")
            return

        batch_name = self.edit_batch_name.text().strip()
        if not batch_name:
            from datetime import datetime
            batch_name = f"质检批次_{datetime.now().strftime('%Y%m%d_%H%M')}"

        note, ok = QInputDialog.getText(self, "备注",
            "请输入批次备注（可选）:",
            QLineEdit.Normal, "")
        if not ok:
            return

        try:
            batch = QualityBatch.create(
                batch_name=batch_name,
                sampled_conversations=self.current_data.get('sampled_conversations', []),
                all_conversations=self.current_data.get('all_conversations', []),
                agents=self.current_data.get('agents', []),
                review_results=self.current_data.get('review_results', {}),
                sampling_params=self.current_data.get('sampling_params', {}),
                note=note
            )
            success = self.batch_manager.save_batch(batch)
            if success:
                self.batch_saved.emit(batch)
                QMessageBox.information(self, "保存成功",
                    f"批次已成功保存！\n\n批次ID: {batch.batch_id}\n批次名称: {batch.batch_name}\n"
                    f"样本数: {len(batch.sampled_conv_ids)}\n"
                    f"保存路径: {self.batch_manager.get_batches_dir()}")
                self._refresh_batch_list()
            else:
                QMessageBox.critical(self, "保存失败", "批次保存失败，请检查文件权限。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存批次时出错: {str(e)}")

    def _on_select_batch(self):
        rows = self.batch_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        batch_id = self.batch_table.item(row, 0).data(Qt.UserRole)
        batch = self.batch_manager.load_batch(batch_id)
        if batch:
            progress = batch.get_review_progress()
            detail = (
                f"📌 批次ID: {batch.batch_id}\n"
                f"📝 批次名称: {batch.batch_name}\n"
                f"⏰ 创建时间: {batch.created_time}\n"
                f"🔄 最后更新: {batch.updated_time}\n"
                f"📊 抽样数: {progress['total']}\n"
                f"✅ 已复核: {progress['reviewed']}\n"
                f"⏳ 待复核: {progress['pending']}\n"
                f"📈 完成进度: {progress['progress']:.1f}%\n"
                f"📄 备注: {batch.note or '无'}"
            )
            self.detail_label.setText(detail)

    def _on_load_selected(self):
        rows = self.batch_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请先选择要加载的批次。")
            return
        row = rows[0].row()
        batch_id = self.batch_table.item(row, 0).data(Qt.UserRole)
        batch = self.batch_manager.load_batch(batch_id)
        if batch:
            reply = QMessageBox.question(self, "确认加载",
                f"确定要加载批次 [{batch.batch_name}] 吗？\n\n"
                f"当前未保存的复核进度将被覆盖。\n"
                f"该批次进度: {batch.get_review_progress()['progress']:.1f}%",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.batch_loaded.emit(batch)
                self.accept()

    def _on_delete_batch(self):
        rows = self.batch_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请先选择要删除的批次。")
            return
        row = rows[0].row()
        batch_id = self.batch_table.item(row, 0).data(Qt.UserRole)
        batch_name = self.batch_table.item(row, 1).text()

        reply = QMessageBox.warning(self, "确认删除",
            f"确定要删除批次 [{batch_name}] 吗？\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success = self.batch_manager.delete_batch(batch_id)
            if success:
                QMessageBox.information(self, "已删除", "批次已删除。")
                self._refresh_batch_list()
                self.detail_label.setText("请在左侧选择一个批次查看详情")
            else:
                QMessageBox.critical(self, "失败", "删除失败。")
