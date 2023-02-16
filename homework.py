import logging
import os
import sys
import time
from http import HTTPStatus

import requests  # type: ignore
import telegram

from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    if not all(tokens):
        logger.critical(
            'Отсутствие обязательных переменных '
            'окружения во время запуска бота.'
        )
        raise ValueError(
            'Отсутствие обязательных переменных '
            'окружения во время запуска бота.'
        )
    else:
        return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения {error}')
    else:
        logger.debug(f'send_message {message}')


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload)
        if response.status_code != HTTPStatus.OK:
            logging.error(response.status_code)
            raise AssertionError(response.status_code)
    except Exception as error:
        logger.error(f'Ошибка запроса, {error}')
        raise AssertionError(response.status_code)
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('response')
        raise TypeError('Response не соответствует типу dictionary')
    if 'homeworks' not in response.keys():
        logger.error('response.keys()')
        raise KeyError('Отсутствует ключ - homeworks')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error('homeworks')
        raise TypeError('Homeworks не соответствует типу list')
    if not homeworks:
        logger.error('homeworks')
        raise KeyError('homeworks - пустой')
    return response['homeworks'][0]


def parse_status(homework):
    """Cтатус запрошенной работы."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        logger.error('homework_name')
        raise AssertionError('homework_name')
    status = homework['status']
    if status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[status]
    else:
        logger.error(f'Ключ {status} отсутствует в словаре HOMEWORK_VERDICTS')
        raise KeyError(
            f'Ключ {status} отсутствует в словаре HOMEWORK_VERDICTS'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    last_status = ''

    if check_tokens():
        timestamp = 1674488489
        # timestamp = int(time.time())
        while True:
            try:
                response = get_api_answer(timestamp)
                timestamp = response['current_date']
                if homework := check_response(response):
                    current_status = parse_status(homework)
                    if current_status != last_status:
                        send_message(bot, current_status)
                        last_status = current_status
                    else:
                        logger.debug('Статус работы не изменился')
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
