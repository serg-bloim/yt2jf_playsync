from itertools import islice


def chunked(iterable, size):
    it = iter(iterable)  # Convert to iterator
    return iter(lambda: list(islice(it, size)), [])
