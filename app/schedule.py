"""SM-2 spaced repetition. No database, no HTTP, no clock of its own.

This is the algorithm behind every flashcard app worth using. You answer a
card and grade how well you remembered it from 0 to 5. The algorithm decides
when you will see it next. Easy cards drift further and further out; a card
you fumble comes back tomorrow.

The three numbers a card carries
--------------------------------
``repetitions`` how many times in a row you have passed it
``ease``        a multiplier, how generous the algorithm is with this card
``interval``    days until it is due again

The rules, as implemented here
------------------------------
* A grade of **3 or more is a pass**, below 3 is a **lapse**.
* On a pass: interval goes 1 day, then 6 days, then ``interval * ease``.
* On a lapse: repetitions reset to 0 and the interval resets to 1 day. The
  card is back tomorrow and has to earn its way out again.
* Ease moves by the standard SM-2 adjustment on **every** answer, pass or
  lapse, and is clamped at a floor of ``MIN_EASE`` (1.3). Without that floor a
  card you keep failing drives its own ease to zero and is then due forever.
  **This module applies the ease penalty on a lapse as well as adjusting it on
  a pass.** Implementations differ on that point - some reset ease, some leave
  it alone. Ours penalises. It is written down here so a test can assert it.

THE HARD PART: a card answered at 23:58 and again at 00:02 is two sessions by
the clock and one by intent. Nobody thinks of a four-minute gap as "tomorrow".
``study_day`` solves it by moving the day boundary to ``DAY_START_HOUR`` (4am
local) instead of midnight, so both answers land on the same study day, and
``is_repeat_in_same_day`` lets the caller refuse to advance an interval twice
for what was really one sitting.

What to test
------------
This module is close to perfect for unit testing: pure arithmetic, sharp
boundaries, and a specification you can look up.

* ``next_ease`` - grade 5 raises ease, grade 4 leaves it almost alone, grade 3
  lowers it slightly, grade 0 lowers it a lot. The floor at 1.3 must hold no
  matter how many times you fail. There is no ceiling - check you did not
  invent one.
* ``is_pass`` - the boundary. 3 passes, 2 does not.
* ``grade validation`` - 6 and -1 must raise, not silently clamp.
* ``review`` on a brand new card: first pass gives interval 1, second gives 6,
  third gives ``6 * ease`` rounded.
* ``review`` on a lapse: repetitions 0, interval 1, ease reduced and floored.
* ``review`` must never mutate the card it was given. Pass a dict, assert the
  original is unchanged.
* ``due_date`` - interval added in days to the study day, not to the raw
  timestamp.
* ``study_day`` - **the hard part**. 23:58 and 00:02 on consecutive calendar
  dates must return the SAME study day. 03:59 belongs to the previous day,
  04:00 starts the new one. Test a timezone offset other than UTC.
* ``is_repeat_in_same_day`` - the same card twice in one sitting.
* ``apply_answer`` - the wrapper that ties it together, with and without a
  previous answer on the same study day.
* ``due_cards`` / ``queue_for`` - ordering is by how overdue a card is, then
  by LOWEST EASE (the cards you find hard come first, while you are fresh),
  then by id. Deterministic, because the queue is built once and popped from:
  two cards equally overdue must always come back in the same order.
"""
from datetime import date, datetime, timedelta, timezone

MIN_GRADE, MAX_GRADE = 0, 5
PASS_GRADE = 3            # 3 or more is a pass
MIN_EASE = 1.3            # the floor that stops a hard card collapsing
DEFAULT_EASE = 2.5        # what a brand new card starts with
FIRST_INTERVAL = 1        # days, after the first successful recall
SECOND_INTERVAL = 6       # days, after the second

# The day boundary. 4am, not midnight - see THE HARD PART above.
DAY_START_HOUR = 4
# India Standard Time, as a fixed offset. A fixed offset rather than a named
# zone keeps this module dependency-free and testable on any machine.
DEFAULT_TZ = timezone(timedelta(hours=5, minutes=30))


class CardError(ValueError):
    pass


# --------------------------------------------------------------------------
# Study days - the hard part
# --------------------------------------------------------------------------

def study_day(moment, tz=DEFAULT_TZ, day_start_hour=DAY_START_HOUR):
    """Which study day does this instant belong to?

    A card answered at 23:58 and again at 00:02 is two calendar dates and one
    sitting. Revising past midnight is the normal case, not the edge case, and
    an algorithm that calls 00:02 "tomorrow" will happily show you the same
    card twice in four minutes and then claim you remembered it after a day.

    So the day starts at 4am. Anything before that belongs to the day before,
    which is exactly how a student thinks about the night they are having.
    """
    if not isinstance(moment, datetime):
        raise CardError("study_day needs a datetime")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(tz)
    if local.hour < day_start_hour:
        local = local - timedelta(days=1)
    return local.date()


def is_repeat_in_same_day(last_reviewed, now, tz=DEFAULT_TZ,
                          day_start_hour=DAY_START_HOUR):
    """Were these two answers part of one sitting?

    If so the caller should record the answer but NOT advance the interval
    again - otherwise answering a card twice in one evening doubles its
    interval, and the schedule quietly stops meaning anything.
    """
    if last_reviewed is None:
        return False
    return (study_day(last_reviewed, tz, day_start_hour)
            == study_day(now, tz, day_start_hour))


def due_date(from_day, interval_days):
    """The study day a card with this interval becomes due again."""
    if interval_days < 0:
        raise CardError("an interval cannot be negative")
    base = from_day if isinstance(from_day, date) and not isinstance(from_day, datetime) \
        else study_day(from_day)
    return base + timedelta(days=int(interval_days))


