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

# A detected chord is the headline result, so it gets a bold, saturated color
# that reads clearly against the panel's blue border. Everything else (bare
# held notes, alternates, history) stays neutral/dim so the chord stands out.
CHORD_STYLE = "bold green"
NOTE_STYLE = "bold grey62"


@lru_cache(maxsize=1)
def _figlet() -> Figlet:
    return Figlet(font=BANNER_FONT)


def _banner_height() -> int:
    return _figlet().Font.height


def _pad_to_banner_height(text: Text) -> Text:
    # Keeps the primary line's row count constant across banner and
    # non-banner renders (e.g. silence, no-chord-match) so the panel
    # doesn't grow and shrink as chords are played and released.
    missing = _banner_height() - text.plain.count("\n") - 1
    if missing <= 0:
        return text
    top = missing // 2
    bottom = missing - top
    return Text("\n" * top) + text + Text("\n" * bottom)


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
        text = Text("—", style="dim", justify="center")
        return _pad_to_banner_height(text) if banner else text
    if result.kind == "single":
        return _styled_label(midi_to_pitch_class(held_notes[0]), NOTE_STYLE, banner)
    if result.kind == "interval":
        names = unique_pitch_classes_lowest_first(held_notes)
        return _styled_label(" + ".join(names), NOTE_STYLE, banner)
    # kind == "chords"
    if result.primary is None:
        text = Text("no chord match", style="dim italic", justify="center")
        return _pad_to_banner_height(text) if banner else text
    return _styled_label(str(result.primary), CHORD_STYLE, banner)


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
    elif banner:
        # Reserve the row even when empty, so the panel height doesn't
        # shift depending on whether alternates are present.
        parts.append(Text(""))

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
