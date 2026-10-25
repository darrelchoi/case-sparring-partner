# What already exists (from web research)

Collected from a web search on 2026-10-22. Sources are vendor sites, app-store listings and third-party reviews
(some written by competitors). Darrel chose to rely on these published reviews rather than hands-on testing,
and the report says so.

| Product | What it does | What it doesn't do (as far as we can tell) | Source |
|---|---|---|---|
| **ChatGPT / Claude (plain)** | Will play interviewer if asked; free or cheap | The case is improvised, so nothing keeps data hidden or numbers consistent; grades can't be checked; no history | General knowledge (not tested hands-on) |
| **PrepLounge** | Peer case-partner marketplace + case library; free tier with ~10 peer meetings, paid Premium (~$49–79/yr reported), coaching from ~€199 | Needs a human partner online; feedback quality depends on the partner | [pricing](https://www.preplounge.com/en/pricing), [review](https://www.roadtooffer.com/blog/preplounge-review) |
| **AlumnAI** | Mobile app; real-time voice AI interviewer; feedback on structure, communication, insight | Unknown how scores are checked; closed case content | [App Store](https://apps.apple.com/us/app/id6474557904) |
| **CaseStudyPrep.AI / MyConsultingCoach** | Voice AI case simulator modeled on MBB interviews | Subscription; scoring method not public | [MyConsultingCoach](https://www.myconsultingcoach.com/case-interview-ai) |
| **CaseStar** | Voice AI case interviewer (positions itself vs PrepLounge) | Subscription; scoring method not public | [comparison](https://www.casestar.io/compare/casestar-vs-preplounge) |
| **Road to Offer** | Voice interview mode + AI scorecards | Subscription; scoring method not public | [tools hub](https://www.roadtooffer.com/blog/hub/tools) |
| **CasetTutor, MockInterview247** | AI interviewer, interviewer-led and candidate-led formats | Subscription | [CasetTutor](https://www.voiceaispace.com/tool/casetutor), [MockInterview247](https://www.producthunt.com/products/mockinterview247-com) |

## So what is actually new here? (honest version)

Voice AI case interviewers already exist, so "talk to an AI interviewer" is not new on its own. What this
project does differently:

1. **Grades you can trust and check.** Math is judged by code against an answer key, every score must quote
   your own words (code verifies the quote), and the scorecard shows exactly what Python changed.
   Commercial tools don't publish how their scores are made.
2. **The interviewer can't leak or invent data.** It never holds the case data. Facts come only through a
   tool when you ask, and a leak filter blocks unrevealed numbers. A general chatbot improvises the case as it goes.
3. **Generated cases are math-verified** before anyone plays them (see `generator_report.md`).
4. **Open and nearly free for a school.** It's open source, the rubric and cases are visible, and it costs about
   2.4¢ per student per month, so a consulting club could run it for its whole membership for a few dollars,
   compared with per-student subscriptions.
5. **Built-in spending and abuse limits** (per turn, case, day), so it's safe to hand out on a shared key.

