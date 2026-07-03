# chordtop

A live MIDI chord identifier for the terminal. Runs alongside your DAW: your
MIDI keyboard is opened as an input by both the DAW and this app at the same
time (macOS Core MIDI supports multiple simultaneous listeners on one device, so
no virtual MIDI routing is needed), and this app shows the chord name for
whatever you're currently holding.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

## Run

```sh
uv run main.py
```

By default, every connected MIDI input port is auto-detected and opened at
startup. Ports that look like control-surfaces (name contains "mcu", "hui",
"control", or "transport") are excluded.

### Multiple keyboards

Notes from all open ports are merged into one pool before chord detection, so
you can play across multiple and still get one combined chord reading. Each
port tracks its own held notes independently

Other flags:

```sh
uv run main.py --list-ports                       # list all ports, flagging which are excluded by default
uv run main.py --port Minilab                      # only listen to a specific port (substring match)
uv run main.py --port Minilab --port Keystation     # only listen to specific ports (repeat --port)
uv run main.py --all-ports                          # also include control-surface-looking ports
uv run main.py --no-pedal                            # ignore the sustain pedal (CC64)
uv run main.py --banner                              # display the chord in large banner-style text
```

## Notes

- Chord recognition is powered by pychord. With 3+ distinct pitch classes held,
  it can return multiple equally valid interpretations (e.g. holding F-G-C shows
  `Fsus2`, with `Csus4/F` noted as an alternate) — the lowest note you're holding
  is used as the bass, so inversions/slash chords are detected automatically.

## Built with

- [`mido`](https://github.com/mido/mido) + [`python-rtmidi`](https://github.com/SpotlightKid/python-rtmidi) — MIDI port discovery and I/O
- [`pychord`](https://github.com/yuma-m/pychord) — chord recognition from held notes
- [`rich`](https://github.com/Textualize/rich) — the live terminal display
- [`pyfiglet`](https://github.com/pwaller/pyfiglet) — large banner-style text (`--banner`)
