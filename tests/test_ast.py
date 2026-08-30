import pytest
from autopoiesis.core.ast import get_normalized_ast_hash


def test_ast_hash_normalization():
    code1 = """
def calculate_sma(data: list, period: int = 20) -> float:
    \"\"\"Calculates simple moving average.\"\"\"
    # Calculate sum
    total_sum = sum(data[:period])
    return total_sum / period
"""

    code2 = """
def compute_average(values: list, n: int = 20) -> float:
    \"\"\"Different docstring.\"\"\"
    # Different comment
    s = sum(values[:n])
    return s / n
"""

    hash1 = get_normalized_ast_hash(code1)
    hash2 = get_normalized_ast_hash(code2)

    assert hash1 == hash2


def test_ast_hash_distinct_code():
    code1 = """
def foo(x):
    return x + 1
"""
    code2 = """
def foo(x):
    return x * 2
"""
    assert get_normalized_ast_hash(code1) != get_normalized_ast_hash(code2)
