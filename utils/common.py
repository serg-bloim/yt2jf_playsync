from collections import defaultdict
from functools import cache
from itertools import islice
from pathlib import Path
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
V = ('V')


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


def group_by(seq: Iterable[T], key: Callable[[T], V]) -> dict[V, list[T]]:
    grps = defaultdict(list)
    for v in seq:
        k = key(v)
        grps[k].append(v)
    return dict(grps)

@cache
def root_dir():
    d = Path.cwd()
    while not d.joinpath("root.txt").exists():
        d = d.parent
    return d
