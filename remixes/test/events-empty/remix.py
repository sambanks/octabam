"""EVENTS without any subscribers: no event code or detours."""
from remix.schema import Evidence, Level, Remix

REMIX = Remix(
    name='events-empty', family='probes', evidence=(Evidence(Level.EMULATOR,
        note="Empty EVENTS selection: stock boundaries checked in the built image."),),
    doc='EVENTS with no clients: no event hooks or dispatcher code.',
    modules=('EVENTS', 'FILTER', 'PLATE REV'), fallback='NONE',
)
