
"""Unit tests for the spaced-repetition scheduling module."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.schedule import (
    CardError,
    MIN_EASE,
    apply_answer,
    due_cards,
    due_date,
    is_pass,
    is_repeat_in_same_day,
    next_ease,
    next_interval,
    queue_for,
    review,
    study_day,
    validate_grade,
)

IST = timezone(timedelta(hours=5, minutes=30))


# Grade validation and pass/fail rules

@pytest.mark.parametrize("grade", range(6))
def test_valid_grades(grade):
    assert validate_grade(grade) == grade


@pytest.mark.parametrize("grade", [-1, 6, "invalid", None])
def test_invalid_grades_raise_error(grade):
    with pytest.raises(CardError):
        validate_grade(grade)


@pytest.mark.parametrize("grade", [3, 4, 5])
def test_grades_three_and_above_are_passes(grade):
    assert is_pass(grade) is True


@pytest.mark.parametrize("grade", [0, 1, 2])
def test_grades_below_three_are_failures(grade):
    assert is_pass(grade) is False


# SM-2 ease calculation

@pytest.mark.parametrize("grade", range(6))
def test_next_ease_never_below_minimum(grade):
    assert next_ease(2.5, grade) >= MIN_EASE


def test_grade_five_increases_ease():
    assert next_ease(2.5, 5) == 2.6


def test_grade_four_keeps_ease_unchanged():
    assert next_ease(2.5, 4) == 2.5


def test_grade_three_decreases_ease():
    assert next_ease(2.5, 3) == 2.36


def test_repeated_failures_respect_ease_floor():
    ease = 2.5

    for _ in range(10):
        ease = next_ease(ease, 0)

    assert ease == MIN_EASE


def test_next_ease_has_no_artificial_ceiling():
    assert next_ease(10.0, 5) == 10.1


# Interval and review behavior

def test_first_successful_review_has_one_day_interval():
    result = review({}, 4)

    assert result["repetitions"] == 1
    assert result["interval"] == 1
    assert result["passed"] is True


def test_second_successful_review_has_six_day_interval():
    card = {"repetitions": 1, "ease": 2.5, "interval": 1}

    result = review(card, 4)

    assert result["repetitions"] == 2
    assert result["interval"] == 6


def test_third_successful_review_uses_ease_multiplier():
    card = {"repetitions": 2, "ease": 2.5, "interval": 6}

    result = review(card, 5)

    assert result["repetitions"] == 3
    assert result["interval"] == round(6 * result["ease"])


def test_failed_review_resets_repetitions_and_interval():
    card = {"repetitions": 5, "ease": 2.5, "interval": 30}

    result = review(card, 2)

    assert result["repetitions"] == 0
    assert result["interval"] == 1
    assert result["lapsed"] is True
    assert result["ease"] < 2.5


def test_review_does_not_mutate_original_card():
    card = {"repetitions": 2, "ease": 2.5, "interval": 6}
    original = card.copy()

    review(card, 5)

    assert card == original


@pytest.mark.parametrize(
    ("interval", "repetitions", "ease", "passed", "expected"),
    [
        (0, 0, 2.5, True, 1),
        (1, 1, 2.5, True, 1),
        (6, 2, 2.5, True, 6),
        (30, 5, 2.5, False, 1),
    ],
)
def test_next_interval(interval, repetitions, ease, passed, expected):
    assert next_interval(interval, repetitions, ease, passed) == expected


# Study-day boundary: 04:00 IST

def test_late_night_and_early_morning_share_study_day():
    late_night = datetime(2026, 10, 14, 23, 58, tzinfo=IST)
    early_morning = datetime(2026, 10, 15, 0, 2, tzinfo=IST)

    assert study_day(late_night) == study_day(early_morning)
    assert study_day(early_morning) == date(2026, 10, 14)


def test_0359_belongs_to_previous_study_day():
    moment = datetime(2026, 10, 15, 3, 59, tzinfo=IST)

    assert study_day(moment) == date(2026, 10, 14)


def test_0400_starts_new_study_day():
    moment = datetime(2026, 10, 15, 4, 0, tzinfo=IST)

    assert study_day(moment) == date(2026, 10, 15)


def test_study_day_boundary_is_exact():
    before = datetime(2026, 10, 15, 3, 59, 59, tzinfo=IST)
    boundary = datetime(2026, 10, 15, 4, 0, tzinfo=IST)

    assert study_day(before) == date(2026, 10, 14)
    assert study_day(boundary) == date(2026, 10, 15)


def test_study_day_accepts_utc_aware_datetime():
    utc_moment = datetime(2026, 10, 14, 22, 30, tzinfo=timezone.utc)

    assert study_day(utc_moment) == date(2026, 10, 15)


def test_study_day_rejects_non_datetime():
    with pytest.raises(CardError):
        study_day("2026-10-15")


# Same-session answer handling

def test_repeat_answer_on_same_study_day():
    last = datetime(2026, 10, 14, 23, 58, tzinfo=IST)
    now = datetime(2026, 10, 15, 0, 2, tzinfo=IST)

    assert is_repeat_in_same_day(last, now) is True


def test_answer_on_next_study_day_is_not_repeat():
    last = datetime(2026, 10, 14, 3, 59, tzinfo=IST)
    now = datetime(2026, 10, 14, 4, 0, tzinfo=IST)

    assert is_repeat_in_same_day(last, now) is False


def test_first_answer_advances_schedule():
    now = datetime(2026, 10, 15, 10, 0, tzinfo=IST)

    result = apply_answer({}, 4, now)

    assert result["same_session"] is False
    assert result["repetitions"] == 1
    assert result["interval"] == 1
    assert result["study_day"] == date(2026, 10, 15)


def test_repeat_answer_does_not_advance_interval():
    card = {"repetitions": 2, "ease": 2.5, "interval": 6}
    last = datetime(2026, 10, 14, 23, 58, tzinfo=IST)
    now = datetime(2026, 10, 15, 0, 2, tzinfo=IST)

    result = apply_answer(card, 5, now, last_reviewed=last)

    assert result["same_session"] is True
    assert result["interval"] == 6
    assert result["repetitions"] == 2
    assert result["ease"] > 2.5
    assert card["interval"] == 6


# Due dates and queue ordering

def test_due_date_uses_study_day():
    moment = datetime(2026, 10, 15, 0, 2, tzinfo=IST)

    assert due_date(moment, 1) == date(2026, 10, 15)


def test_due_date_rejects_negative_interval():
    with pytest.raises(CardError):
        due_date(date(2026, 10, 15), -1)


def test_due_cards_prioritize_overdue_then_low_ease_then_id():
    today = date(2026, 10, 15)
    cards = [
        {"id": 3, "due_on": date(2026, 10, 14), "ease": 2.5},
        {"id": 2, "due_on": date(2026, 10, 14), "ease": 1.8},
        {"id": 1, "due_on": date(2026, 10, 13), "ease": 2.5},
        {"id": 4, "due_on": date(2026, 10, 16), "ease": 1.3},
    ]

    result = due_cards(cards, today)

    assert [card["id"] for card in result] == [1, 2, 3]


def test_queue_for_returns_ordered_card_ids():
    today = date(2026, 10, 15)
    cards = [
        {"id": 2, "due_on": today, "ease": 2.5},
        {"id": 1, "due_on": today, "ease": 1.8},
    ]

    assert queue_for(cards, today) == [1, 2]


def test_due_cards_respects_limit():
    today = date(2026, 10, 15)
    cards = [
        {"id": 1, "due_on": today, "ease": 2.5},
        {"id": 2, "due_on": today, "ease": 2.0},
        {"id": 3, "due_on": today, "ease": 1.8},
    ]

    assert len(due_cards(cards, today, limit=2)) == 2
