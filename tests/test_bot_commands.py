import os
import tempfile
import unittest

from stock_watcher.bot_commands import _parse_logs_count, tail_log_lines


class BotCommandTests(unittest.TestCase):
    def test_parse_logs_count_default(self):
        self.assertEqual(_parse_logs_count("/logs"), 30)

    def test_parse_logs_count_with_value(self):
        self.assertEqual(_parse_logs_count("/logs 15"), 15)

    def test_parse_logs_count_caps_max(self):
        self.assertEqual(_parse_logs_count("/logs 999"), 200)

    def test_tail_log_lines(self):
        fd, path = tempfile.mkstemp(prefix="watcher-log-", text=True)
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("a\n")
                f.write("b\n")
                f.write("c\n")
            out = tail_log_lines(path, lines=2)
            self.assertEqual(out, "b\nc")
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
