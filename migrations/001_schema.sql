CREATE TABLE IF NOT EXISTS decks (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '');

CREATE TABLE IF NOT EXISTS cards (
    id SERIAL PRIMARY KEY,
    deck_id INT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS cards_deck ON cards (deck_id);

CREATE TABLE IF NOT EXISTS progress (
    user_name TEXT NOT NULL,
    card_id INT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    repetitions INT NOT NULL DEFAULT 0 CHECK (repetitions >= 0),
    ease NUMERIC(5,4) NOT NULL DEFAULT 2.5 CHECK (ease >= 1.3),
    interval_days INT NOT NULL DEFAULT 0 CHECK (interval_days >= 0),
    due_on DATE,
    last_reviewed TIMESTAMPTZ,
    PRIMARY KEY (user_name, card_id));
CREATE INDEX IF NOT EXISTS progress_due ON progress (user_name, due_on);

CREATE TABLE IF NOT EXISTS answers (
    id SERIAL PRIMARY KEY,
    user_name TEXT NOT NULL,
    card_id INT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    grade INT NOT NULL CHECK (grade BETWEEN 0 AND 5),
    study_day DATE NOT NULL,
    answered_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS answers_user_day ON answers (user_name, study_day DESC);
