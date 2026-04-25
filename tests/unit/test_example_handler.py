"""
tests/unit/test_example_handler.py — Test Pattern Reference

Demonstrates the test naming convention, fixture usage, and assertion patterns.

Naming convention:
    test_<module>__<method>__<scenario>()

Fixture usage:
    - mock_algorithm: Pre-configured QCAlgorithm stub
    - mock_indicators: Factory for indicator dicts
    - mock_option_contract: Factory for OptionContract stubs
"""

from handlers._example_handler import ExampleHandler


class TestExampleHandler:
    """Tests for ExampleHandler."""

    def test_example_handler__example_method__returns_dict(self, mock_algorithm):
        """Handler method returns expected dict structure."""
        handler = ExampleHandler(mock_algorithm)
        result = handler.example_method("AAPL", 150.0)

        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"
        assert result["price"] == 150.0
        assert result["passed"] is True

    def test_example_handler__example_method__zero_price_fails(self, mock_algorithm):
        """Zero price should not pass validation."""
        handler = ExampleHandler(mock_algorithm)
        result = handler.example_method("AAPL", 0.0)

        assert result["passed"] is False
