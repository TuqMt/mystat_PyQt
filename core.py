import time
import requests
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from typing import List

logger = logging.getLogger("MyStatSDK")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class MyStatSDK:
    TOKEN_LIFETIME = 7200  # 2 часа — время жизни токена
    pause = 0.5  # задержка между запросами
    REQUEST_TIMEOUT = 8  # seconds

    def __init__(self, username: str, password: str, proxies: Dict[str, str] = None):
        """
        Инициализация SDK:
        :param username: логин пользователя
        :param password: пароль пользователя
        :param proxies: словарь прокси, например {'http': 'http://...', 'https': 'https://...'}
        """
        self.username = username
        self.password = password
        self.proxies = proxies or {}
        self.session_token: Optional[str] = None
        self.token_time: float = 0.0
        self._last_get_cache: Dict[str, Any] = {}

    def login(self) -> bool:
        """
        Авторизация на сервере MyStat.
        Получает Bearer токен и сохраняет время получения.
        Возвращает True при успехе.
        """
        time.sleep(self.pause)
        url = "https://mapi.itstep.org/v1/mystat/auth/login"
        try:
            r = requests.post(
                url,
                json={"login": self.username, "password": self.password},
                proxies=self.proxies,
                timeout=self.REQUEST_TIMEOUT,
            )
            if r.status_code == 200:
                # Токен приходит в теле как строка "...", поэтому strip('"')
                self.session_token = r.text.strip('"')
                self.token_time = time.time()
                logger.info("Токен успешно получен.")
                return True
            logger.error("Ошибка авторизации: %s — %s", r.status_code, r.text)
            return False
        except requests.RequestException as e:
            logger.exception("Ошибка при авторизации: %s", e)
            return False

    def _headers(self) -> Dict[str, str]:
        """Возвращает заголовки для авторизации."""
        return {"Authorization": f"Bearer {self.session_token}"} if self.session_token else {}

    def _is_token_valid(self) -> bool:
        """Проверяет, действителен ли текущий токен (по времени)."""
        return bool(self.session_token) and (time.time() - self.token_time < self.TOKEN_LIFETIME)

    def clear_cache(self) -> None:
        """Очищает внутренний кеш для _get (вызывать перед новой загрузкой)."""
        self._last_get_cache.clear()

    def _get(self, url: str, use_cache: bool = True) -> Optional[Any]:
        """
        Универсальный GET с таймаутом, кешем и авто-логином.
        :param url: полный URL
        :param use_cache: если True, ответ кешируется в рамках экземпляра
        :return: распарсенный JSON или None
        """
        if use_cache and url in self._last_get_cache:
            return self._last_get_cache[url]

        if not self._is_token_valid():
            if not self.login():
                return None

        try:
            r = requests.get(url, headers=self._headers(), proxies=self.proxies, timeout=self.REQUEST_TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                if use_cache:
                    self._last_get_cache[url] = data
                return data
            logger.error("Ошибка запроса %s: %s — %s", url, r.status_code, r.text)
            return None
        except requests.RequestException as e:
            logger.exception("Ошибка запроса %s: %s", url, e)
            return None

    # ---------------- API methods ----------------

    def get_grades(self) -> List[int]:
        """Возвращает список оценок (ints)."""
        url = "https://mapi.itstep.org/v1/mystat/aqtobe/statistic/marks"
        data = self._get(url)
        if not data:
            return []
        if isinstance(data, list):
            out: List[int] = []
            for item in data:
                if isinstance(item, dict) and "mark" in item:
                    try:
                        out.append(int(item["mark"]))
                    except Exception:
                        continue
            return out
        logger.warning("get_grades: неожиданный формат ответа")
        return []

    def get_average_score(self) -> float:
        """Берёт total_average_point из API (годовой)."""
        url = "https://mapi.itstep.org/v1/mystat/aqtobe/statistic/progress?period=year"
        data = self._get(url)
        if isinstance(data, dict):
            try:
                return round(float(data.get("total_average_point", 0) or 0), 2)
            except Exception:
                return 0.0
        return 0.0

    def get_leaderboard(self) -> List[str]:
        """
        Возвращает список имён лидеров (fio_stud).
        Поддерживает несколько возможных форматов ответа.
        """
        url = "https://mapi.itstep.org/v1/mystat/aqtobe/progress/leader-table"
        data = self._get(url)
        leaders: List[str] = []
        if isinstance(data, dict):
            group = data.get("group", {})
            top = group.get("top", [])
            if isinstance(top, list):
                for item in top:
                    if isinstance(item, dict):
                        leaders.append(item.get("fio_stud", "Неизвестно"))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    leaders.append(item.get("fio_stud", "Неизвестно"))
        return leaders

    def get_homework(self) -> List[int]:
        """
        Возвращает пару [done_count, overdue_count].
        Обрабатывает разные структуры ответа.
        """
        url = "https://mapi.itstep.org/v1/mystat/aqtobe/count/homework"
        data = self._get(url)
        if not data:
            return [0, 0]

        # Если список — пытаемся получить ожидаемые индексы, иначе парсим
        if isinstance(data, list):
            try:
                # часто структура: [.., {counter: X}, {counter: Y}, ...]
                done = int(data[1].get("counter", 0) or 0) + int(data[2].get("counter", 0) or 0)
                overdue = int(data[2].get("counter", 0) or 0)
                return [done, overdue]
            except Exception:
                # fallback — агрегация по полям
                done = overdue = 0
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    cnt = int(item.get("counter", 0) or 0)
                    status = item.get("status") or item.get("type") or ""
                    if str(status).lower() == "overdue":
                        overdue += cnt
                    else:
                        done += cnt
                return [done, overdue]

        # Если словарь — ищем вложенные поля
        if isinstance(data, dict):
            # варианты: {"data": [...]} или {"counts": {...}}
            arr = data.get("data") or data.get("counts") or data
            if isinstance(arr, list):
                # переиспользуем логику парсинга списка
                return self._parse_homework_list(arr)
            if isinstance(arr, dict):
                done = int(arr.get("done", 0) or 0)
                overdue = int(arr.get("overdue", 0) or 0)
                return [done, overdue]

        return [0, 0]

    def _parse_homework_list(self, arr: List[Any]) -> List[int]:
        done = overdue = 0
        for item in arr:
            if not isinstance(item, dict):
                continue
            cnt = int(item.get("counter", 0) or 0)
            status = item.get("status") or item.get("type") or ""
            if str(status).lower() == "overdue":
                overdue += cnt
            else:
                done += cnt
        return [done, overdue]

    def get_attendance(self) -> str:
        """Возвращает строку вида '92.3%' (месячная посещаемость)."""
        url = "https://mapi.itstep.org/v1/mystat/aqtobe/statistic/attendance?period=month"
        data = self._get(url)
        if isinstance(data, dict):
            # возможные ключи
            percent = data.get("percentOfAttendance") or data.get("percent") or data.get("percent_of_attendance")
            if percent is None:
                # возможно структура {"data": {...}}
                inner = data.get("data")
                if isinstance(inner, dict):
                    percent = inner.get("percentOfAttendance") or inner.get("percent")
            try:
                return f"{float(percent):.1f}%"
            except Exception:
                return str(percent or "0%")
        return "0%"


    def get_schedule(self, date_filter: str = "2025-09-15") -> List[str]:
        """Получить расписание недели, отсортированное по дате (по возрастанию)."""
        url = f"https://mapi.itstep.org/v1/mystat/aqtobe/schedule/get-month?type=week&date_filter={date_filter}"
        data = self._get(url)
        lessons_list = []

        # Вспомогательный парсер даты
        def parse_date(d):
            try:
                return datetime.strptime(d, "%Y-%m-%d")
            except Exception:
                return None

        # Сбор всех уроков
        all_lessons = []
        if isinstance(data, dict):
            lessons = data.get("data", []) if data.get("data") else []
            if isinstance(lessons, list):
                all_lessons.extend(lessons)
        elif isinstance(data, list):
            all_lessons.extend(data)

        # Сортируем по дате
        all_lessons.sort(key=lambda x: parse_date(x.get("date", "")) or datetime.max)

        # Формируем строки
        for lesson in all_lessons:
            if isinstance(lesson, dict):
                date = lesson.get("date", "Неизвестно")
                subject = lesson.get("subject", "Без названия")
                lessons_list.append(f"{date} — {subject}")

        return lessons_list
