"""Excepciones de la librería."""


class SmartCityError(Exception):
    """Error devuelto por la API (o de conexión, con ``status = None``).

    Atributos: ``status`` (código HTTP), ``message`` (mensaje del servidor), ``method`` y ``path``.
    """

    def __init__(self, message, status=None, method=None, path=None):
        self.message = message
        self.status = status
        self.method = method
        self.path = path
        where = f"{method} {path}" if method else ""
        code = f" -> {status}" if status is not None else ""
        super().__init__(f"{where}{code}: {message}" if where else message)


class SmartCityConnectionError(SmartCityError):
    """No se pudo contactar con el servidor (apagado, URL incorrecta, sin red...)."""


class ValidationError(SmartCityError):
    """400 / 422: los datos enviados no son válidos (o no hay calle cerca del punto)."""


class AuthError(SmartCityError):
    """401: falta el token o no es válido."""


class ForbiddenError(SmartCityError):
    """403: acción bloqueada en este servidor (por ejemplo, ``LOCK_PARAMS=1``)."""


class NotFoundError(SmartCityError):
    """404: el recurso (sensor, semáforo, calle, línea, restricción...) no existe."""


class PayloadTooLargeError(SmartCityError):
    """413: el cuerpo de la petición supera 64 KB."""


_BY_STATUS = {400: ValidationError, 401: AuthError, 403: ForbiddenError, 404: NotFoundError,
              413: PayloadTooLargeError, 422: ValidationError}


def error_for_status(status, message, method, path):
    return _BY_STATUS.get(status, SmartCityError)(message, status=status, method=method, path=path)
