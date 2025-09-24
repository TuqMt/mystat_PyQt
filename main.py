# main_sidebar.py
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QListWidget, QGridLayout, QPushButton, QStackedWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from datetime import datetime, timedelta
from core import MyStatSDK


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


# ---- Main App ----
class MyStatApp(QMainWindow):
    def __init__(self, sdk: MyStatSDK):
        super().__init__()
        self.sdk = sdk
        self.setWindowTitle("MyStat Dashboard")
        self.setGeometry(200, 100, 1100, 650)
        self.setStyleSheet("background-color: white;")

        # Layout: sidebar + main area
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
        page_schedule = QWidget()
        sched_layout = QVBoxLayout(page_schedule)
        schedule_label = QLabel("Расписание")
        schedule_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        sched_layout.addWidget(schedule_label)
        self.schedule_list = QListWidget()
        sched_layout.addWidget(self.schedule_list)
        self.pages.addWidget(page_schedule)

        # Page 3: Homework
        page_hw = QWidget()
        hw_layout = QVBoxLayout(page_hw)
        hw_label = QLabel("Домашние задания")
        hw_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        hw_layout.addWidget(hw_label)
        self.hw_list = QListWidget()
        hw_layout.addWidget(self.hw_list)
        self.pages.addWidget(page_hw)

        # ---- Signals ----
        self.btn_main.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.btn_schedule.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.btn_hw.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        self.btn_refresh.clicked.connect(self.load_all_data)
        # ThreadPool
        self.pool = QThreadPool.globalInstance()

        # Load data
        self.load_all_data()

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

        self.schedule_list.clear()
        self.schedule_list.addItems(data.get("schedule", ["Нет расписания"]))

        self.hw_list.clear()
        self.hw_list.addItems([f"Выполнено: {hw[0]}", f"Просрочено: {hw[1]}"])

    def _on_error(self, message):
        print("Ошибка:", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sdk = MyStatSDK("foros_md93", "gHrh7w*6")
    window = MyStatApp(sdk)
    window.show()
    sys.exit(app.exec_())
