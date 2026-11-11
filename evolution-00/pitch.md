# Evolution 0 — System Pitch

## The Fifth Pick — An NBA Fantasy Selection & Discipline Experiment

### User and Problem

The main user of this system will be me. The problem I want to work on is not simply finding good NBA fantasy selections. I want to improve the discipline and consistency of how I make those selections.

When I make fantasy selections, I normally rank them from the ones I trust the most to the ones I trust less. One pattern I have noticed is that when I make a larger entry and miss one or two selections, the misses are often among the lower-confidence selections that I added after my strongest choices.

I want to test whether an agent can learn and consistently apply my NBA fantasy-selection strategy while also helping me follow an important rule: **know when to stop**.

### Proposed System

The system will gather current NBA fantasy projections from supported sources and evaluate them using strategies and rules that I provide.

These rules can include which players, teams, or situations I want to avoid; whether I consider a player stronger for points, rebounds, assists, or PRA; possible foul trouble; matchup conditions; and situations where a game may become a blowout and reduce a player's minutes.

The system will evaluate possible Higher and Lower selections, remove candidates that violate my rules, and rank the remaining candidates from strongest to weakest.

An important part of the system will be a **Stop Gate**. The maximum number of final selections will not be treated as a target. For a small slate, the system can recommend no more than four selections. For a large slate, it can recommend no more than five. If only two selections meet the required standard, the system should stop at two. If none meet the standard, it should return:

**NO ENTRY RECOMMENDED TODAY.**

I will remain **Governance 0**, meaning I have the final decision. I can accept fewer selections than the agent recommends, reject a selection, or make no entry. The system will not automatically submit an entry or make the final decision for me.

The final evaluation will normally happen about **20 minutes before the relevant game begins**. Earlier analysis can create a watchlist, but a candidate must survive the final review of current projections, player availability, lineup or role information, and other relevant conditions before becoming a final recommendation.

### Why This Project Fits the Semester

This project gives me room to use the different things I learned during the semester.

The **agent loop** can allow the system to gather information, evaluate a candidate, apply my rules, observe new information, and continue until it reaches a reason to recommend, reject, or stop.

**Patterns and orchestration** can help organize the different steps used to gather projections, evaluate candidates, rank them, and apply the Stop Gate.

**Tools and MCP** can allow the system to access supported sources and other approved tools for current fantasy and NBA information.

**Context and memory** can help the system keep track of my documented strategies, player-specific rules, previous decisions, and changes during the NBA season.

**Evaluation** will allow me to test two different things. First, I can test whether the agent correctly followed my documented strategy. Second, I can track the actual results of the selections over time and determine whether my strongest-ranked selections perform better than the lower-ranked selections.

**Governance and human oversight** are important because the agent recommends selections, but I remain responsible for the final decision.

Finally, **deployment and runtime** will allow me to run the system as a CLI, record what information it used, what rules were applied, which candidates were rejected, what it recommended, and why it stopped.

### Biggest Risk

One of the biggest risks is treating an uncertain prediction as if it were guaranteed.

NBA fantasy outcomes can change because of injuries, foul trouble, changes in playing time, blowouts, lineup changes, or normal game variation. A good decision can still have a bad result.

Because of this, I do not want to evaluate the system only by whether an individual selection wins or loses. I also want to measure whether the agent correctly followed the strategy and rules that I gave it.

Another important risk is bad or outdated information. The system should not invent projections, injuries, lineup information, or other evidence. If the information needed to evaluate a candidate is unavailable, the system should show that uncertainty instead of pretending to know.

## PEAS Specification

### Performance Measure — Evaluation and Feedback

I will measure whether the agent correctly follows my documented fantasy-selection strategy, respects the Stop Gate, avoids prohibited selections, uses the correct fantasy market for a player, and gives reasons for its decisions.

I will separately track actual selection results, hit rate, and performance by ranking position to test whether my strongest-ranked selections perform better than lower-ranked selections.

**Nine-component mapping:** Evaluation and Feedback.

### Environment — Runtime and Operations

The environment is the NBA fantasy-selection process during the 2026–27 NBA season. It includes NBA games, players, current fantasy projections, player availability, lineup and role information, matchup conditions, and the strategy rules I provide.

**Nine-component mapping:** Runtime and Operations.

### Actuators — Tools and Orchestration

The system can gather available fantasy projections and NBA information, evaluate candidates, reject candidates that violate my rules, rank the remaining candidates, apply the Stop Gate, and produce a final recommendation or **NO ENTRY RECOMMENDED TODAY**.

The system will not automatically submit fantasy entries.

**Nine-component mapping:** Tools and Orchestration.

### Sensors — Perception

The system receives current fantasy projections, NBA player and game information, injury or availability information, lineup and role information when available, and my documented fantasy-selection rules.

**Nine-component mapping:** Perception.
