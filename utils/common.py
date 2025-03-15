from itertools import islice


def chunked(iterable, size):
    it = iter(iterable)  # Convert to iterator
    return iter(lambda: list(islice(it, size)), [])


def get_nested_value(d, *keys):
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return None
    return d
