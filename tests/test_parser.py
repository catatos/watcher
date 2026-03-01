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

    def test_ignores_script_and_style_content(self):
        html = (
            "<html>"
            "<head><style>.soldout{content:'sold out'}</style></head>"
            "<body><script>var msg='sold out';</script><button>Add to Cart</button></body>"
            "</html>"
        )
        out = parse_availability(html, AvailabilityRules(), FilterConfig())
        self.assertEqual(out.status, StockStatus.IN_STOCK)

    def test_structured_in_stock_precedence(self):
        html = (
            "<html><head>"
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Product",'
            '"offers":{"@type":"Offer","availability":"https://schema.org/InStock"}}'
            "</script></head>"
            "<body>Notify me when available</body></html>"
        )
        out = parse_availability(html, AvailabilityRules(), FilterConfig())
        self.assertEqual(out.status, StockStatus.IN_STOCK)

    def test_structured_out_of_stock_precedence(self):
        html = (
            "<html><head>"
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Product",'
            '"offers":{"@type":"Offer","availability":"https://schema.org/OutOfStock"}}'
            "</script></head>"
            "<body><button>Add to Cart</button></body></html>"
        )
        out = parse_availability(html, AvailabilityRules(), FilterConfig())
        self.assertEqual(out.status, StockStatus.OUT_OF_STOCK)

    def test_structured_conflict_falls_back_to_keywords(self):
        html = (
            "<html><head>"
            '<script type="application/ld+json">'
            '[{"@context":"https://schema.org","@type":"Product","offers":{"availability":"https://schema.org/InStock"}},'
            '{"@context":"https://schema.org","@type":"Product","offers":{"availability":"https://schema.org/OutOfStock"}}]'
            "</script></head>"
            "<body>sold out</body></html>"
        )
        out = parse_availability(html, AvailabilityRules(), FilterConfig())
        self.assertEqual(out.status, StockStatus.OUT_OF_STOCK)


if __name__ == "__main__":
    unittest.main()
