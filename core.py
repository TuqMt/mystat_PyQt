import time
import requests


class MyStatSDK:
    TOKEN_LIFETIME = 7200  # 2 часа
    pause = 0.5

    def __init__(self, username, password, proxies=None):
        self.username = username
        self.password = password
        self.proxies = proxies or {}
        self.session_token = None
        self.token_time = 0

    def login(self):
        """Авторизация и получение токена"""
        time.sleep(self.pause)
        url = 'https://mapi.itstep.org/v1/mystat/auth/login'
        try:
            response = requests.post(url, json={'login': self.username, 'password': self.password}, proxies=self.proxies)
            if response.status_code == 200:
                self.session_token = response.text.strip('"')
                self.token_time = time.time()
                print("[INFO] Токен успешно получен.")
                return True
            else:
                print(f"[ERROR] Ошибка авторизации: {response.status_code} — {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"[EXCEPTION] Ошибка при авторизации: {e}")
            return False

    def _headers(self):
        return {'Authorization': f'Bearer {self.session_token}'}

    def _is_token_valid(self):
        return self.session_token and (time.time() - self.token_time < self.TOKEN_LIFETIME)

    def _get(self, url):
        if not self._is_token_valid():
            if not self.login():
                return None
        try:
            response = requests.get(url, headers=self._headers(), proxies=self.proxies)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ERROR] Ошибка запроса: {response.status_code} — {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[EXCEPTION] Ошибка запроса: {e}")
            return None

    def get_grades(self):
        url = 'https://mapi.itstep.org/v1/mystat/aqtobe/statistic/marks'
        data = self._get(url)
        return [int(item['mark']) for item in data if 'mark' in item] if data else []

    def get_average_score(self):
        """Средний балл за год (берем total_average_point из ответа API)"""
        url = "https://mapi.itstep.org/v1/mystat/aqtobe/statistic/progress?period=year"
        data = self._get(url)  
        if data:
            return round(data.get("total_average_point", 0), 2)
        else:
            return 0

    def get_leaderboard(self):
        url = 'https://mapi.itstep.org/v1/mystat/aqtobe/progress/leader-table'
        data = self._get(url)
        return [item.get("fio_stud") for item in data['group']['top']] if data else []

    def get_homework(self):
        url = 'https://mapi.itstep.org/v1/mystat/aqtobe/count/homework'
        return self._get(url)[2]['counter'] or []

    def get_attendance(self):
        url = 'https://mapi.itstep.org/v1/mystat/aqtobe/statistic/attendance?period=month'
        print(self._get(url))
        return f'{self._get(url)['percentOfAttendance']}%' or []



if __name__ == "__main__":
    sdk = MyStatSDK("foros_md93", "gHrh7w*6")

    if sdk.login():
        print("Оценки:", sdk.get_grades())
        print("Средний балл:", sdk.get_average_score())
        print("Лидеры:", sdk.get_leaderboard())
        print("Домашка:", sdk.get_homework())
        print("Посещаемость:", sdk.get_attendance())
