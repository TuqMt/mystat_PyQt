import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QListWidget, QGridLayout, QPushButton, QStackedWidget, QTextEdit, QSizePolicy, QScrollArea, QDialog, QFileDialog, QCalendarWidget
)
from PyQt5.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject, QDate
from PyQt5.QtGui import QFont, QTextCharFormat, QColor
from datetime import datetime, timedelta
from core import MyStatSDK
from typing import List


# ---- Worker helpers ----
class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))


# ---- UI Components ----
class Card(QFrame):
    def __init__(self, title, value="—", bg_color="#f5f3ff", text_color="#4b0082"):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 12px;
                padding: 12px;
            }}
            QLabel {{
                color: {text_color};
            }}
        """)
        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()

    def set_value(self, value):
        self.value_label.setText(str(value))


def get_monday_of_week(date: datetime) -> str:
    monday = date - timedelta(days=date.weekday())
    return monday.strftime("%Y-%m-%d")


class HomeworkCard(QFrame):
    def __init__(self, hw_id, title, on_click=None):
        super().__init__()
        self.hw_id = hw_id
        self.title = title
        self.setFixedSize(200, 120)
        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5ff;
                border-radius: 12px;
                padding: 10px;
            }
            QLabel {
                color: #333;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #e0bbff;
                border: none;
                border-radius: 6px;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d1aaff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.label = QLabel(title)
        self.label.setAlignment(Qt.AlignCenter)
        self.btn = QPushButton("Открыть")
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.btn)

        if on_click:
            self.btn.clicked.connect(lambda: on_click(self.hw_id, self.title))


class HomeworkDialog(QDialog):
    def __init__(self, hw_id, title, sdk, parent=None):
        super().__init__(parent)
        self.hw_id = hw_id
        self.sdk = sdk
        self.hw_title = title
        self.selected_file = None  # выбранный файл

        self.setWindowTitle("Домашнее задание")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog {
                background: white;
                border-radius: 12px;
            }
            QLabel {
                font-size: 14px;
                color: #333;
            }
            QPushButton {
                background-color: #e0bbff;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #d1aaff;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 5px;
            }
        """)

        layout = QVBoxLayout(self)

        lbl_title = QLabel(self.hw_title)
        lbl_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(lbl_title)

        btn_open = QPushButton("Открыть задание")
        layout.addWidget(btn_open)

        btn_file = QPushButton("Выбрать файл")
        layout.addWidget(btn_file)

        self.comment = QTextEdit()
        self.comment.setPlaceholderText("Введите комментарий...")
        layout.addWidget(self.comment)

        btn_send = QPushButton("Отправить")
        layout.addWidget(btn_send)

        btn_open.clicked.connect(self.open_task)
        btn_file.clicked.connect(self.select_file)
        btn_send.clicked.connect(self.send_homework)

    def open_task(self):
        try:
            self.sdk.download_homework_by_date(self.hw_title)
            print("Задание загружено")
        except Exception as e:
            print(f"Ошибка при открытии задания: {e}")

    def select_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if file:
            self.selected_file = file
            print(f"Выбран файл: {file}")

    def send_homework(self):
        if not self.selected_file:
            print("Сначала выберите файл!")
            return

        comment = self.comment.toPlainText()
        try:
            self.sdk.upload_homework(self.hw_id, self.selected_file, comment)
            print("ДЗ успешно отправлено")
            self.accept()
        except Exception as e:
            print(f"Ошибка при отправке ДЗ: {e}")


