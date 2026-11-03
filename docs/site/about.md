# About

## Why Octabam exists

I started Octabam because I love the Octatrack. It's the center of my workflow and my entire creative process, but I've never particularly enjoyed its effects, so I've always relied on Eventide effects on the cue output as an FX loop. When a friend shared the octamax repo with me on Discord, I saw an opportunity to create some new effects that were more to my taste and would streamline my workflow.

After offering to contribute my effects to octamax and speaking with Max on Discord, we decided it would be best if I forked the repo and shared my progress with him. That way he could ingest any parts he wanted, but retain his repo's focus on specific improvements.

Originally I intended to make my effects, get back to music, and share my repo so others could do the same for themselves. That remains the spirit of my focus. However, when things exploded online and people started sharing (and often misrepresenting) my repo on Elektronauts and social media, I decided to make the octahackers Discord so other developers could collaborate and share code in a more appropriate forum. Now there are over 2,000 people on there, with channels for hacking almost every Elektron device ever created, along with channels for specific community efforts such as Octabam.

As with all community building efforts (accidental or intentional), there have been some growing pains, but generally it's been an incredibly fruitful collaborative space where people can discuss and share their ideas with like-minded individuals from all around the world. Every day I receive pull requests from new developers with mind-blowing modules that I never could have conceived for the Octatrack, which is hugely rewarding.

As far as Octabam goes, my focus these days is on creating a stable, stage-ready range of firmware revisions that will keep the Octatrack churning out the bangers for many years to come.

We are getting close to our first stable releases now, so watch this space!

## What it is

Octabam is an unofficial community remixer for the Elektron Octatrack's
operating system. It is not affiliated with Elektron. A **module** adds one
feature; a **remix** is a named set of modules built into one image from
your own copy of OS 1.40C. This site covers Octabam v0.3, one remix
([what is in it](remix-octabam.md)); [Create your own remix](own-remix.md)
covers choosing other modules.

## How it is made

- Every module is contributed by its author and credited on its page and in
  [Credits](reference/manual/octabam/credits.md).
- A module ported from an existing mod is checked byte for byte against the
  author's own build.
- The build refuses to combine modules that claim the same memory, hook or
  effect id, and names the clash.
- Images are derived from your own OS 1.40C on your own computer, in the
  browser or from source. The built file contains Elektron's OS and stays
  with you.
- Source, issues and pull requests are in the
  [repository](https://github.com/sambanks/octabam). The licence is MIT for
  the repository's own code and documentation; Elektron's firmware is not
  distributed.

## Status and testing

Octabam is a community project and version 0.1 was its first release; this site is version 0.3. If
something misbehaves, see [Safety and Recovery](safety.md) and report it on
GitHub Issues.

## Get involved

[GitHub Issues](https://github.com/sambanks/octabam/issues) take bug
reports, module proposals and hardware test reports. Pull requests are
accepted for a module, a port of an existing mod, a fix, or a doc
correction; [CONTRIBUTING](https://github.com/sambanks/octabam/blob/main/CONTRIBUTING.md)
has the rules.
