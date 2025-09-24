import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QListWidget, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from core import MyStatSDK  # <-- подключаем SDK


class Card(QFrame):
    def __init__(self, title, value="—", bg_color="#f5f3ff", text_color="#4b0082"):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 12px;
                padding: 15px;
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


class MyStatApp(QMainWindow):
    def __init__(self, sdk):
        super().__init__()
        self.sdk = sdk
        self.setWindowTitle("MyStat Dashboard")
        self.setGeometry(200, 100, 1000, 600)
        self.setStyleSheet("background-color: white;")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ---- Верхние карточки ----
        self.cards_layout = QGridLayout()
        self.card_tasks = Card("Задачи", "—", "#e0bbff")
        self.card_overdue = Card("Просрочено", "—", "#ffcccc", "#800000")
        self.card_avg = Card("Средний балл", "—", "#ccffcc", "#006400")
        self.card_attendance = Card("Посещаемость", "—", "#cce5ff", "#003366")

        self.cards_layout.addWidget(self.card_tasks, 0, 0)
        self.cards_layout.addWidget(self.card_overdue, 0, 1)
        self.cards_layout.addWidget(self.card_avg, 0, 2)
        self.cards_layout.addWidget(self.card_attendance, 0, 3)
        main_layout.addLayout(self.cards_layout)

        # ---- Список лидеров ----
        leader_label = QLabel("Лидеры")
        leader_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        leader_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(leader_label)

        self.leader_list = QListWidget()
        self.leader_list.setStyleSheet("""
            QListWidget {
                background: #f5f3ff;
                border: none;
                border-radius: 8px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 6px;
                font-size: 14px;
            }
            QListWidget::item:selected {
                background: #e0bbff;
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(self.leader_list)

        # Загружаем данные
        self.load_data()

    def load_data(self):
        if self.sdk.login():
            self.card_avg.set_value(self.sdk.get_average_score())
            self.card_tasks.set_value("28")
            self.card_overdue.set_value(self.sdk.get_homework())  
            self.card_attendance.set_value(self.sdk.get_attendance())

            leaders = self.sdk.get_leaderboard()
            self.leader_list.clear()
            self.leader_list.addItems(leaders)
        else:
            self.card_avg.set_value("Ошибка")
            self.card_tasks.set_value("Ошибка")
            self.card_overdue.set_value("Ошибка")
            self.card_attendance.set_value("Ошибка")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sdk = MyStatSDK("foros_md93", "gHrh7w*6")
    window = MyStatApp(sdk)
    window.show()
    sys.exit(app.exec_())

