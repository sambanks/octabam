# About

## Why Octabam exists

I started Octabam because I love the Octatrack. It's the center of my workflow and my entire creative process, but I've never particularly enjoyed its effects, so I've always relied on Eventide effects on the cue output as an FX loop. When a friend shared the octamax repo with me on Discord, I saw an opportunity to create some new effects that were more to my taste and would streamline my workflow.

After offering to contribute my effects to octamax and speaking with Max on Discord, we decided it would be best if I forked the repo and shared my progress with him. That way he could ingest any parts he wanted, but retain his repo's focus on specific improvements.

Originally I intended to make my effects, get back to music, and share my repo so others could do the same for themselves. That remains the spirit of my focus. However, when things exploded online and people started sharing (and often misrepresenting) my repo on Elektronauts and social media, I decided to make the octahackers Discord so other developers could collaborate and share code in a more appropriate forum. Now there are over 2,000 people on there, with channels for hacking almost every Elektron device ever created, along with channels for specific community efforts such as Octabam.

As with all community building efforts (accidental or intentional), there have been some growing pains, but generally it's been an incredibly fruitful collaborative space where people can discuss and share their ideas with like-minded individuals from all around the world. Every day I receive pull requests from new developers with mind-blowing modules that I never could have conceived for the Octatrack, which is hugely rewarding.

As far as Octabam goes, my focus these days is on creating a stable, stage-ready range of firmware revisions that will keep the Octatrack churning out the bangers for many years to come.

We are getting close to our first stable releases now, so watch this space!

## What it is

Octabam is an unofficial community firmware remixer for the Elektron Octatrack,
and is not affiliated with Elektron. A **module** adds a single feature, and a
**remix** is a named set of modules built into one image from your own copy of
OS 1.40C. This site covers Octabam v0.6 and its three official remixes:
[Octabam](remix-octabam.md), [Octabam Verbs](remix-octabam-verbs.md), and
[Octabam Bus](remix-octabam-bus.md). See
[Create your own remix](own-remix.md) if you want to combine other modules.

## How it is made

- Each module is contributed by its author and credited on its manual page and
  in [Credits](reference/manual/credits.md).
- Modules ported from existing mods are checked byte for byte against the
  original author's build.
- The build catches conflicts if two selected modules claim the same memory,
  hook, or effect ID, and reports both by name.
- Firmware images are built locally from your own copy of OS 1.40C, either in
  the browser or from source. Because built images contain Elektron's OS, keep
  them private.
- Source code, issues, and pull requests live in the
  [repository](https://github.com/sambanks/octabam). The repository's own code
  and documentation are licensed under MIT; Elektron's firmware is not
  distributed.

## Status and testing

Octabam is a community project currently at version 0.6 (version 0.1 was the
initial release). If you run into a bug or crash, see
[Safety and Recovery](safety.md) and report it on GitHub Issues.

## Get involved

Use [GitHub Issues](https://github.com/sambanks/octabam/issues) for bug
reports, module proposals, and hardware test reports. Pull requests are welcome
for new modules, ports of existing mods, bugfixes, and documentation
improvements; see
[CONTRIBUTING](https://github.com/sambanks/octabam/blob/main/CONTRIBUTING.md)
for the guidelines.
