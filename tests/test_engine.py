import unittest
from datetime import datetime, timedelta

from stock_watcher.engine import should_send_stock_alert
from stock_watcher.models import CheckResult, StockStatus
from stock_watcher.state import ItemState


def _result(status: StockStatus) -> CheckResult:
    return CheckResult(
        item_id="a",
        item_name="A",
        url="http://example.com",
        retailer="generic",
        status=status,
        matched_text="x",
        checked_at=datetime.now(),
    )


class EngineTests(unittest.TestCase):
    def test_transition_to_in_stock_alerts(self):
        state = ItemState(status=StockStatus.OUT_OF_STOCK.value)
        self.assertTrue(should_send_stock_alert(_result(StockStatus.IN_STOCK), state, 12))

    def test_no_alert_for_out_of_stock(self):
        state = ItemState(status=StockStatus.OUT_OF_STOCK.value)
        self.assertFalse(should_send_stock_alert(_result(StockStatus.OUT_OF_STOCK), state, 12))

    def test_repeat_alert_after_window(self):
        state = ItemState(
            status=StockStatus.IN_STOCK.value,
            last_alert_at=datetime.now() - timedelta(hours=13),
        )
        self.assertTrue(should_send_stock_alert(_result(StockStatus.IN_STOCK), state, 12))

    def test_no_repeat_before_window(self):
        state = ItemState(
            status=StockStatus.IN_STOCK.value,
            last_alert_at=datetime.now() - timedelta(hours=1),
        )
        self.assertFalse(should_send_stock_alert(_result(StockStatus.IN_STOCK), state, 12))


if __name__ == "__main__":
    unittest.main()
