Use page 2 parameter locks to automate FX1 or FX2 parameters that are not
available on stock page 1.

A step can hold locks for both FX pages at once.

## Create and remove a lock

Open the FX1 or FX2 SETUP page, hold one or more trigs, and turn a knob to set
that parameter's page-2 lock on each held step. To remove a lock, hold the
trig and press the knob, or hold FUNC while turning it. Pressing the knob for
an unlocked parameter locks it to the Part's current value. Page-1 locks
behind the window are left untouched. When the step plays, it applies the
lock, and the next trig restores the Part's value just like page 1.

After the same short hold delay as page 1, the locked value stays on screen
with the value area highlighted while the parameter name stays unchanged.
Turning a knob while holding a trig updates the displayed lock immediately.
Releasing the trig restores the Part value display while keeping the step's
lock. A normal bare trig tap still clears the step and its locks.

![GVOL locked to 50 while trig 1 is held](../../img/plocks-p2/lock.png)

![GVOL returns to the Part value 20 on release](../../img/plocks-p2/released.png)

Page-2 locks follow standard editing operations: copying, pasting, clearing,
and undoing trigs or patterns copies or clears them accordingly. SAVE PROJECT
writes them to storage, and they persist across a power cycle.

## Limits and saving

- Page 2 does not support parameter slides; slide trigs affect page 1 only.
- Holding an empty step still creates a page-2 lock, though it will not play
  without a trig.
- The power-off backup of the current bank holds up to 4,768 locks. If a bank
  exceeds that limit, no power-off backup is kept, so a power cut loses
  unsaved page-2 locks back to the last save.

Page-2 locks add no controls of their own and use the same trig-hold and FUNC
gestures as page 1.
