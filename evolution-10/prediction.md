# Sortie 10 prediction draft

The threshold is 12 of 12 passing. Seven cases must refuse. Each expected
value comes from the frozen universe or the LIVE market and identity rules.
The proposed baseline is the all-green acceptance target, pending TP1.
No graded sortie can run before a qualifying E9 PASS and a dated Chase GO.

For TP2, remove only the exact-grant rejection in
`final-project/src/fifth_pick/authorization.py`: delete the assignment to
`grant` and the following `if grant not in player.grants` block, leaving
the canonical-player, enum, and LIVE-category checks intact. The earlier
`AuthorizationGrant` import may remain in the isolated witness checkout.

Predicted RED cases: `mit-p-hi`, `mit-pra-lo`, `tat-ast-hi`,
`white-pra-lo`, and `monk-p-hi`. The remaining seven cases stay green.
Restore the file before TP3.

For TP4, substitute Boolean true for the actual authorization result in
`mit-p-hi`. Its expected result remains false. For TP5, compare every
case with both constant Boolean authorization results. A case is hollow
if both constants pass it.
