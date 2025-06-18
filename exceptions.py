class LackEnvVariables(Exception):
    """Критическое исключение при нехватке нужных параметров."""


class APIPracticumError(Exception):
    """Исключение при возникновении ошибок при вызове API Практикума."""


class WrongStatus(Exception):
    """Некорректный статус."""
