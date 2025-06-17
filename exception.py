class LackEnvVariables(Exception):
    """Критическое исключение при нехватке нужных параметров."""
    
    pass


class APIPracticumError(Exception):
    """Исключение при возникновении ошибок при вызове API Практикума."""
    
    pass


class WrongStatus(Exception):
    """Некорректный статус."""
    
    pass
