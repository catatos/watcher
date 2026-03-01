import unittest
from datetime import datetime, timedelta

from stock_watcher.engine import _daily_summary_due


class SummaryTests(unittest.TestCase):
    def test_daily_summary_due_when_never_sent(self):
        self.assertTrue(_daily_summary_due(None, "00:00"))

    def test_daily_summary_not_due_before_time_today(self):
        future = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        self.assertFalse(_daily_summary_due(datetime.now() - timedelta(days=1), future))


if __name__ == "__main__":
    unittest.main()
