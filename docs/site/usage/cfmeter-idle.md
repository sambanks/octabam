This diagnostic module measures how much CPU time the ColdFire spends idle, supplying the idle-time readout for CF Meter. It times `main`'s idle loop: because `main` runs at priority 0 and never blocks, it executes only when no other task is ready and no interrupt is active.

## Access

This module has no menu or screen of its own. It pairs with CF Meter in diagnostic remixes that include both (such as `cfmeter`, `cfmeter-post`, and `cfmeter-tracks`), where the idle measurement appears in CF Meter's readout. It is not included in the standard remixes.

## Operation

- It replaces the final initialization call in `main` and its trailing `bras .` instruction with that call followed by a loop that polls DMA timer 3.
- Any loop iteration shorter than twice the shortest observed iteration plus 8 counts is added to CF Meter's idle counter; longer iterations indicate preemption by an interrupt or another task. The shortest observed step is reported in slot 6.
- Under the port, the loop boots and loads a project, though accurate idle figures require running on hardware: once a borrowed call returns to the stock `bras .`, `main` parks there and idle accounting stops.
