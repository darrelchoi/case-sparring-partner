# Tokenomics: measured from real runs

5 full cases (scripted candidates of different quality), model `gpt-6-luna`. Prices per 1M tokens: input $0.1, cached input $0.01, output $0.5. Raw rows are in `output/usage_log.jsonl`.

## One case, by agent (average of 5)

| Agent | Input tokens | of which cached | Output tokens | Cost |
|---|---|---|---|---|
| Interviewer (all turns) | 28,063 | 25,790 | 697 | $0.00088 |
| Grader | 2,838 | 0 | 712 | $0.00071 |
| Coach | 1,243 | 0 | 179 | $0.00024 |
| **Whole case** | 32,144 | 25,790 | 1,588 | $0.00182 |

## Each run

| Case | Candidate | Turns | Overall score | Tokens in / cached / out | Cost |
|---|---|---|---|---|---|
| brew_bloom | strong | 9 | 3.8 | 35,112 / 29,318 / 1,565 | $0.0018 |
| skylink | medium | 7 | 2.7 | 31,540 / 26,239 / 1,594 | $0.0017 |
| pickleball | strong | 8 | 4.2 | 33,266 / 26,246 / 1,455 | $0.0018 |
| ledgerloop_ai | weak | 7 | 1.5 | 22,087 / 15,234 / 1,583 | $0.0018 |
| harbor_er | strong | 8 | 4.7 | 38,716 / 31,915 / 1,741 | $0.0020 |

## Cost per user and at scale

- **One case:** $0.0018. Without prompt caching the same tokens would cost $0.0040, so caching saves 55% (80% of input tokens were served from cache).
- **Per user per month:** 13 cases (3 a week in recruiting season) → **$0.024**.
- **100 users** (a consulting club): $2.37 a month.
- **10,000 users** (several MBA programs): $237 a month.
- **Generating a new case** costs about $0.002 (see `generator_report.md`), and library cases cost $0.
- **Compared with a human coach:** one 30-minute case with a paid coach is about $75. The app costs $0.0018, about 41,136 times cheaper. A classmate costs no money but 30–60 minutes of their time.

## What keeps cost down

1. **Prompt caching.** Static instructions and the case brief come first, the growing conversation comes last, and there's one cache key per case, so later turns re-read the prefix at 10% of the price.
2. **The opening prompt is read from the case file**, with no model call.
3. **Low reasoning effort** for the Interviewer, Grader and Coach, and short replies (about 90 words).
4. **The Interviewer never holds the whole case**, only topic names, so its prompt stays small.
5. **Hard caps:** 5 model calls and 40K tokens per turn, $0.05 per case, $2 per day (see `safety_results.md`).
6. **Compressed transcript for the Grader** (the experiment below).

## Experiment: does a compressed transcript hurt grading?

| Case | Grader input, full | Compressed | Saved | Overall A (full) | B (full again) | C (compressed) | Avg score change A→B (randomness) | A→C (compression) |
|---|---|---|---|---|---|---|---|---|
| brew_bloom | 3,315 | 3,215 | 3% | 3.8 | 3.8 | 4.0 | 0.00 | 0.17 |
| skylink | 2,865 | 2,787 | 3% | 2.7 | 2.8 | 2.5 | 0.17 | 0.17 |
| pickleball | 2,604 | 2,588 | 1% | 3.7 | 4.0 | 4.2 | 0.67 | 0.83 |
| ledgerloop_ai | 2,633 | 2,599 | 1% | 1.3 | 1.5 | 1.3 | 0.17 | 0.00 |
| harbor_er | 3,060 | 3,002 | 2% | 4.3 | 4.5 | 4.7 | 0.17 | 0.33 |

**Result:** compression saved 2% of grader input tokens. The average per-dimension score change was 0.30 points from compression, against 0.23 points from grading the same transcript twice. Compression changed scores about as much as simply grading twice, so it didn't measurably hurt quality. Honest caveat: grader input is mostly the cached rubric and answer key, so the dollar saving per case is small.
