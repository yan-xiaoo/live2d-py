import time

__enable = True

__logLevel = 0


def enableLog(v: bool):
    global __enable
    __enable = v


def isLogEnabled() -> bool:
    return __enable


def setLogLevel(level: int) -> None:
    """设置日志等级，兼容最低支持的 Python 3.8 语法。"""
    global __logLevel
    __logLevel = level
    if __logLevel == 0:
        LOGD("[Log] Level=DEBUG")
    elif __logLevel == 1:
        LOGI("[Log] Level=INFO")
    elif __logLevel == 2:
        LOGW("[Log] Level=WARN")
    elif __logLevel == 3:
        LOGE("[Log] Level=ERROR")



def getLogLevel() -> int:
    return __logLevel


def LOGD(*args, **kwargs):
    if __enable and 0 >= __logLevel:
        print(
            time.strftime(f"[D] "),
            *args,
            **kwargs
        )


def LOGI(*args, **kwargs):
    if __enable and 1 >= __logLevel:
        print(
            time.strftime("[I] "),
            *args,
            **kwargs
        )


def LOGW(*args, **kwargs):
    if __enable and 2 >= __logLevel:
        print(
            time.strftime(f"[W] "),
            *args,
            **kwargs
        )


def LOGE(*args, **kwargs):
    if __enable and 3 >= __logLevel:
        print(
            time.strftime(f"[E] "),
            *args,
            **kwargs
        )
