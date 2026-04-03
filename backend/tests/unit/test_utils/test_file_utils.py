from app.utils.file_utils import sanitize_filename, get_unique_filename

def test_sanitize_filename():
    assert sanitize_filename("../../etc/passwd") == "passwd"

def test_get_unique_filename():
    assert get_unique_filename("test.txt") != "test.txt"
