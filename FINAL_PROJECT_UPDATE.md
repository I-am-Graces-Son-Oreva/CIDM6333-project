# The Fifth Pick — Final Project Update

## An NBA Fantasy Selection & Discipline Experiment

My final project is **The Fifth Pick**, an NBA fantasy-selection agent and experiment for the 2026–27 NBA season.

The idea comes from something I have noticed in my own fantasy selections. I normally rank my picks from the ones I trust the most to the ones I trust less. When I make larger entries and finish 4/6 or 5/6, the selections that miss are often among my lower-confidence choices. This made me interested in testing whether knowing when to stop can improve my decision process.

My main question is:

**Can I teach an agent my NBA fantasy-selection strategy and use it to make my process more disciplined and consistent?**

I plan to teach the agent the strategies I already use when evaluating Higher and Lower fantasy projections. This includes how I evaluate points, rebounds, assists, and PRA, as well as teams or situations I avoid, foul-trouble risk, player roles, matchup conditions, and possible blowouts. The agent should follow my documented strategy rather than create its own rules.

An important part of the project is the **Stop Gate**. For a small slate, the maximum will be four final selections. For a large slate, the maximum will be five. These are ceilings, not targets. If only two selections meet my standard, the agent should stop at two. If nothing qualifies, it should return **NO ENTRY RECOMMENDED TODAY.** I remain **Governance 0**, meaning I make the final decision and can always reduce or reject the recommendations.

I also plan to use a **T-20 rule**. Final candidates will normally be reviewed about 20 minutes before their game begins because player availability, starting lineups, roles, and other information can change close to game time. Earlier analysis can create a watchlist, but those candidates must survive the final review.

I want the system to gather current fantasy projections from supported sources such as Underdog, PrizePicks, Dabble, or DraftKings instead of requiring me to manually enter every candidate. I plan to begin with one reliable source and build the project as a CLI system.

I am currently in the **planning and design stage**. I have not built the final project yet. During the experiment, I want to record the selections, rankings, reasons, and eventual results. This will allow me to test whether my strongest-ranked selections actually perform better than my lower-ranked selections and whether the Stop Gate improves my decision discipline.

## Questions

1. Is this experiment an appropriate scope for the final project?
2. Is one reliable fantasy projection source enough for the project, or should I plan to integrate multiple sources?
