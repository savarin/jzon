"""
Test data generators for JSON parsing benchmarks.

Creates various JSON structures optimized for performance testing:
- Different sizes (small/medium/large)
- Different complexity levels (simple/nested/mixed)
- String-heavy content with escape sequences
"""

import json
import random
import string
from typing import Any

# Constants for random data generation
_INT_TYPE = 1
_FLOAT_TYPE = 2
_STRING_TYPE = 3
_BOOL_TYPE = 4
_NULL_TYPE = 5
_ESCAPE_PROBABILITY = 0.3


def generate_test_data(data_type: str) -> str:
    """Generates JSON test data based on specified type."""
    generators = {
        "small_object": _generate_small_object,
        "large_object": _generate_large_object,
        "mixed_array": _generate_mixed_array,
        "nested_structure": _generate_nested_structure,
        "string_heavy": _generate_string_heavy,
    }

    if data_type not in generators:
        raise ValueError(f"Unknown data type: {data_type}")

    return generators[data_type]()


def _generate_small_object() -> str:
    """Generates a small JSON object (< 1KB) with basic key-value pairs."""
    data = {
        "id": 12345,
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "active": True,
        "balance": 1234.56,
        "metadata": {"created": "2024-01-15T10:30:00Z", "source": "api"},
    }
    return json.dumps(data)


def _generate_large_object() -> str:
    """Generates a large JSON object (> 10KB) with many fields."""
    # Generate a user profile with extensive data
    data = {
        "user_id": random.randint(1000000, 9999999),
        "profile": {
            "personal": {
                "first_name": _random_string(10),
                "last_name": _random_string(12),
                "email": f"{_random_string(8)}@{_random_string(6)}.com",
                "phone": f"+1-{random.randint(100, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                "address": {
                    "street": f"{random.randint(1, 9999)} {_random_string(8)} St",
                    "city": _random_string(12),
                    "state": _random_string(2).upper(),
                    "zip": f"{random.randint(10000, 99999)}",
                    "country": "US",
                },
            },
            "preferences": {
                "language": random.choice(["en", "es", "fr", "de", "zh"]),
                "timezone": random.choice(
                    [
                        "America/New_York",
                        "America/Los_Angeles",
                        "Europe/London",
                        "Asia/Tokyo",
                        "Australia/Sydney",
                    ]
                ),
                "notifications": {
                    "email": random.choice([True, False]),
                    "sms": random.choice([True, False]),
                    "push": random.choice([True, False]),
                },
            },
        },
        # Generate transaction history
        "transactions": [
            {
                "id": f"txn_{i:06d}",
                "amount": round(random.uniform(1.0, 1000.0), 2),
                "currency": random.choice(["USD", "EUR", "GBP", "JPY"]),
                "timestamp": f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00Z",
                "description": f"Payment for {_random_string(20)}",
                "status": random.choice(["completed", "pending", "failed"]),
            }
            for i in range(50)  # 50 transactions
        ],
        # Generate activity log
        "activity_log": [
            {
                "timestamp": f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00Z",
                "action": random.choice(
                    ["login", "logout", "purchase", "view", "update"]
                ),
                "ip_address": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
                "user_agent": f"Mozilla/5.0 ({_random_string(20)})",
            }
            for i in range(30)  # 30 log entries
        ],
    }
    return json.dumps(data)


def _generate_mixed_array() -> str:
    """Generates a large array with mixed data types."""
    array: list[Any] = []

    # Add various data types
    for i in range(200):
        choice = random.randint(1, 6)
        if choice == _INT_TYPE:
            array.append(random.randint(-1000, 1000))
        elif choice == _FLOAT_TYPE:
            array.append(round(random.uniform(-100.0, 100.0), 3))
        elif choice == _STRING_TYPE:
            array.append(_random_string(random.randint(5, 30)))
        elif choice == _BOOL_TYPE:
            array.append(random.choice([True, False]))
        elif choice == _NULL_TYPE:
            array.append(None)
        else:
            # Nested object
            array.append(
                {
                    "index": i,
                    "value": _random_string(10),
                    "score": round(random.uniform(0, 100), 2),
                }
            )

    return json.dumps(array)


def _generate_nested_structure() -> str:
    """Generates deeply nested JSON structure."""

    def create_nested_dict(depth: int) -> dict[str, Any]:
        if depth <= 0:
            return {"value": _random_string(10)}

        return {
            "level": depth,
            "data": _random_string(15),
            "items": [create_nested_dict(depth - 1) for _ in range(3)],
            "nested": create_nested_dict(depth - 1),
        }

    data = create_nested_dict(8)  # 8 levels deep
    return json.dumps(data)


def _generate_string_heavy() -> str:
    """Generates JSON with many string escape sequences."""

    def create_escaped_string() -> str:
        """Creates a string with various escape sequences."""
        chars = []
        for _ in range(50):
            if (
                random.random() < _ESCAPE_PROBABILITY
            ):  # 30% chance of escape sequence
                escape_char = random.choice(
                    ['\\"', "\\\\", "\\/", "\\b", "\\f", "\\n", "\\r", "\\t"]
                )
                chars.append(escape_char)
            else:
                chars.append(
                    random.choice(string.ascii_letters + string.digits + " ")
                )
        return "".join(chars)

    data = {
        "strings": [create_escaped_string() for _ in range(100)],
        "unicode": [
            f"Unicode: \\u{random.randint(0x0020, 0x007E):04x}"
            for _ in range(50)
        ],
        "mixed_content": {
            f"key_{i}": {
                "description": create_escaped_string(),
                "content": 'Content with \\n newlines \\t tabs and \\" quotes',
                "path": f"C:\\\\Users\\\\{_random_string(8)}\\\\Documents\\\\file_{i}.txt",
            }
            for i in range(20)
        },
    }
    return json.dumps(data)


def _random_string(length: int) -> str:
    """Generates a random string of specified length."""
    return "".join(random.choices(string.ascii_letters, k=length))
