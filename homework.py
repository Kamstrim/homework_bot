import logging
import os
import sys
import time
from http import HTTPStatus

import requests  # type: ignore
import telegram

from dotenv import load_dotenv

from exceptions import ResponseError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ONE_WEEK_IN_UNIX = 604800

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


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
        return False
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
    except Exception as error:
        logger.error(f'Ошибка запроса, {error}')
        raise ResponseError(f'Ошибка запроса, {error}')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Ошибка HTTPStatus не ОК - {response.status_code}')
        raise AssertionError(response.status_code)
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('response')
        raise TypeError('Response не соответствует типу dictionary')
    if 'homeworks' not in response:
        logger.error('Отсутствует ключ - homeworks')
        raise KeyError('Отсутствует ключ - homeworks')
    if 'current_date' not in response:
        logger.error('Отсутствует ключ - current_date')
        raise KeyError('Отсутствует ключ - current_date')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error('homeworks')
        raise TypeError('Homeworks не соответствует типу list')
    if not homeworks:
        logger.info('Пустой ответ на запрос')
        return None
    return response['homeworks'][0]


def parse_status(homework):
    """Cтатус запрошенной работы."""
    if 'homework_name' not in homework:
        logger.error('Отсутствует ключ - homework_name')
        raise KeyError('Отсутствует ключ - homework_name')
    if 'status' not in homework:
        logger.error('Отсутствует ключ - status')
        raise KeyError('Отсутствует ключ - status')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        logger.error(
            f'Ключ {status} отсутствует в словаре HOMEWORK_VERDICTS'
        )
        raise KeyError(
            f'Ключ {status} отсутствует в словаре HOMEWORK_VERDICTS'
        )

    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    last_status = ''
    last_message_error = ''

    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time()) - ONE_WEEK_IN_UNIX
        while True:
            try:
                response = get_api_answer(timestamp)
                print(response)
                homework = check_response(response)
                timestamp = response['current_date']
                if homework:
                    current_status = parse_status(homework)
                    if current_status != last_status:
                        send_message(bot, current_status)
                        last_status = current_status
                    else:
                        logger.debug('Статус работы не изменился')
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
                if message != last_message_error:
                    send_message(bot, message)
                    last_message_error = message

            finally:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
