import pytest

pytest.register_assert_rewrite("tests.utils.bedrock.openai")
pytest.register_assert_rewrite("tests.utils.bedrock.json")
pytest.register_assert_rewrite("tests.utils.bedrock.exception")
