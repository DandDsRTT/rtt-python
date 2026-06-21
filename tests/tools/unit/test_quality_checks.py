import ast

from tools import quality_checks as qc


def test_line_count_counts_final_unterminated_line():
    assert qc.line_count("a\nb\nc") == 3
    assert qc.line_count("a\nb\nc\n") == 3
    assert qc.line_count("") == 0


def test_file_length_violation_only_over_limit():
    under = "x = 1\n" * qc.MAX_FILE_LINES
    over = "x = 1\n" * (qc.MAX_FILE_LINES + 1)
    assert file_length_violations(under) == []
    flagged = file_length_violations(over)
    assert len(flagged) == 1
    assert "file is" in flagged[0].message


def test_function_length_violation_reports_name_and_span():
    body = "\n".join(f"    x{i} = {i}" for i in range(qc.MAX_FUNCTION_LINES + 5))
    source = f"def big():\n{body}\n"
    flagged = function_length_violations(source)
    assert len(flagged) == 1
    assert flagged[0].message.startswith("big is")


def test_short_function_is_clean():
    assert function_length_violations("def small():\n    return 1\n") == []


def test_docstring_violation_flags_module_class_function():
    source = '"""m"""\nclass C:\n    """c"""\n    def f(self):\n        """f"""\n        return 1\n'
    messages = [v.message for v in docstring_violations(source)]
    assert messages == ["docstring is banned"] * 3


def test_no_docstring_is_clean():
    assert docstring_violations("def f():\n    return 1\n") == []


def test_collect_and_main_over_a_tree(tmp_path, capsys):
    bad = tmp_path / "pkg"
    bad.mkdir()
    (bad / "m.py").write_text('"""doc"""\ndef f():\n    return 1\n')
    assert qc.main(["prog", str(tmp_path)]) == 1
    assert "docstring is banned" in capsys.readouterr().out


def test_main_clean_tree_returns_zero(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    assert qc.main(["prog", str(tmp_path)]) == 0


def file_length_violations(text):
    return qc.file_length_violations("m.py", text)


def function_length_violations(source):
    return qc.function_length_violations("m.py", ast.parse(source))


def docstring_violations(source):
    return qc.docstring_violations("m.py", ast.parse(source))
