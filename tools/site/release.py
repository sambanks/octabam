"""What the site and the web builder publish: one release of its remixes.

The generated manual, the remix overview table and `tools/web/publish.py` read
this, so a remix that is not listed here (the community and test remixes) has no
manual and no overview row. The remixes stay in the repository.

The web builder also offers every community remix (remixes/community/<name>/)
that builds at the release tag and passes `make check` in the publish run
(`tools/web/publish.py`); CI's own runs leave them out, so that check is theirs.
"""

VERSION = "v0.5"          # the git tag the builder's patches are built from
REMIXES = ("octabam", "octabam-verbs", "octabam-bus")
