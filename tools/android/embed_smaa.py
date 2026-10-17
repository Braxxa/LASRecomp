"""Generate the renderer's SMAA string include without a Unix shell."""
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_bytes().replace(b"\r\n", b"\n").decode("ascii", errors="replace").replace("\ufffd", "?")
Path(sys.argv[2]).write_text("".join('"' + line.replace("\\", "\\\\").replace('"', '\\"') + '\\n"\n'
                                   for line in text.splitlines()), encoding="ascii")
