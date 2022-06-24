from http import HTTPStatus
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (
    APIStatusCodeError, HWStatusRaise, ExchangeError, EmptyError
)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('ya_token')
TELEGRAM_TOKEN = os.getenv('tg_token')
TELEGRAM_CHAT_ID = os.getenv('chat_id')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
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
old_message = ''


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.info('Сообщение отправлено')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Сообщение: {message}. Oтправлено')
    except Exception as error:
        raise telegram.error.TelegramError(
            f'Не отправляются сообщения, {error}'
        )


def get_api_answer(current_timestamp):
    """Извлекаем информацию из Эндпоинта API сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logging.info('Начало запроса')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as exc:
        raise ExchangeError(f'Ошибка подключения к телеграмм: {exc}') from exc

    if response.status_code != HTTPStatus.OK:
        raise APIStatusCodeError(
            'Неверный ответ сервера: '
            f'http code = {response.status_code}; '
            f'reason = {response.reason}; '
            f'content = {response.text}'
        )

    if response.json() == []:
        raise EmptyError(
            'В ответе от запроса API новый статус'
            'не появился—список работ пуст'
        )
    return response.json()


def check_response(response):
    """Проверяет запрос API."""
    if not isinstance(response, dict):
        raise TypeError('Ошибка типа данных в response')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ошибка типа данных переменной homeworks')
    if len(homeworks) != 0:
        return homeworks
    else:
        raise IndexError('Список работ пуст')


def parse_status(homework):
    """Извлекаем статус домашки."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        raise KeyError('Не найден ключ "homework_name"')
    if homework_name is None:
        raise KeyError(f'Ключ {"homework_name"} не найден')
    try:
        homework_status = homework['status']
    except KeyError:
        raise KeyError('Не найден ключ "status"')
    if homework_status is None:
        raise KeyError(f'Ключ {"homework_status"} не найден')

    if homework_status not in HOMEWORK_VERDICTS:
        message = f'ключ {homework_status} не найден'
        raise HWStatusRaise(message)

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения."""
    ALL_TOKENS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    return all(ALL_TOKENS.values())


def main():
    """Основная логика работы бота."""
    global old_message
    if not check_tokens():
        raise SystemExit('Я вышел')
    logging.critical('Всё упало! Зовите админа!1!111')

    bot = telegram.Bot(TELEGRAM_TOKEN)
    bot.get_chat(TELEGRAM_CHAT_ID)
    current_timestamp = int(time.time()) - RETRY_TIME

    while True:
        try:
            if type(current_timestamp) is not int:
                raise SystemError('В функцию передана не дата')
            response = get_api_answer(current_timestamp)
            response = check_response(response)

            if len(response) > 0:
                homework_status = parse_status(response[0])
                if homework_status is not None:
                    send_message(bot, homework_status)
            else:
                logger.debug('нет новых статусов')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != old_message:
                bot.send_message(TELEGRAM_CHAT_ID, message)
                old_message = message
        finally:
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
