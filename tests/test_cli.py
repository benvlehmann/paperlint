from paperlint.cli import main


def test_usage():
    assert main([]) == 2


def test_error_exits_nonzero(tmp_path):
    path = tmp_path / "main.tex"
    path.write_text("$$x$$\n", encoding="utf-8")
    assert main([str(path)]) == 1


def test_warnings_exit_zero(tmp_path):
    path = tmp_path / "main.tex"
    path.write_text("e.g. next\n", encoding="utf-8")
    assert main([str(path)]) == 0


def test_missing_file(tmp_path):
    assert main([str(tmp_path / "nope.tex")]) == 2
