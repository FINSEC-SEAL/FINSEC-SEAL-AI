class ProviderError(Exception):
    pass


class ProviderProtocolError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderUnavailableError(ProviderError):
    pass
