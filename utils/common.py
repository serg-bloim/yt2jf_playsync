from itertools import islice
from typing import Callable, TypeVar, Iterable


def chunked(iterable, size):
    it = iter(iterable)  # Convert to iterator
    return iter(lambda: list(islice(it, size)), [])


def get_nested_value(d, *keys):
    for key in keys:
        if hasattr(d, '__getitem__') and hasattr(d, '__contains__') and key in d:
            d = d[key]
        else:
            return None
    return d


T = TypeVar('T')


class LazyProperty[T]:
    def __init__(self, initializer: Callable[[], T]):
        self.__initializer = initializer
        self.__data_val = None

    @property
    def obj(self) -> T:
        if self.__data_val is None:
            self.__data_val = self.__initializer()
        return self.__data_val


def first(col:Iterable):
    return next(iter(col))
