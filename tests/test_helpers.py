import unittest

from faster_sam import helpers


class TestHelpers(unittest.TestCase):
    def teste_empty_attributes(self):
        result = helpers.build_message_attributes({})
        self.assertEqual(result, {})

    def test_string_attributes(self):
        attributes = {"key1": "value1", "key2": "value2"}
        expected_result = {
            "key1": {"stringValue": "value1", "dataType": "String"},
            "key2": {"stringValue": "value2", "dataType": "String"},
        }
        result = helpers.build_message_attributes(attributes)
        self.assertEqual(result, expected_result)

    def test_number_attributes(self):
        attributes = {"key1": 123, "key2": 12.3}
        expected_result = {
            "key1": {"stringValue": "123", "dataType": "Number"},
            "key2": {"stringValue": "12.3", "dataType": "Number"},
        }
        result = helpers.build_message_attributes(attributes)
        self.assertEqual(result, expected_result)

    def test_bytes_attributes(self):
        attributes = {"key1": b"test_bytes"}
        expected_result = {"key1": {"BinaryValue": str(b"test_bytes"), "dataType": "Binary"}}
        result = helpers.build_message_attributes(attributes)
        self.assertEqual(result, expected_result)

    def test_multi_attributes(self):
        attributes = {"key1": 123, "key2": "value1"}
        expected_result = {
            "key1": {"stringValue": "123", "dataType": "Number"},
            "key2": {"stringValue": "value1", "dataType": "String"},
        }
        result = helpers.build_message_attributes(attributes)
        self.assertEqual(result, expected_result)

    def test_unsupported_type(self):
        attributes = {"key1": "value1", "key2": [1, 2, 3]}
        with self.assertRaises(TypeError):
            helpers.build_message_attributes(attributes)