# ---- Main App ----
class MyStatApp(QMainWindow):
    def __init__(self, sdk: MyStatSDK):
        super().__init__()
        self.sdk = sdk
        self.setWindowTitle("MyStat Dashboard")
        self.setGeometry(200, 100, 1200, 650)
        self.setStyleSheet("background-color: white;")

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # ---- Sidebar ----
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(10, 10, 10, 10)
        sidebar.setSpacing(10)

        self.btn_main = QPushButton("Главная")
        self.btn_schedule = QPushButton("Расписание")
        self.btn_hw = QPushButton("ДЗ")
        self.btn_refresh = QPushButton("Обновить")

        for btn in [self.btn_main, self.btn_schedule, self.btn_hw]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e0bbff;
                    border: none;
                    padding: 10px;
                    border-radius: 8px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #d1aaff;
                }
            """)
            sidebar.addWidget(btn)

        sidebar.addStretch()
        self.btn_refresh.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #cce5ff;
                border: none;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #99ccff;
            }
        """)
        sidebar.addWidget(self.btn_refresh)
        main_layout.addLayout(sidebar, 1)

        # ---- Stacked pages ----
        self.pages = QStackedWidget()
        main_layout.addWidget(self.pages, 4)

        # Page 1: Dashboard
        page_dashboard = QWidget()
        dash_layout = QVBoxLayout(page_dashboard)

        self.cards_layout = QGridLayout()
        self.card_tasks = Card("ДЗ", "—", "#e0bbff")
        self.card_overdue = Card("Просрочено", "—", "#ffcccc", "#800000")
        self.card_avg = Card("Средний балл", "—", "#ccffcc", "#006400")
        self.card_attendance = Card("Посещаемость", "—", "#cce5ff", "#003366")

        self.cards_layout.addWidget(self.card_tasks, 0, 0)
        self.cards_layout.addWidget(self.card_overdue, 0, 1)
        self.cards_layout.addWidget(self.card_avg, 0, 2)
        self.cards_layout.addWidget(self.card_attendance, 0, 3)
        dash_layout.addLayout(self.cards_layout)

        leader_label = QLabel("Лидеры")
        leader_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        dash_layout.addWidget(leader_label)

        self.leader_list = QListWidget()
        dash_layout.addWidget(self.leader_list)
        self.pages.addWidget(page_dashboard)

        # Page 2: Schedule
        self._create_schedule_page()

        # Page 3: Homework
        page_hw = QWidget()
        hw_layout = QVBoxLayout(page_hw)
        hw_label = QLabel("Домашние задания")
        hw_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        hw_layout.addWidget(hw_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self.hw_container = QGridLayout(scroll_content)
        self.hw_container.setContentsMargins(10, 10, 10, 10)
        self.hw_container.setSpacing(10)

        scroll_area.setWidget(scroll_content)
        hw_layout.addWidget(scroll_area)
        self.pages.addWidget(page_hw)

        # ---- Signals ----
        self.btn_main.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.btn_schedule.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.btn_hw.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        self.btn_refresh.clicked.connect(self.load_all_data)

        self.pool = QThreadPool.globalInstance()
        self.load_all_data()

    def _create_schedule_page(self):
        page_schedule = QWidget()
        sched_layout = QVBoxLayout(page_schedule)

        schedule_label = QLabel("Расписание")
        schedule_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        sched_layout.addWidget(schedule_label)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.calendar.setStyleSheet("""
            QCalendarWidget QToolButton {
                background-color: #e0bbff;
                color: black;
                font-size: 14px;
                border-radius: 5px;
                margin: 5px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #d1aaff;
            }
            QCalendarWidget QAbstractItemView:enabled {
                selection-background-color: #e0bbff;
                selection-color: black;
                font-size: 13px;
            }
        """)
        sched_layout.addWidget(self.calendar)

        self.day_lessons = QListWidget()
        sched_layout.addWidget(self.day_lessons)

        self.calendar.clicked.connect(self.show_day_schedule)
        self.pages.addWidget(page_schedule)

    def mark_schedule_dates(self):
        if not hasattr(self, "schedule_data"):
            return

        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#e0bbff"))

        for item in self.schedule_data:
            date_str = item.get("date") if isinstance(item, dict) else item
            if date_str:
                d = QDate.fromString(date_str, "yyyy-MM-dd")
                if d.isValid():
                    self.calendar.setDateTextFormat(d, highlight_format)

    def show_day_schedule(self, date):
        self.day_lessons.clear()
        selected_date = date.toString("yyyy-MM-dd")

        lessons = []
        for item in self.schedule_data:
            if isinstance(item, dict) and item.get("date") == selected_date:
                lessons.append(item.get("lesson", "Без названия"))
            elif item == selected_date:
                lessons.append("Урок")

        self.day_lessons.addItems(lessons if lessons else ["Нет занятий"])

    def load_all_data(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Обновление...")
        self.sdk.clear_cache()
        monday = get_monday_of_week(datetime.now())
        worker = Worker(self._fetch_data, monday)
        worker.signals.finished.connect(self._update_ui)
        worker.signals.finished.connect(self._enable_refresh_btn)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _enable_refresh_btn(self, *args):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("Обновить")

    def _fetch_data(self, monday: str):
        return {
            "homework": self.sdk.get_homework(),
            "avg": self.sdk.get_average_score(),
            "leaders": self.sdk.get_leaderboard(),
            "attendance": self.sdk.get_attendance(),
            "schedule": self.sdk.get_schedule(monday),
        }

    def _update_ui(self, data):
        hw = data.get("homework", [0, 0])
        self.card_tasks.set_value(hw[0])
        self.card_overdue.set_value(hw[1])
        self.card_avg.set_value(data.get("avg", "—"))
        self.card_attendance.set_value(data.get("attendance", "—"))

        self.leader_list.clear()
        self.leader_list.addItems(data.get("leaders", ["Нет данных"]))

        self.schedule_data = data.get("schedule", [])
        self.mark_schedule_dates()

        while self.hw_container.count():
            item = self.hw_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        homeworks = self.sdk.get_homeworks_list()
        cols = 4
        row, col = 0, 0

        for hw in homeworks:
            card = HomeworkCard(hw["id"], hw["title"], self._open_hw_dialog)
            self.hw_container.addWidget(card, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

    def _open_hw_dialog(self, hw_id, hw_title):
        dialog = HomeworkDialog(hw_id, hw_title, self.sdk, self)
        dialog.exec_()

    def _on_error(self, message):
        print("Ошибка:", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sdk = MyStatSDK("foros_md93", "gHrh7w*6")
    window = MyStatApp(sdk)
    window.show()
    sys.exit(app.exec_())
