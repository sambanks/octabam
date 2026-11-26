DLPUMP is the sending half of the two-part effect loader, paired with the [copier](dlcopy.md). SPECTRUM, CHARACTER, MODULATION, SHATTER, and COMPRESSOR's side-chain do not stay loaded in the effects processor at all times; the loader loads an effect when a track uses it and unloads it when none does. DLPUMP streams the effect code to the processor in small chunks. It has no controls or panel indicators.

## What you will notice

- Audio passes through dry for about 25 ms after you select one of these effects while its code finishes loading.
- A pattern change that adds one of these effects to all eight tracks (or removes it from all eight) produces about 0.34 s of silence during the transition.
- In Octabam, a loaded effect shares memory with stock reverbs (PLATE, SPRING, and DARK) on the same FX2 slot. Selecting a stock reverb while a loaded effect is using that memory, or selecting a loaded effect while a stock reverb is using it, is blocked with a message. If a project assigns both through another path (such as loading a saved Part), one of them stays dry and a message identifies which one the next time you press a page key.
