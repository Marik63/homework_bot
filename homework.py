from http import HTTPStatus
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import HWStatusRaise

load_dotenv()


PRACTICUM_TOKEN = os.getenv('ya_token')
TELEGRAM_TOKEN = os.getenv('tg_token')
TELEGRAM_CHAT_ID = os.getenv('chat_id')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    filename=os.path.expanduser('main.log'),
    encoding='UTF-8',
    filemode='a',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s -'
    '%(message)s - %(funcName)s - %(lineno)d'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Сообщение: {message}. Oтправлено')
    except telegram.error.TelegramError:
        logger.error('Не было доставлено сообщение в чат')
        raise telegram.error.TelegramError(
            'Не было доставлено сообщение в чат')


def get_api_answer(current_timestamp):
    """Извлекаем информацию из Эндпоинта API сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        message = f'Ошибка при запросе к основному API: {error}'
        logging.error(message)
        logger.error(message)
        raise Exception(message)

    if response.status_code != HTTPStatus.OK:
        message = f'код запроса API не равен {HTTPStatus.OK}'
        logger.error(message)
        raise requests.HTTPError(message)

    if response.json() == []:
        logging.error('В ответе от запроса API не может быть пустым')
        raise requests.exceptions.JSONDecodeError(
            'В ответе от запроса API не может быть пустым'
        )
    return response.json()


def check_response(response):
    """Проверяет запрос API на корректность работы.
    возвращая список домашних работ.
    """
    try:
        homework = response['homeworks']
    except KeyError:
        logger.error('Не найден ключ "homeworks"')
        raise KeyError('Не найден ключ "homeworks"')

    if not isinstance(homework, list):
        message = 'Ответ от API не может быть списком'
        logger.error(message)
        raise TypeError(message)
    return homework


def parse_status(homework):
    """Функция извлекает из информации о конкретной.
    домашней работе статус этой работы.
    """
    homework_name = homework['homework_name']
    if homework_name is None:
        logger.error(
            f'ключ {homework_name} не соотвествует ключу "homework_name"')
        raise KeyError(
            f'ключ {homework_name} не соотвествует ключу "homework_name"')

    homework_status = homework['status']
    if homework_status is None:
        logger.error(
            f'ключ {homework_status} не соотвествует ключу "status"')
        raise KeyError(
            f'ключ {homework_status} не соотвествует ключу "status"')

    if homework_status not in HOMEWORK_STATUSES:
        message = f'ключ {homework_status} не найден'
        logging.error(message)
        raise HWStatusRaise(message)

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения."""
    ALL_TOKENS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }

    try:
        return all(ALL_TOKENS.values())
    except Exception:
        for token_name, token in ALL_TOKENS.items():
            if token in ('', None):
                logger.critical(
                    'Отсутствует обязательная переменная окружения:'
                    f'"{token_name}"')
        return False


def main():
    """Основная логика работы бота."""
    try:
        bot = telegram.Bot(TELEGRAM_TOKEN)
        bot.get_chat(TELEGRAM_CHAT_ID)
        current_timestamp = int(time.time())

    except telegram.error.TelegramError as telegram_error:
        logger.error(f'Ошибка в телеграм боте {telegram_error}')
        exit()

    if not check_tokens():
        exit()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                parse_status_result = parse_status(homework)
                send_message(bot, parse_status_result)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе програмы: {error}'
            logger.error(message)
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            time.sleep(RETRY_TIME)
            raise Exception(message)


if __name__ == '__main__':
    main()
