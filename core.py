""" CДЕЛАТЬ API ДЛЯ ПОЛУЧЕНИЯ НАЗВАНИЙ ДЗ И СКАЧИВАТЬ ПО ДАТЕ
    ДИЗАЙН С МАЙСТАТ 
        
    """
import time
import requests
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from typing import List
import os

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
    def get_homeworks_names(self) -> List[str]:
        url = f"https://mapi.itstep.org/v1/mystat/aqtobe/homework/list?status=3&limit=100&sort=-hw.time"
        data = self._get(url)
        lessons_list = []
        if isinstance(data, dict):
            lessons = data.get("data", []) if data.get("data") else []
            if isinstance(lessons, list):
                for lesson in lessons:
                    if isinstance(lesson, dict):
                        subject = lesson.get("creation_time", "Без названия")
                        lessons_list.append(subject)

        return lessons_list
    
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
    
    def download_homework_by_date(self, date_filter: str, folder: str = "homeworks"):
        """
        Скачивает ДЗ только за указанную дату.
        :param date_filter: Дата в формате YYYY-MM-DD
        :param folder: Папка для сохранения файлов
        """
        import requests
        import os
        from datetime import datetime

        os.makedirs(folder, exist_ok=True)

        url = "https://mapi.itstep.org/v1/mystat/aqtobe/homework/list?status=3&limit=100&sort=-hw.time"
        data = self._get(url, use_cache=False)
        if not data or "data" not in data:
            print("Ошибка: не удалось получить список ДЗ")
            return

        homeworks = data.get("data", [])
        target_hw = None
        for hw in homeworks:
            hw_time = hw.get("creation_time")
            if not hw_time:
                continue

            try:
                dt = datetime.fromtimestamp(int(hw_time))
            except:
                try:
                    dt = datetime.fromisoformat(str(hw_time).replace("Z", "+00:00"))
                except:
                    continue

            if dt.strftime("%Y-%m-%d") == date_filter:
                target_hw = hw
                break

        if not target_hw:
            print(f"Нет ДЗ за дату {date_filter}")
            return

        f_url = target_hw.get("file_path")
        if not f_url:
            print(f"У ДЗ за {date_filter} нет прикреплённого файла")
            return

        try:
            r = requests.get(f_url, headers=self._headers(), stream=True, timeout=10)
            if r.status_code == 200:
                cd = r.headers.get("Content-Disposition", "")
                ext = ""
                if "filename=" in cd:
                    fname = cd.split("filename=")[-1].strip().strip('"')
                    if "." in fname:
                        ext = "." + fname.split(".")[-1]

                if not ext and "." in f_url:
                    ext = "." + f_url.split(".")[-1]

                filename = f"{date_filter}{ext or '.bin'}"
                filepath = os.path.join(folder, filename)

                counter = 1
                while os.path.exists(filepath):
                    filename = f"{date_filter}_{counter}{ext or '.bin'}"
                    filepath = os.path.join(folder, filename)
                    counter += 1

                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                print(f"Сохранено: {filepath}")
            else:
                print(f"Ошибка загрузки {f_url}: {r.status_code}")

        except Exception as e:
            print(f"Не удалось скачать {f_url}: {e}")

    def get_id_hw(self):
        url = f"https://mapi.itstep.org/v1/mystat/aqtobe/homework/list?status=3&limit=100&sort=-hw.time"
        data = self._get(url)
        ids_list = []
        if isinstance(data, dict):
            lessons = data.get("data", []) if data.get("data") else []
            if isinstance(lessons, list):
                for lesson in lessons:
                    if isinstance(lesson, dict):
                        subject = lesson.get("id", "Без названия")
                        ids_list.append(subject)

        return ids_list

    def get_homeworks_list(self):
        url = "https://mapi.itstep.org/v1/mystat/aqtobe/homework/list?status=3&limit=100&sort=-hw.time"
        data = self._get(url)
        result = []
        if isinstance(data, dict):
            lessons = data.get("data", []) if data.get("data") else []
            if isinstance(lessons, list):
                for lesson in lessons:
                    if isinstance(lesson, dict):
                        hw_id = lesson.get("id")
                        title = lesson.get("creation_time", "Без названия")
                        if hw_id is not None:
                            result.append({"id": hw_id, "title": title})
        return result

    def upload_to_fs(self, file_path: str, directory: str = None) -> str:
        """Загружает файл на файловый сервер ITStep и возвращает URL"""

        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл '{file_path}' не найден")

        fs_info = self.upls_fs()
        token = fs_info["token"]
        if directory is None:
            directory = fs_info["directories"]["homeworkDirId"]

        hosts = [
            "https://fsx3.itstep.org",
            "https://fsx2.itstep.org",
            "https://fsx1.itstep.org",
            "https://fs3.itstep.org",
            "https://fs2.itstep.org",
            "https://fs1.itstep.org",
        ]

        headers = {
            "Authorization": f"Bearer {token}"
        }

        errors = []
        for base in hosts:
            url = f"{base}/api/v1/files"
            try:
                with open(file_path, "rb") as f:
                    files = {
                        "files[]": (os.path.basename(file_path), f)
                    }
                    data = {
                        "directory": directory
                    }
                    r = requests.post(url, headers=headers, data=data, files=files, timeout=40)
                    if r.status_code == 200:
                        js = r.json()
                        if isinstance(js, list) and js and js[0].get("link"):
                            return js[0]["link"]
                    errors.append(f"{url} — HTTP {r.status_code}: {r.text[:200]}")
            except Exception as e:
                errors.append(f"{url} — {e}")

        raise RuntimeError("FS upload failed. Tried:\n" + "\n".join(errors))


    def upload_homework(self, homework_id: int, file_path: str, comment: str = ""):
        """Загружает ДЗ с файлом: сначала на FS, потом отправляет ссылку в MyStat"""
        if not file_path or not os.path.exists(file_path):
            print("Файл не выбран или не существует")
            return

        try:

            file_url = self.upload_to_fs(file_path)

            url = f"https://mapi.itstep.org/v1/mystat/aqtobe/homework/create"
            payload = {
                "answerText": comment,
                "filename": file_url,
                "id": homework_id
            }

            r = requests.post(url, headers=self._headers(), json=payload, timeout=60)
            if r.status_code in (200, 201):
                print(f"ДЗ {homework_id} успешно отправлено: {file_url}")
            else:
                print(f"Ошибка при создании ДЗ: {r.status_code} — {r.text}")

        except Exception as e:
            print(f"Ошибка при загрузке ДЗ: {e}")


    def upls_fs(self):
        url='https://mapi.itstep.org/v1/mystat/aqtobe/user/file-token'
        data = self._get(url)
        return data #['directories']['homeworkDirId']

if __name__ == "__main__":
    sdk = MyStatSDK("foros_md93", "gHrh7w*6")
    if sdk.login():
        print(sdk.upls_fs())
        sdk.get_homeworks_names()
        print(sdk.get_homeworks_names())
        
    else:
        print("Не удалось войти в систему.")


      
