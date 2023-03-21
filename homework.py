import logging
import os
import sys
import time
from http import HTTPStatus


import telegram

import requests
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('YAPTOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TGchatid')

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
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.debug(f'Отправлено сообщение: {message}')
    except telegram.TelegramError as error:
        logger.error(error)


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        homework_status = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_status.status_code != HTTPStatus.OK:
            logger.error('Ошибка при запросе к API')
            raise Exception('Ошибка при запросе к API')
        return homework_status.json()
    except Exception as Error:
        logger.error(f'Ошибка {Error} при запросе к API')
        raise Exception(f'Ошибка {Error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ не соответсвует словарю.')
    homework = response.get('homeworks')
    cur_date = response.get('current_date')
    if (homework is None or cur_date is None):
        raise KeyError('Ошибка в получении значений словаря.')
    if not isinstance(homework, list):
        raise TypeError('Ответ API не соответствует ожиданиям.')
    return homework


def parse_status(homework):
    """Извлекает cтатус домашки."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError(f'Нету домашки: {homework_name}')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'что-то сломалось: {homework_status}')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Статус домашки изменился "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Токен отсутствует')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug('Домашка не сдана')
            current_timestamp = response.get(
                'current_date',
                int(time.time()) - RETRY_PERIOD
            )
        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
