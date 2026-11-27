This module fixes a click in looping recorder playback. A FLEX voice playing
its own recorder buffer every bar now re-primes cleanly at tempos where a bar
is not a whole number of samples (such as 82,687.5 samples at 128 BPM). It
adds no panel controls.
