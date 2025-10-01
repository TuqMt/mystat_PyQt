# main_sidebar.py
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QListWidget, QGridLayout, QPushButton, QStackedWidget, QTextEdit,
    QSizePolicy, QScrollArea, QDialog, QFileDialog, QCalendarWidget, QToolButton
)
from PyQt5.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject, QDate, QLocale
from PyQt5.QtGui import QFont, QTextCharFormat, QColor, QIcon
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
        self.setMinimumWidth(420)
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
            # пытаемся загрузить прикреплённые файлы (sdk должен уметь это)
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
        self.setGeometry(200, 100, 1200, 680)
        self.setStyleSheet("background-color: white;")
        self.setWindowIcon(QIcon("favicon.ico"))
        self._schedule_by_date = {}

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

        # Page 2: Schedule (calendar view)
        page_schedule = QWidget()
        sched_layout = QVBoxLayout(page_schedule)

        # top nav (prev / month label / next)
        nav_layout = QHBoxLayout()
        self.prev_btn = QToolButton()
        self.prev_btn.setText("◀")
        self.prev_btn.setFixedSize(34, 34)
        self.next_btn = QToolButton()
        self.next_btn.setText("▶")
        self.next_btn.setFixedSize(34, 34)
        self.month_label = QLabel("")
        self.month_label.setAlignment(Qt.AlignCenter)
        self.month_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.month_label, stretch=1)
        nav_layout.addWidget(self.next_btn)
        sched_layout.addLayout(nav_layout)

        # calendar
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.setNavigationBarVisible(False)  # прячем стандартный бар (используем свои кнопки)
        self.calendar.setLocale(QLocale(QLocale.Russian))
        self.calendar.setStyleSheet("""
            QCalendarWidget QAbstractItemView {
                selection-background-color: #e0bbff;
                font-size: 12px;
            }
        """)
        sched_layout.addWidget(self.calendar)

        # lessons list for selected day
        self.schedule_list = QListWidget()
        sched_layout.addWidget(self.schedule_list)

        self.pages.addWidget(page_schedule)

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

        # signals
        self.btn_main.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.btn_schedule.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.btn_hw.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        self.btn_refresh.clicked.connect(self.load_all_data)

        self.prev_btn.clicked.connect(lambda: self.shift_month(-1))
        self.next_btn.clicked.connect(lambda: self.shift_month(1))
        self.calendar.selectionChanged.connect(self.show_day_lessons)

        self.pool = QThreadPool.globalInstance()
        self.load_all_data()

        # установить начальную метку месяца
        self.update_month_label()

    # ---- data loading ----
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
        # собираем расписание на 8 недель вперёд (можно поменять число)
        all_schedule = []
        start = datetime.strptime(monday, "%Y-%m-%d")

        for i in range(8):  # 8 недель
            week_start = start + timedelta(weeks=i)
            week_str = week_start.strftime("%Y-%m-%d")
            week_schedule = self.sdk.get_schedule(week_str)
            if week_schedule:
                all_schedule.extend(week_schedule)

        return {
            "homework": self.sdk.get_homework(),
            "homeworks_list": self.sdk.get_homeworks_list(),
            "avg": self.sdk.get_average_score(),
            "leaders": self.sdk.get_leaderboard(),
            "attendance": self.sdk.get_attendance(),
            "schedule": all_schedule,  
        }



    # ---- UI update ----
    def _update_ui(self, data):
        # cards
        hw = data.get("homework", [0, 0])
        self.card_tasks.set_value(hw[0])
        self.card_overdue.set_value(hw[1])
        self.card_avg.set_value(data.get("avg", "—"))
        self.card_attendance.set_value(data.get("attendance", "—"))

        # leaders
        self.leader_list.clear()
        self.leader_list.addItems(data.get("leaders", ["Нет данных"]))

        # parse schedule -> fill self._schedule_by_date (date_str -> list[str])
        raw_schedule = data.get("schedule", []) or []
        mapped = {}
        for item in raw_schedule:
            # item может быть строкой "YYYY-MM-DD — subject" или dict с полем date/subject
            if isinstance(item, dict):
                date = item.get("date")
                # пытаемся получить человека/предмет
                subject = item.get("subject") or item.get("lesson") or item.get("theme") or ""
                line = f"{date} — {subject}" if subject else date
            elif isinstance(item, str):
                # ожидаем формат "YYYY-MM-DD ...", разбираем первое поле как дату
                parts = item.split("—", 1)
                if len(parts) == 2:
                    date = parts[0].strip()
                    subject = parts[1].strip()
                    line = f"{subject}"
                else:
                    tokens = item.split()
                    date = tokens[0] if tokens else ""
                    subject = " ".join(tokens[1:]) if len(tokens) > 1 else ""
                    line = subject or item
            else:
                continue

            if not date:
                continue
            mapped.setdefault(date, []).append(line)

        # сохраняем в атрибут для использования при клике
        self._schedule_by_date = mapped

        # подсветка дат
        self.highlight_schedule_dates()

        # обновляем метку месяца (если пользователь на странице)
        self.update_month_label()

        # домашки (карточки)
        while self.hw_container.count():
            item = self.hw_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        homeworks = data.get("homeworks_list", [])

        cols = 4
        row = 0
        col = 0
        for hw in homeworks:
            title = hw.get("title") if isinstance(hw, dict) else str(hw)
            hw_id = hw.get("id") if isinstance(hw, dict) else None
            card = HomeworkCard(hw_id, title, self._open_hw_dialog)
            self.hw_container.addWidget(card, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

        # сразу показать уроки для текущей выбранной даты
        self.show_day_lessons()

    # ---- calendar helper ----
    def highlight_schedule_dates(self):
        """Подсветить все даты, для которых есть записи в self._schedule_by_date."""
        # очищаем предыдущие форматы (заниженно — чищу всё календаря)
        default_fmt = QTextCharFormat()
        # получить диапазон текущего отображаемого месяца и очистить только его — но проще очистить всё:
        # NOTE: setDateTextFormat(QDate(), fmt) не очищает — применяем для каждой существующей даты замену.
        # Для простоты — перезапишем только даты из self._schedule_by_date
        # (Если нужно, можно хранить старые форматы и восстанавливать)
        highlight = QTextCharFormat()
        highlight.setBackground(QColor("#e6f0ff"))
        highlight.setForeground(QColor("#000000"))
        highlight.setFontWeight(QFont.Bold)

        # Сначала очистим формат для всех известных дат (чтобы избежать наслоений)
        # (проходим календарь: 1..31 текущего года/месяца — но это тяжеловато, пропустим)
        # Просто установим формат для нужных дат
        for date_str in self._schedule_by_date.keys():
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                qd = QDate(d.year, d.month, d.day)
                self.calendar.setDateTextFormat(qd, highlight)
            except Exception as e:
                # если парсинг не удался — пропустить
                # print("highlight parse error:", e)
                continue

    def show_day_lessons(self):
        """Показать уроки за выбранный день (день, не неделя)."""
        self.schedule_list.clear()
        sel = self.calendar.selectedDate()
        date_str = sel.toString("yyyy-MM-dd")
        lessons = self._schedule_by_date.get(date_str, [])
        if lessons:
            # уроки уже содержат описания (subject lines), добавляем красиво
            self.schedule_list.addItems(lessons)
        else:
            self.schedule_list.addItem("Нет уроков")

    def shift_month(self, offset: int):
        """Сдвинуть отображаемый месяц в календаре (offset в месяцах)."""
        cur = self.calendar.selectedDate()
        new = cur.addMonths(offset)
        self.calendar.setSelectedDate(new)
        # прокрутка view: QCalendarWidget автоматически покажет нужный месяц при установке selectedDate
        self.update_month_label()
        # при смене месяца можно заново подсветить даты (подсветка основана на полных датах, потому ничего не нужно делать)

    def update_month_label(self):
        sel = self.calendar.selectedDate()
        # "MMMM yyyy" выдаёт полный месяц (на локале календаря)
        txt = sel.toString("MMMM yyyy")
        # приведём первую букву в верхний регистр (обычно уже так)
        if txt:
            txt = txt[0].upper() + txt[1:]
        self.month_label.setText(txt)

    def _open_hw_dialog(self, hw_id, hw_title):
        dialog = HomeworkDialog(hw_id, hw_title, self.sdk, self)
        dialog.exec_()

    def _on_error(self, message):
        print("Ошибка:", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sdk = MyStatSDK("foros_md93", "gHrh7w*6")  # аккуратно с логином/паролем
    window = MyStatApp(sdk)
    window.show()
    sys.exit(app.exec_())
