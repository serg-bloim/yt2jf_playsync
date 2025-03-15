from itertools import islice


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
