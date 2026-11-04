import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shell_integration import find_file_arg  # noqa: E402


def test_find_file_arg(tmp_path):
    f = tmp_path / "قائمة المشتركين 1.xlsx"
    f.write_bytes(b"x")
    assert find_file_arg([str(f)]) == str(f)
    assert find_file_arg(['"%s"' % f]) == str(f)           # بين علامتي اقتباس
    assert find_file_arg(["--flag", str(f)]) == str(f)
    assert find_file_arg([str(tmp_path / "missing.xlsx")]) is None
    txt = tmp_path / "a.txt"
    txt.write_bytes(b"x")
    assert find_file_arg([str(txt)]) is None
    assert find_file_arg([]) is None
