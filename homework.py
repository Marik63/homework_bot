from http import HTTPStatus
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (
    APIStatusCodeError, NoDictKey, ExchangeError, TelegramError
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
        raise TelegramError(
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
    return response.json()


def check_response(response):
    """Проверяет наличие всех ключей в ответе API practicum."""
    if not isinstance(response, dict):
        raise TypeError(
            'В ответе от API нет словаря: '
            f'response = {response}'
        )
    if response.get('homeworks') is None:
        raise NoDictKey(
            'В ответе API отсутствует необходимый ключ "homeworks"!'
        )
    if response.get('current_date') is None:
        raise NoDictKey(
            'В ответе API отсутствует необходимый ключ "current_date"!'
        )
    if not isinstance(response.get('homeworks'), list):
        raise TypeError(
            'В ответе API в ключе "homeworks" нет списка: '
            f'response = {response.get("homeworks")}'
        )
    logging.info(response['homeworks'])
    logging.info('Проверка ответа от API завершена.')
    if len(response.get('homeworks')) == 0:
        logging.info('Список работ пустой или работу еще не взяли на проверку')
    return response['homeworks']


def parse_status(homework):
    """Проверяем статус домашнего задания."""
    logging.info('Начинаем проверку статуса домашнего задания.')
    if homework['homework_name'] is None:
        raise NoDictKey(
            'В ответе API отсутствует необходимый ключ "homework_name"!'
        )
    else:
        homework_name = homework['homework_name']
    if homework['status'] is None:
        raise NoDictKey(
            'В ответе API отсутствует необходимый ключ "status"!'
        )
    else:
        homework_status = homework['status']
    if HOMEWORK_VERDICTS[homework_status] is None:
        raise NoDictKey(
            f'В словаре "HOMEWORK_VERDICTS" не найден ключ {homework_status}!'
        )
    else:
        verdict = HOMEWORK_VERDICTS[homework_status]
    logging.info('Окончание проверки статуса домашнего задания.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяем доступность всех необходимых переменных окружения."""
    ALL_TOKENS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    return all(ALL_TOKENS.values())


# def check_tokens() -> bool:
#     """Проверяем наличие всех необходимых переменных окружения."""
#     tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
#     return all(tokens)


def main() -> None:
    """Основная логика работы бота."""
    global old_message
    if not check_tokens():
        raise SystemExit('Я вышел')
    logging.critical('Всё упало! Зовите админа!1!111')

    bot = telegram.Bot(TELEGRAM_TOKEN)
    logging.info('Запуск бота')
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
