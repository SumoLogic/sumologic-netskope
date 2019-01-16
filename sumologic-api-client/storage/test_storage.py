from factory import ProviderFactory
import unittest


class TestingStorage(unittest.TestCase):

    def setUp(self):
        self.aws_cli = ProviderFactory.get_provider("aws", region_name="us-east-1")
        self.op_cli = ProviderFactory.get_provider("onprem")
        key_type = "S"
        if self._testMethodName == "test_int_keys":
            key_type = "N"

        self.aws_kvstore = self.aws_cli.get_storage("keyvalue", name='kvstore', key_type=key_type, force_create=True)
        self.op_kvstore = self.op_cli.get_storage("keyvalue", name='kvstore', force=True)

    def tearDown(self):
        self.aws_kvstore.destroy()
        self.op_kvstore.destroy()

    def test_string_values(self):
        key = "abckey"
        value = "abvvalue"
        self.run_checks(key, value)

    def test_object_values(self):
        key = "abckey"
        value = {"name": "John", "age": 31, "city": ["New York", "Detroit", {"a": 40}], "hobbies": {"cricket": True, "football": False}}
        self.run_checks(key, value)

    def test_int_keys(self):
        key = 1
        value = {"msg": {"value": [{"morning": "Good morning"}, {"night": "Good night"}]}}
        self.run_checks(key, value)

    def run_checks(self, key, value):
        self.aws_kvstore.set(key, value)
        self.op_kvstore.set(key, value)
        self.assertTrue(self.op_kvstore.get(key) == value)
        self.assertTrue(self.aws_kvstore.get(key) == value)
        self.assertTrue(self.op_kvstore.has_key(key) == True)
        self.assertTrue(self.aws_kvstore.has_key(key) == True)
        self.op_kvstore.delete(key)
        self.aws_kvstore.delete(key)
        self.assertTrue(self.op_kvstore.has_key(key) == False)
        self.assertTrue(self.aws_kvstore.has_key(key) == False)


if __name__ == "__main__":
    unittest.main()
