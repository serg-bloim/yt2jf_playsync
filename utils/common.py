from itertools import islice
from typing import Callable, TypeVar, Iterable, Union


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


def first(col: Iterable):
    return next(iter(col))


def format_scaled_number(n: Union[int, float]):
    formats = {1_000_000_000: 'B', 1_000_000: 'M', 1_000: 'K'}
    for b, s in formats.items():
        if n >= b:
            return f"{n / b:.1f}{s}"
    return str(n)
