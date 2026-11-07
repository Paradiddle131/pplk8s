# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A product manager, and other non-technical people beside them, who must decide where a team spends budget, time and people on an AI that answers business questions from the company's data.
They open the page for a few minutes, between meetings, and want to see their options and how each one behaves, without learning how anything was measured.

## Product Purpose

The Approaches page shows, for each way of letting an AI answer business questions, how often it gives the right number, how often it says it cannot answer, and how often it gives a wrong number as if it were right.
It compares; it never recommends, ranks a winner or favours an option.
Success: a reader can say, in their own words, what each option gets right and what it risks, after one look.

## Positioning

The numbers are measured, not claimed: every approach answered the same business questions many times and every answer was checked against the warehouse.
The page is a pitch-level companion to a separate technical report; it shares no style or vocabulary with that report.

## Operating Context

- Built by `build.py` from the evaluation's `results.json` and republished to one fixed link after every test pass, so its numbers change over time without anyone editing the page.
- Read on a laptop, sometimes on a phone; shared as a link.

## Capabilities and Constraints

- Shows only one thing: the approaches, ordered from the most native (Google's managed data agent) to the most custom (an agent the team builds), each drawn as 100 answers.
- A switch between the two question sets (everyday questions and questions hard to interpret) changes every number at once.
- Every number column sorts; the approach column restores the native-to-custom order.
- No recommendation, verdict, budget advice, process metadata (dates of runs, issue numbers, file names, versions) or explanatory paragraphs.
- No text in a muted or greyed colour anywhere: every word and number is read at full contrast.
- Approaches are named in plain words and marked with icons instead of sub-text; official product logos where they exist (BigQuery, Agent Development Kit, Model Context Protocol, Lightdash); MetricFlow has no official mark, and none is borrowed for it.
- No model or model-provider logos.

## Evidence on Hand

- `../results.json`: every scored run.
- `logos/`: the four official marks, with their sources in `logos/SOURCES.md`.
- No cost-per-question, staffing or effort figures exist; the page must not show or imply any.

## Product Principles

- Show, don't advise: the reader draws the conclusion.
- One look is enough: anything that needs a paragraph to explain does not belong on the page.
- Risk is as visible as accuracy: a confidently wrong answer is never hidden inside a percentage.
- Plain words over terms of art; a term that needs a definition gets it on hover, not in the layout.
