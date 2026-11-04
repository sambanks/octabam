![BRAIN: Log](../../img/brain/log.png)

*BRAIN: Log*

Use **LEFT / RIGHT** to switch between **EVENTS** and **MIDI**.

**EVENTS** holds the latest 40 events, newest first: FRAME OVER, CPU FULL, and CARD SLOW. Each entry includes the uptime when it occurred. Turn off **EVENT LOG** to stop recording events.

**MIDI** shows the latest 24 decoded messages. **MIDI LOG** controls the debug recording. **WRITE DEBUG LOG** saves the last 256 messages to `/BRAIN/debug.txt` on the card, leaving out clock and active sensing. Both logging switches are on by default.
