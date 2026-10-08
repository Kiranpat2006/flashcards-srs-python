INSERT INTO decks (id, name, subject) VALUES
 (1,'Operating Systems','Computer Science'),
 (2,'Hindi Vocabulary','Languages'),
 (3,'Organic Chemistry','Chemistry')
ON CONFLICT DO NOTHING;
SELECT setval('decks_id_seq', GREATEST((SELECT MAX(id) FROM decks),1));

INSERT INTO cards (id, deck_id, front, back) VALUES
 (1,1,'What is a race condition?','Two threads touching shared state where the result depends on the order they get scheduled.'),
 (2,1,'Deadlock: name all four Coffman conditions','Mutual exclusion, hold and wait, no pre-emption, circular wait.'),
 (3,1,'Difference between a process and a thread?','Processes have separate address spaces; threads of one process share theirs.'),
 (4,1,'What does the scheduler do on a context switch?','Saves the registers and program counter of the running thread, loads another.'),
 (5,1,'What is thrashing?','The system spends more time paging than running useful work.'),
 (6,1,'Why is a semaphore not the same as a mutex?','A mutex has an owner and must be released by that owner; a semaphore is just a counter.'),
 (7,1,'What is copy-on-write in fork()?','Parent and child share pages read-only until one writes, then that page is duplicated.'),
 (8,1,'What is the difference between preemptive and cooperative scheduling?','Preemptive: the kernel takes the CPU back. Cooperative: the task must yield.'),
 (9,2,'kitaab','book'),
 (10,2,'khidki','window'),
 (11,2,'darwaaza','door'),
 (12,2,'baarish','rain'),
 (13,2,'suraj','sun'),
 (14,2,'chaabi','key'),
 (15,2,'raasta','road, way'),
 (16,3,'What is an electrophile?','An electron-poor species that accepts an electron pair.'),
 (17,3,'Markovnikov rule, in one line','The hydrogen adds to the carbon that already has more hydrogens.'),
 (18,3,'What does SN1 stand for, and what is rate-limiting?','Unimolecular nucleophilic substitution; the carbocation forms first and that step sets the rate.'),
 (19,3,'Why is benzene unusually stable?','Six delocalised pi electrons in a closed ring - aromaticity.'),
 (20,3,'What is a racemic mixture?','Equal amounts of both enantiomers, so it is optically inactive.')
ON CONFLICT DO NOTHING;
SELECT setval('cards_id_seq', GREATEST((SELECT MAX(id) FROM cards),1));

-- Progress for "demo", relative to the CURRENT study day so the app is
-- interesting the moment it boots. A mix of:
--   * cards well learned and not due for weeks
--   * cards due exactly today
--   * cards overdue by several days (these come to the front of the queue)
--   * a card with its ease on the 1.3 floor, from being failed repeatedly
--   * cards never seen at all (no progress row) - card 7, 8, 14, 15, 19, 20
INSERT INTO progress (user_name, card_id, repetitions, ease, interval_days,
                      due_on, last_reviewed) VALUES
 ('demo', 1, 4, 2.6000, 21, CURRENT_DATE + 14, now() - interval '7 days'),
 ('demo', 2, 1, 1.3000,  1, CURRENT_DATE -  5, now() - interval '6 days'),
 ('demo', 3, 3, 2.5000, 15, CURRENT_DATE +  9, now() - interval '6 days'),
 ('demo', 4, 2, 2.3600,  6, CURRENT_DATE -  2, now() - interval '8 days'),
 ('demo', 5, 0, 1.7000,  1, CURRENT_DATE,      now() - interval '1 day'),
 ('demo', 6, 5, 2.9000, 45, CURRENT_DATE + 30, now() - interval '15 days'),
 ('demo', 9, 2, 2.5000,  6, CURRENT_DATE,      now() - interval '6 days'),
 ('demo',10, 1, 2.3600,  1, CURRENT_DATE -  1, now() - interval '2 days'),
 ('demo',11, 6, 2.7000, 60, CURRENT_DATE + 44, now() - interval '16 days'),
 ('demo',12, 0, 1.3000,  1, CURRENT_DATE -  3, now() - interval '4 days'),
 ('demo',13, 3, 2.5000, 15, CURRENT_DATE +  7, now() - interval '8 days'),
 ('demo',16, 2, 2.1800,  6, CURRENT_DATE -  1, now() - interval '7 days'),
 ('demo',17, 1, 2.5000,  1, CURRENT_DATE,      now() - interval '1 day'),
 ('demo',18, 4, 2.4000, 25, CURRENT_DATE + 18, now() - interval '7 days')
ON CONFLICT DO NOTHING;

-- Two weeks of answer history, so GET /stats/demo has a shape on first run.
INSERT INTO answers (user_name, card_id, grade, study_day, answered_at)
SELECT 'demo', c.id, 3 + ((g + c.id) % 3), CURRENT_DATE - g,
       now() - make_interval(days => g)
FROM generate_series(1, 12) AS g,
     (VALUES (1),(3),(6),(9),(11),(13),(18)) AS c(id)
WHERE (g + c.id) % 3 <> 0;
