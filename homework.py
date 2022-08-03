import logging
import os
import requests
import sys
import time
import telegram

from http import HTTPStatus

from dotenv import load_dotenv
import exceptions as exc

load_dotenv()

API_RESPONSE_ERROR = (
    'Значение кода возрата "{response}" не соответствует требуемому - "200".'
)
PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TOKEN_ERRORS = (
    'Отстутствует переменная окружения "TELEGRAM_TOKEN"',
    'Отстутствует переменная окружения "TELEGRAM_CHAT_ID"',
    'Отстутствует переменная окружения "PRACTICUM_TOKEN"',
)
STATUS_SUMMARY = 'Изменился статус проверки работы "{name}". ' "\n\n{verdict}"
STATUS_UNEXPECTED = 'Неожиданное значение ключа "status": {status}'
HW_NOT_LIST_ERR = "Домашняя работа приходит не в виде списка."
HW_NOT_IN_LIST = "Домашней работы нет в списке."
RETRY_TIME = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}
SUCCESSFUL_MSG_SENDING = "Сообщение {message} успешно отправлено."
HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}
SEND_MESSAGE_ERROR = ("Ошибка {error} при отправке"
                      "сообщения {message} в Telegram")
TIME_SLEEP = 30

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(SUCCESSFUL_MSG_SENDING.format(message=message))
    except Exception as error:
        raise exc.SendMessageError(
            SEND_MESSAGE_ERROR.format(error=error, message=message)
        )


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception:
        message = "Запрос выполнить не удалось"
        raise exc.AnswerError(message)
    if response.status_code != HTTPStatus.OK:
        raise exc.ResponseError(
            API_RESPONSE_ERROR.format(response=response.status_code)
        )
    response = response.json()
    return response


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) != dict:
        raise TypeError()
    if "homeworks" not in response:
        raise exc.MissingKey(HW_NOT_IN_LIST)
    if not isinstance(response["homeworks"], list):
        raise TypeError(HW_NOT_LIST_ERR)
    return response["homeworks"]


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")
    result_string = f'"{homework_name}". {HOMEWORK_VERDICTS[homework_status]}'
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_UNEXPECTED.format(status=homework_status))
    return f"Изменился статус проверки работы {result_string}"


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы программы."""
    if not check_tokens():
        sys.exit('Ошибка в переменных окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    message_cache = None
    reports_cache = {}

    while True:
        try:
            current_timestamp = int(time.time())
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                for hw in homeworks:
                    status = parse_status(hw)
                    name = hw.get("homework_name")
                    if reports_cache.get(name, "") != status:
                        reports_cache[name] = status
                        send_message(bot, status)
            else:
                logger.debug('Отсутствует новая информация')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if (message_cache != message):
                send_message(bot, message)
                message_cache = message
                logger.error(f'Бот столкнулся с ошибкой запроса: {error}')

        finally:
            time.sleep(RETRY_TIME)


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        filemode="a",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
    )
    main()
