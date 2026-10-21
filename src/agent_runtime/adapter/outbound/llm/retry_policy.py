import httpx
from pycraftcore.http.policy.http_error_policy import is_retryable


def should_retry_model_call(exception: BaseException) -> bool:
    if isinstance(exception, httpx.ReadTimeout):
        return False
    return is_retryable(exception)
