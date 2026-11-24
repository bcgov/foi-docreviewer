from datetime import datetime, timezone
import pytest
from utils.basicutils import pstformat


def test_null_datetime():
    assert pstformat(None) == ""


@pytest.mark.parametrize("month,expected", [(1, "2020-01-15T04:00:00-08:00"),
                                           (7, "2020-07-15T05:00:00-07:00")])
def test_historical_vancouver_datetime(month, expected):
    assert pstformat(datetime(2020, month, 15, 12, tzinfo=timezone.utc)) == expected
