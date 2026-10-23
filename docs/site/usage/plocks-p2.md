Use page 2 parameter locks to automate FX1 or FX2 parameters that are not
available on stock page 1.

A step can carry locks for both FX pages.

## Create and remove a lock

Open the FX1 or FX2 SETUP page, hold one or more trigs and turn a knob:
each held step gets that slot's page-2 lock. Hold FUNC while turning to
remove it. The trig plays the lock, and the next trig puts the Part's
value back — the same as page 1.

After the same short hold delay as page 1, the page-two lock value stays visible with the value
area highlighted, as on page 1. The parameter name stays unchanged.
Turning a knob while holding a trig updates the displayed lock immediately.
Releasing the trig shows the Part value again and keeps the step's lock. A later bare trig tap still clears the step and its locks.

![GVOL locked to 50 while trig 1 is held](../../img/plocks-p2/lock.png)

![GVOL returns to the Part value 20 on release](../../img/plocks-p2/released.png)

The locks move with the data: trig copy and paste, clear a trig's locks,
pattern copy and paste, clear a pattern and its undo each carry or clear
them. SAVE PROJECT writes them and a power cycle loads them back.

## Limits and saving

- Page 2 has no slide: a slide trig moves page 1 only.
- A held step with no trig takes a page-2 lock that never plays.
- The power-off copy of the current bank holds 4,768 locks. A bank with
  more has no power-cut copy: a power cut loses its unsaved page-2 locks
  back to the last save.

EDIT EVENTS coordinates held-step editing and clipboard/undo copying for
registered extensions. PLOCKS P2 is its first client. This adds no controls.

Core PLK858/build 98: held edits and copy/undo checked on an MKII, 22 October
2026.
