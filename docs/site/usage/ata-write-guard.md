## What this changes

A card-write path: stock's initial PIO write could hang polling the card
after a task switch; the guard keeps its critical section intact.
Measured under the port, not on hardware. Nothing on the panel.
