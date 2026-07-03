"""Pure chord-identification logic: MIDI note numbers -> ChordResult.

No I/O here — this module only knows about lists of MIDI note numbers (0-127)
and pychord's Chord objects.
"""

from dataclasses import dataclass, field
from typing import Literal

from pychord import Chord
from pychord.analyzer import find_chords_from_notes

# Sharp-only spelling. Key-aware enharmonic spelling (Gb vs F#) is out of
# scope for v1 -- this table is the hook to add a flats mode later.
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_pitch_class(note: int) -> str:
    """Bare pitch-class name with no octave digit, e.g. 60 -> 'C'."""
    return NOTE_NAMES[note % 12]


def midi_to_display_name(note: int) -> str:
    """Pitch class + octave for display, e.g. 61 -> 'C#4'."""
    octave = note // 12 - 1
    return f"{midi_to_pitch_class(note)}{octave}"


def unique_pitch_classes_lowest_first(held_notes: list[int]) -> list[str]:
    """Dedupe held MIDI notes by pitch class, keeping the lowest note's
    position first. This is what makes pychord's bass-aware slash-chord
    detection "free" -- pychord treats the first list element as the bass.
    """
    seen: set[str] = set()
    result: list[str] = []
    for note in sorted(held_notes):
        pc = midi_to_pitch_class(note)
        if pc not in seen:
            seen.add(pc)
            result.append(pc)
    return result


ChordKind = Literal["silence", "single", "interval", "chords"]


@dataclass
class ChordResult:
    kind: ChordKind
    held_notes: list[int]
    primary: Chord | None = None
    alternates: list[Chord] = field(default_factory=list)


def identify_chords(held_notes: list[int]) -> ChordResult:
    pitch_classes = unique_pitch_classes_lowest_first(held_notes)

    if len(pitch_classes) == 0:
        return ChordResult(kind="silence", held_notes=held_notes)
    if len(pitch_classes) == 1:
        return ChordResult(kind="single", held_notes=held_notes)
    if len(pitch_classes) == 2:
        # pychord's 2-note "qualities" (e.g. "no5") produce confusing labels
        # for a bare interval, so we don't send these to pychord at all.
        return ChordResult(kind="interval", held_notes=held_notes)

    matches = find_chords_from_notes(pitch_classes)

    if not matches:
        return ChordResult(kind="chords", held_notes=held_notes)
    return ChordResult(
        kind="chords",
        held_notes=held_notes,
        primary=matches[0],
        alternates=matches[1:],
    )


if __name__ == "__main__":
    # Inline sanity checks -- no hardware needed, run with `uv run chords.py`.
    def notes_for(*pitch_classes_with_octave: str) -> list[int]:
        # helper only for these self-checks
        pc_to_idx = {name: i for i, name in enumerate(NOTE_NAMES)}
        result = []
        for spec in pitch_classes_with_octave:
            pc, octave = spec[:-1], int(spec[-1])
            result.append((octave + 1) * 12 + pc_to_idx[pc])
        return result

    r = identify_chords(notes_for("C4", "E4", "G4"))
    assert r.kind == "chords" and str(r.primary) == "C", r

    r = identify_chords(notes_for("F3", "G3", "C4"))
    assert r.kind == "chords" and str(r.primary) == "Fsus2", r
    assert [str(c) for c in r.alternates] == ["Csus4/F"], r

    r = identify_chords(notes_for("E3", "G3", "C4"))
    assert r.kind == "chords" and str(r.primary) == "C/E", r

    r = identify_chords([])
    assert r.kind == "silence", r

    r = identify_chords(notes_for("C4"))
    assert r.kind == "single", r

    r = identify_chords(notes_for("C4", "E4"))
    assert r.kind == "interval", r

    # Same pitch class in two octaves should still dedupe to a 2-note interval.
    r = identify_chords(notes_for("C3", "G3", "C4"))
    assert r.kind == "interval", r

    print("All chords.py sanity checks passed.")
