# Real user tests

## Who and how

Friends of mine who are recruiting for consulting tried the app on my laptop in Chrome, with voice, on 2026-10-24.
The app saves each finished case automatically (`data/history.json`, `output/runs/`). One complete session was
saved (Albert's).

## What they said

- **Realism:** the case felt quite realistic.
- **Feedback:** the scorecard and coaching were useful.
- **Would use again:** yes.
- **Quote:** "this is pretty good, better than scheduling time with real case interviewers." (Albert)

## Saved session

| Tester | Case | Mode | Turns | Time | Overall | Math | Cost | Coach's next step |
|---|---|---|---|---|---|---|---|---|
| Albert | Pickleball paddles (market sizing) | voice | 7 | 4.7 min | 1.2 / 5 | 0 / 2 | $0.0017 | Quantitative drill → EV chargers case |

Albert ended the case early ("okay thank you bye") before doing the math, so the low score is fair. The Grader:
"You never converted the player base into annual purchases and revenue." Run file:
`output/runs/2026-10-24T07-38-19_pickleball_98df28904805.json`.

## My own motivation (Darrel)

I'm recruiting for consulting and practice with real people all the time. The frustrating part is finding
interviewers who can give 1–2 hours of their time: the case takes about an hour and the feedback takes about another hour.

## What confused people, and what I changed

1. **The microphone picked up background conversation** (Albert's first message begins with words from people nearby,
   "kissing question say something"). Auto-send is now off by default: your words appear in the box first, so
   you can fix them, then press Enter. There's a hint under the box explaining this.
2. **The same message was sent twice.** The app now ignores an identical message sent again within 15 seconds
   (browser and server).

## Simulated test candidates (AI-scripted, NOT real users)

Kept separate from the friend feedback above. Each is a scripted set of answers written with AI assistance to play
one skill level, run through the real app on 2026-10-24 (scripts: `scripts/sample_answers/sim_*.txt`, logs:
`output/sim_runs/`).

| Simulated candidate | Case | Written to be | Turns | Overall | Math | Cost | Coach's focus → next case |
|---|---|---|---|---|---|---|---|
| Sim A | ev_chargers | strong | 8 | 4.8 | 3/3 | $0.0019 | clarifying → harbor_er |
| Sim C | freshcart_kits | rambling | 8 | 2.7 | 2/3 | $0.0019 | judgment → brightsmile |
| Sim B | brightsmile | average | 8 | 2.2 | 1/3 | $0.0020 | quantitative → voltade_gritbar |
| Sim D | nighthawks | beginner | 7 | 1.3 | 0/3 | $0.0015 | quantitative → ev_chargers |

## Not done yet (honest gaps)

- No before-and-after score (a second case after the coach's drill).
- Only one complete session saved; no numeric 1–5 ratings recorded.
- No feedback from a club or organization yet. Next: a pilot with the SOM consulting club.
