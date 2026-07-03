"""MIDI I/O: port discovery/selection and held-note tracking.

No chord-detection or rendering knowledge lives here.
"""

import threading
from typing import Callable, Iterable

import mido

SUSTAIN_PEDAL_CC = 64
SUSTAIN_PEDAL_THRESHOLD = 64


# Substrings (case-insensitive) that suggest a port is a control-surface
# protocol channel (Mackie Control/HUI, transport buttons, etc.) rather than
# a source of musical notes. These protocols repurpose note_on/note_off
# messages for button/LED signaling, so auto-listening to them by default
# could inject garbage into chord detection.
#
# Deliberately specific rather than a bare "control" -- that generic word
# also appears in real note-producing keyboard names (e.g. "MIDI
# Controller"), which would wrongly exclude them from the default port list.
CONTROL_SURFACE_HINTS = ("mcu", "hui", "mackie control", "transport")


def list_input_ports() -> list[str]:
    return mido.get_input_names()


def sorted_union(*note_collections: Iterable[int]) -> list[int]:
    """Merge multiple collections of MIDI notes into one sorted, deduped list."""
    merged: set[int] = set()
    for notes in note_collections:
        merged.update(notes)
    return sorted(merged)


def is_likely_control_surface_port(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in CONTROL_SURFACE_HINTS)


def resolve_port_names(
    cli_args: list[str] | None,
    available: list[str],
    use_all: bool = False,
) -> list[str]:
    """Pick one or more MIDI input port names to listen to.

    - --port substring match(es) (repeatable flag) always wins, unfiltered --
      if you name a port explicitly, you get exactly that port. A substring
      that matches more than one available port is an error rather than
      silently picking one.
    - --all-ports opens every connected port, unfiltered.
    - Otherwise (the default), every connected port is opened *except* ones
      that look like control-surface protocol channels. If every port looks
      like a control surface, fall back to opening everything rather than
      silently listening to nothing.
    """
    if not available:
        raise RuntimeError("No MIDI input ports found. Is your keyboard connected?")

    if cli_args:
        resolved: list[str] = []
        for arg in cli_args:
            matches = [name for name in available if arg.lower() in name.lower()]
            if not matches:
                raise RuntimeError(
                    f"No MIDI input port matching {arg!r}. Available: {available}"
                )
            if len(matches) > 1:
                raise RuntimeError(
                    f"{arg!r} matches multiple MIDI input ports: {matches}. "
                    "Use a more specific substring."
                )
            if matches[0] not in resolved:
                resolved.append(matches[0])
        return resolved

    if use_all:
        return list(available)

    filtered = [name for name in available if not is_likely_control_surface_port(name)]
    return filtered if filtered else list(available)


class NoteTracker:
    """Tracks currently-held MIDI notes from a stream of mido messages,
    including basic sustain-pedal behavior (CC64).

    Thread-safe: `handle_message` is expected to run on mido/rtmidi's
    background callback thread.
    """

    def __init__(
        self, on_change: Callable[[list[int]], None], pedal_enabled: bool = True
    ):
        self._on_change = on_change
        self._pedal_enabled = pedal_enabled
        self._lock = threading.Lock()
        self._held: set[int] = set()
        self._sustained_but_released: set[int] = set()
        self._pedal_down = False

    def handle_message(self, msg: mido.Message) -> None:
        with self._lock:
            if msg.type == "note_on" and msg.velocity > 0:
                self._held.add(msg.note)
                self._sustained_but_released.discard(msg.note)
            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                self._held.discard(msg.note)
                if self._pedal_enabled and self._pedal_down:
                    self._sustained_but_released.add(msg.note)
                else:
                    self._sustained_but_released.discard(msg.note)
            elif (
                self._pedal_enabled
                and msg.type == "control_change"
                and msg.control == SUSTAIN_PEDAL_CC
            ):
                pedal_down = msg.value >= SUSTAIN_PEDAL_THRESHOLD
                if pedal_down and not self._pedal_down:
                    self._pedal_down = True
                elif not pedal_down and self._pedal_down:
                    self._pedal_down = False
                    self._sustained_but_released.clear()
            else:
                return

            snapshot = self._snapshot_locked()

        self._on_change(snapshot)

    def get_held_notes(self) -> list[int]:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> list[int]:
        return sorted_union(self._held, self._sustained_but_released)


def open_midi_port(name: str, tracker: NoteTracker) -> mido.ports.BaseInput:
    return mido.open_input(name, callback=tracker.handle_message)
