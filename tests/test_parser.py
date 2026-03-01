import unittest

from stock_watcher.models import AvailabilityRules, FilterConfig, StockStatus
from stock_watcher.parser import parse_availability


class ParserTests(unittest.TestCase):
    def test_in_stock_detected(self):
        html = "<html><body><button>Add to Cart</button></body></html>"
        out = parse_availability(html, AvailabilityRules(), FilterConfig())
        self.assertEqual(out.status, StockStatus.IN_STOCK)

    def test_out_of_stock_detected(self):
        html = "<html><body>Sorry, this item is sold out</body></html>"
        out = parse_availability(html, AvailabilityRules(), FilterConfig())
        self.assertEqual(out.status, StockStatus.OUT_OF_STOCK)

    def test_pickup_only_ignored_when_shipping_filter_on(self):
        html = "<html><body>Available for pickup only at local store</body></html>"
        out = parse_availability(html, AvailabilityRules(), FilterConfig())
        self.assertEqual(out.status, StockStatus.OUT_OF_STOCK)

    def test_unknown_when_no_signals(self):
        html = "<html><body>Product details and specs only</body></html>"
        out = parse_availability(html, AvailabilityRules(), FilterConfig())
        self.assertEqual(out.status, StockStatus.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
