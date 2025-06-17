import logging
import os
import requests
import time
from http import HTTPStatus

from dotenv import load_dotenv
from telebot import TeleBot

import exceptions


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
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка обязательных переменных окружения во время запуска бота."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправка уведомления в телеграмм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено в телеграмм. {message}')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в телеграмм: {error}')


def get_api_answer(timestamp):
    """Получение данных от API Практикума."""
    payload = {'from_date': timestamp}
    try:
        logger.debug(f'Отправка запроса к API Практикума. {payload=}')
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as request_exc:
        logger.error(f'Ошибка при вызове API Практикума. {request_exc}')
        raise exceptions.APIPracticumError('Ошибка при запросе к API')
    if response.status_code != HTTPStatus.OK:
        raise exceptions.WrongStatus(f'Статус ответа {response.status_code}.')
    return response.json()


def check_response(response):
    """Проверка ответа API Практикума на соответствие документации."""
    if not isinstance(response, dict):
        logger.error(
            f'Ответ API Практикума не словарь. Получен {type(response)}.'
        )
        raise TypeError('Ответ API Практикума не словарь.')
    if 'homeworks' not in response:
        logger.error('Ключ homeworks не найден.')
        raise KeyError('Nonexistent key homeworks.')
    homework_value = response.get('homeworks')
    if not isinstance(homework_value, list):
        logger.error('Значение homeworks не список.')
        raise TypeError('Значение homeworks не список.')
    if not homework_value:
        logger.info('Пустой список работ.')
        raise IndexError('Пустой список работ.')
    homework = homework_value[0]
    return homework


def parse_status(homework):
    """Извлекает статус и вердикт о последней домашней работе."""
    if not isinstance(homework, dict):
        logger.error('homework не словарь.')
        raise TypeError()
    if 'status' not in homework:
        logger.error('Ключ status не найден.')
        raise KeyError('Nonexistent key status.')
    if 'reviewer_comment' not in homework:
        logger.error('Ключ reviewer_comment не найден.')
        raise KeyError('Nonexistent key reviewer_comment.')
    if 'homework_name' not in homework:
        logger.error('Ключ homework_name не найден.')
        raise KeyError('Nonexistent key homework_name.')
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        logger.error(f'Получен неизвестный статус {status}.')
        raise KeyError('Nonexistent key status.')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.info('Бот запущен.')
    if not check_tokens():
        lackvariables = [varname for varname in (
            'PRACTICUM_TOKEN',
            'TELEGRAM_TOKEN',
            'TELEGRAM_CHAT_ID'
        ) if globals()[varname] is None]
        msg = f'Нехватка переменных окружения {lackvariables}. Бот остановлен!'
        logger.critical(msg)
        raise exceptions.LackEnvVariables(msg)
    bot = TeleBot(token=TELEGRAM_TOKEN)
    last_msg = ''
    msg = ''
    while True:
        try:
            timestamp = int(time.time())
            answer = get_api_answer(timestamp)
            last_homework = check_response(answer)
            msg = parse_status(last_homework)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            if msg != last_msg:
                last_msg = msg
                send_message(bot, msg)
            else:
                logger.debug('Новой информации нет.')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
