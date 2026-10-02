from time import perf_counter


def elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 2)