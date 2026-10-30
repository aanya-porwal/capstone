import pandas as pd
import pytest

from engine.data_quality import audit_price_frame, point_in_time_filter


def test_price_audit_flags_duplicates_invalid_values_and_bad_dates():
    frame = pd.DataFrame({
        "Date": ["2024-01-02", "2024-01-01", "2024-01-01", "bad"],
        "close": [101, 100, 0, 99],
    })
    result = audit_price_frame(frame)
    assert result["rows"] == 4
    assert result["invalid_dates"] == 1
    assert result["non_positive_values"] == 1
    assert result["duplicate_date_rows"] == 2
    assert not result["passes_basic_checks"]


def test_price_audit_passes_clean_ordered_data():
    frame = pd.DataFrame({
        "Date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "close": [100, 101],
    })
    result = audit_price_frame(frame)
    assert result["passes_basic_checks"]
    assert result["start_date"] == "2024-01-01"
    assert result["end_date"] == "2024-01-02"


def test_price_audit_checks_availability_timestamp():
    frame = pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02"],
        "close": [100, 101],
        "available_at": ["2024-01-01", "2024-01-01"],
    })
    result = audit_price_frame(frame, availability_col="available_at")
    assert result["availability_issues"] == 1
    assert not result["passes_basic_checks"]


def test_point_in_time_filter_excludes_future_and_unknown_publications():
    frame = pd.DataFrame({
        "event": ["known", "future", "unknown"],
        "available_at": ["2024-01-01", "2024-02-01", None],
    })
    result = point_in_time_filter(frame, "2024-01-15")
    assert result["event"].tolist() == ["known"]


def test_point_in_time_filter_requires_availability_column():
    with pytest.raises(ValueError, match="availability column"):
        point_in_time_filter(pd.DataFrame({"x": [1]}), "2024-01-01")
