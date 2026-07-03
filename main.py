"""CLI entry point: wires MIDI input, chord detection, and the live TUI."""

import argparse
import sys
import threading
from collections import deque

from rich.live import Live

from chords import identify_chords
from midi_input import (
    NoteTracker,
    is_likely_control_surface_port,
    list_input_ports,
    open_midi_port,
    resolve_port_names,
    sorted_union,
)
from tui import build_display


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live MIDI chord identifier.")
    parser.add_argument(
        "--port",
        action="append",
        dest="ports",
        metavar="SUBSTRING",
        help="Substring to match against a MIDI input port name. Repeat to listen "
        "to multiple keyboards, e.g. --port Minilab --port Keystation. By default, "
        "every connected port is auto-detected and opened.",
    )
    parser.add_argument(
        "--all-ports",
        action="store_true",
        help="Also listen to ports that look like control surfaces (MCU/HUI/transport), "
        "which are excluded by default since they can send note-shaped button/LED messages.",
    )
    parser.add_argument(
        "--list-ports", action="store_true", help="List available MIDI input ports and exit."
    )
    parser.add_argument(
        "--no-pedal", action="store_true", help="Ignore the sustain pedal (CC64)."
    )
    parser.add_argument(
        "--banner",
        action="store_true",
        help="Display the detected chord in large banner-style text.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_ports:
        for name in list_input_ports():
            tag = " (excluded by default, looks like a control surface)" if is_likely_control_surface_port(name) else ""
            print(f"{name}{tag}")
        return

    try:
        port_names = resolve_port_names(args.ports, list_input_ports(), use_all=args.all_ports)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    # Two ports can enumerate under the identical name (e.g. two identical
    # keyboard models); we can't tell them apart by name, so only listen once.
    port_names = list(dict.fromkeys(port_names))
    print(f"Listening on: {', '.join(port_names)}")

    history: deque[str] = deque(maxlen=8)
    last_shown_chord: str | None = None
    held_by_port: dict[str, list[int]] = {name: [] for name in port_names}
    # Each port's MIDI callback runs on its own background thread, so all
    # reads/writes of the state above and the Live display must be
    # serialized through this lock.
    state_lock = threading.Lock()

    def merged_held_notes() -> list[int]:
        return sorted_union(*held_by_port.values())

    initial = build_display([], identify_chords([]), history, port_names, banner=args.banner)
    with Live(initial, auto_refresh=False) as live:

        def make_on_change(port_name: str):
            def on_change(held_notes: list[int]) -> None:
                nonlocal last_shown_chord
                with state_lock:
                    held_by_port[port_name] = held_notes
                    notes = merged_held_notes()
                    result = identify_chords(notes)
                    name = str(result.primary) if result.primary else None
                    if name and name != last_shown_chord:
                        history.append(name)
                    last_shown_chord = name
                    live.update(
                        build_display(notes, result, history, port_names, banner=args.banner),
                        refresh=True,
                    )

            return on_change

        trackers = [
            NoteTracker(make_on_change(name), pedal_enabled=not args.no_pedal)
            for name in port_names
        ]
        ports: list = []
        try:
            for name, tracker in zip(port_names, trackers):
                ports.append(open_midi_port(name, tracker))
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            for port in ports:
                port.close()


if __name__ == "__main__":
    main()
