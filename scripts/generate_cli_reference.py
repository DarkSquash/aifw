"""Generate the reference directly from the Python argument parser."""

from pathlib import Path
import sys

from aifw.cli import create_parser


def render():
    parser = create_parser()
    sections = [
        f"## `aifw {' '.join(parts)}`\n\n```text\n{leaf.format_help().rstrip()}\n```"
        for parts, leaf in parser.command_parsers.items()
    ]
    return "\n".join(
        [
            "# Referência gerada da CLI do AIFW",
            "",
            "> Gerado por `python scripts/generate_cli_reference.py`. Guia: [HOW_TO_USE.md](../HOW_TO_USE.md).",
            "",
            f"Esta referência contém {len(sections)} comandos finais e suas opções.",
            "",
            "## `aifw --help`",
            "",
            "```text",
            parser.format_help().rstrip(),
            "```",
            "",
            "\n\n".join(sections),
            "",
        ]
    )


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "docs/cli-reference.generated.md"
    expected = render()
    if "--check" in sys.argv:
        if not output.exists() or output.read_text(encoding="utf-8") != expected:
            print("CLI reference is stale. Run python scripts/generate_cli_reference.py.", file=sys.stderr)
            raise SystemExit(2)
    else:
        output.write_text(expected, encoding="utf-8", newline="\n")
        print("Updated docs/cli-reference.generated.md")
