"""Pure rendering: (state) -> rich renderable. No I/O, no state ownership."""

from collections import deque
from functools import lru_cache

from pyfiglet import Figlet
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from chords import (
    ChordResult,
    midi_to_display_name,
    midi_to_pitch_class,
    unique_pitch_classes_lowest_first,
)

BANNER_FONT = "banner"


@lru_cache(maxsize=1)
def _figlet() -> Figlet:
    return Figlet(font=BANNER_FONT)


def _styled_label(label: str, style: str, banner: bool) -> Text:
    if banner:
        # No justify: pyfiglet already pads every row to the same width, and
        # Rich's per-line justify would re-center each row independently off
        # its own (whitespace-stripped) content, distorting the glyph shape.
        # Align.center() in build_display centers the whole block instead.
        return Text(_figlet().renderText(label).rstrip("\n"), style=style)
    return Text(label, style=style, justify="center")


def _primary_line(held_notes: list[int], result: ChordResult, banner: bool) -> Text:
    if result.kind == "silence":
        return Text("—", style="dim", justify="center")
    if result.kind == "single":
        return _styled_label(midi_to_pitch_class(held_notes[0]), "bold", banner)
    if result.kind == "interval":
        names = unique_pitch_classes_lowest_first(held_notes)
        return _styled_label(" + ".join(names), "bold", banner)
    # kind == "chords"
    if result.primary is None:
        return Text("no chord match", style="dim italic", justify="center")
    return _styled_label(str(result.primary), "bold cyan", banner)


def build_display(
    held_notes: list[int],
    result: ChordResult,
    history: deque[str],
    port_names: list[str],
    banner: bool = False,
) -> RenderableType:
    parts: list[RenderableType] = []

    parts.append(Align.center(_primary_line(held_notes, result, banner)))

    if result.kind == "chords" and result.alternates:
        alt_names = ", ".join(str(c) for c in result.alternates)
        parts.append(Align.center(Text(f"also matches: {alt_names}", style="dim")))

    held_line = (
        ", ".join(midi_to_display_name(n) for n in held_notes)
        if held_notes
        else "(no notes held)"
    )
    parts.append(Text(""))
    parts.append(Text(f"held: {held_line}", style="dim"))

    if history:
        parts.append(Text(f"recent: {' → '.join(history)}", style="dim"))

    return Panel(
        Group(*parts),
        title=f"chordtop — {', '.join(port_names)}",
        border_style="blue",
    )
