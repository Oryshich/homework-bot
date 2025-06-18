import logging
import logging.handlers
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import apihelper, TeleBot

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
    '%(asctime)s [%(levelname)-8s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
filehandler = logging.handlers.TimedRotatingFileHandler(
    filename=__file__[:-2] + 'log',
    when='midnight',
    interval=1,
    backupCount=14
)
filehandler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка обязательных переменных окружения во время запуска бота."""
    lackvariables = [varname for varname in (
        'PRACTICUM_TOKEN',
        'TELEGRAM_TOKEN',
        'TELEGRAM_CHAT_ID'
    ) if globals()[varname] is None]
    if lackvariables:
        logger.critical(
            f'Нехватка переменных окружения: {', '.join(lackvariables)}.'
            f' Бот остановлен!'
        )
        return False
    return True


def send_message(bot, message):
    """Отправка уведомления в телеграмм."""
    try:
        logger.debug('Сообщение подготовлено к отправке в телеграмм.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено в телеграмм. {message}')
    except apihelper.ApiException as error:
        logger.error(f'Сбой при отправке сообщения в телеграмм: {error}')
        return False
    except requests.exceptions.RequestException as error:
        logger.error(f'Сбой при отправке сообщения в телеграмм: {error}')
        return False
    else:
        return True


def get_api_answer(timestamp):
    """Получение данных от API Практикума."""
    payload = {'from_date': timestamp}
    req_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': payload
    }
    try:
        logger.debug(
            'Отправка запроса к API Практикума по адресу {url},'
            ' заголовок {headers}, параметры {params}'.format(**req_params)
        )
        response = requests.get(**req_params)
    except requests.RequestException as error:
        raise exceptions.APIPracticumError(
            f'Ошибка при запросе к API {error}'
        )
    if response.status_code != HTTPStatus.OK:
        raise exceptions.WrongStatus(f'Статус ответа {response.status_code}.')
    return response.json()


def check_response(response):
    """Проверка ответа API Практикума на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API Практикума не словарь. Получен {type(response)}.'
        )
    if 'homeworks' not in response:
        raise KeyError('Nonexistent key homeworks.')
    homework_value = response.get('homeworks')
    if not isinstance(homework_value, list):
        raise TypeError('Значение homeworks не список.')
    return homework_value


def parse_status(homework):
    """Извлекает статус и вердикт о последней домашней работе."""
    if not isinstance(homework, dict):
        raise TypeError('homework не словарь.')
    if 'status' not in homework:
        raise KeyError('Nonexistent key status.')
    if 'reviewer_comment' not in homework:
        raise KeyError('Nonexistent key reviewer_comment.')
    if 'homework_name' not in homework:
        raise KeyError('Nonexistent key homework_name.')
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Получен неизвестный статус {status}.')
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.info('Бот запущен.')
    if not check_tokens():
        raise exceptions.LackEnvVariables(
            'Нехватка переменных окружения. Бот остановлен!'
        )
    bot = TeleBot(token=TELEGRAM_TOKEN)
    last_dtu = ''
    dtu = ''
    msg = ''
    timestamp = int(time.time())
    while True:
        try:
            answer = get_api_answer(timestamp)
            homeworks = check_response(answer)
            if not homeworks:
                logger.debug('Список работ пуст.')
                continue
            msg = parse_status(homeworks[0])
            dtu = homeworks[0].get('date_updated', last_dtu)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            if dtu != last_dtu:
                if send_message(bot, msg):
                    last_dtu = dtu
                    timestamp = answer.get('current_date', timestamp)
            else:
                logger.debug('Новой информации нет.')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
