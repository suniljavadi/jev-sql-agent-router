class ProviderError(Exception):
    pass


class SecurityError(Exception):
    pass


class QueryTimeout(Exception):
    pass


class ReviewNotFound(Exception):
    pass


class ReviewConflict(Exception):
    pass