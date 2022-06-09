class HWStatusRaise(Exception):
    pass


class NoneTokensENV(Exception):
    pass


class SendMessageFailure(Exception):
    """Исключение отправки сообщения."""

    pass


class APIResponseStatusCodeException(Exception):
    """Исключение сбоя запроса к API."""

    pass