# --------------------------------------------------------------------------
# SM-2 itself
# --------------------------------------------------------------------------

def validate_grade(grade):
    try:
        g = int(grade)
    except (TypeError, ValueError):
        raise CardError("grade must be a whole number from 0 to 5")
    if g < MIN_GRADE or g > MAX_GRADE:
        raise CardError(f"grade must be between {MIN_GRADE} and {MAX_GRADE}")
    return g


def is_pass(grade):
    """3 or more is a pass. 2 is 'I nearly had it', which is still a lapse."""
    return validate_grade(grade) >= PASS_GRADE


def next_ease(ease, grade):
    """The standard SM-2 ease adjustment, with a floor and no ceiling.

        ease' = ease + (0.1 - (5 - g) * (0.08 + (5 - g) * 0.02))

    Grade 5 adds 0.10, grade 4 adds nothing, grade 3 subtracts 0.14, grade 0
    subtracts 0.80. The floor at 1.3 is not decoration: without it a card you
    keep failing drives its ease negative, its interval to zero, and it is then
    due for the rest of your life.
    """
    g = validate_grade(grade)
    delta = 0.1 - (5 - g) * (0.08 + (5 - g) * 0.02)
    return round(max(MIN_EASE, float(ease) + delta), 4)


def next_interval(interval, repetitions, ease, passed):
    """Days until the card comes back.

    A lapse sends it to tomorrow regardless of how well it was doing - that is
    the point of the algorithm, and softening it is the most common way people
    break SM-2 while thinking they are improving it.
    """
    if not passed:
        return FIRST_INTERVAL
    if repetitions <= 1:
        return FIRST_INTERVAL
    if repetitions == 2:
        return SECOND_INTERVAL
    return max(1, round(float(interval) * float(ease)))


def review(card, grade):
    """Answer one card. Returns a NEW card dict - the input is never mutated.

    `card` is {"repetitions": 0, "ease": 2.5, "interval": 0}; missing keys take
    their default, so a brand new card can be an empty dict.
    """
    g = validate_grade(grade)
    reps = int(card.get("repetitions", 0))
    ease = float(card.get("ease", DEFAULT_EASE))
    interval = float(card.get("interval", 0))

    passed = g >= PASS_GRADE
    reps = reps + 1 if passed else 0
    new_ease = next_ease(ease, g)
    new_interval = next_interval(interval, reps, new_ease, passed)
    return {"repetitions": reps, "ease": new_ease, "interval": new_interval,
            "grade": g, "passed": passed,
            "lapsed": not passed,
            "ease_floored": new_ease <= MIN_EASE}


def apply_answer(card, grade, now, last_reviewed=None, tz=DEFAULT_TZ):
    """Answer a card, honouring the one-sitting rule.

    If this card was already answered today - by the 4am-to-4am definition of
    today - the answer is recorded but the schedule is NOT advanced a second
    time. Only the ease moves, because how well you recalled it is real
    information even on a repeat; the interval is not, because you have not
    actually slept on it.
    """
    today = study_day(now, tz)
    if is_repeat_in_same_day(last_reviewed, now, tz):
        g = validate_grade(grade)
        updated = {
            "repetitions": int(card.get("repetitions", 0)),
            "ease": next_ease(float(card.get("ease", DEFAULT_EASE)), g),
            "interval": int(card.get("interval", 0)),
            "grade": g, "passed": g >= PASS_GRADE, "lapsed": g < PASS_GRADE,
        }
        updated["ease_floored"] = updated["ease"] <= MIN_EASE
        return {**updated, "study_day": today,
                "due_on": due_date(today, updated["interval"]),
                "same_session": True,
                "note": "already answered today - ease updated, interval left alone"}
    updated = review(card, grade)
    return {**updated, "study_day": today,
            "due_on": due_date(today, updated["interval"]),
            "same_session": False, "note": ""}


# --------------------------------------------------------------------------
# Building the day's queue
# --------------------------------------------------------------------------

def is_due(card, today):
    """A card with no due date has never been seen, so it is due now."""
    due = card.get("due_on")
    return due is None or due <= today


def overdue_days(card, today):
    due = card.get("due_on")
    return 0 if due is None else max(0, (today - due).days)


def due_cards(cards, today, limit=None):
    """The cards to revise today, hardest-overdue first.

    Order is (most overdue, then lowest ease - the cards you find hard come
    first while you are fresh, then id). Entirely deterministic: the queue is
    built once per study day and popped from, so it must not reshuffle itself
    between page loads.
    """
    ready = [c for c in cards if is_due(c, today)]
    ready.sort(key=lambda c: (-overdue_days(c, today),
                              float(c.get("ease", DEFAULT_EASE)),
                              int(c["id"])))
    return ready[:limit] if limit else ready


def queue_for(cards, today, limit=None):
    """Just the ids, which is what goes into the cache as the day's queue."""
    return [int(c["id"]) for c in due_cards(cards, today, limit)]


def deck_summary(cards, today):
    """How a deck is doing. `new` has never been answered."""
    new = sum(1 for c in cards if not c.get("due_on"))
    due = sum(1 for c in cards if is_due(c, today))
    return {"cards": len(cards), "new": new, "due_today": due,
            "learning": sum(1 for c in cards if 0 < int(c.get("repetitions", 0)) < 3),
            "mature": sum(1 for c in cards if float(c.get("interval", 0)) >= 21),
            "average_ease": round(
                sum(float(c.get("ease", DEFAULT_EASE)) for c in cards) / len(cards), 3)
            if cards else 0.0}
