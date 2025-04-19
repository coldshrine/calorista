class BaseFatsecretError(Exception):
    def __init__(self, code, message):
        Exception.__init__(self, "Error {0}: {1}".format(code, message))


class GeneralError(BaseFatsecretError):
    def __init__(self, code, message):
        BaseFatsecretError.__init__(self, code, message)


class AuthenticationError(BaseFatsecretError):
    def __init__(self, code, message):
        BaseFatsecretError.__init__(self, code, message)


class ParameterError(BaseFatsecretError):
    def __init__(self, code, message):
        BaseFatsecretError.__init__(self, code, message)


class ApplicationError(BaseFatsecretError):
    def __init__(self, code, message):
        BaseFatsecretError.__init__(self, code, message)