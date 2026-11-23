from analysis.tracker import functions_in


def test_same_method_name_in_two_classes():
    src = "class A:\n    def run(self): pass\nclass B:\n    def run(self): pass\n"
    assert set(functions_in(src)) == {"A.run", "B.run"}


def test_syntax_error_is_not_an_empty_file():
    assert functions_in("def broken(:") is None
    assert functions_in("") == {}