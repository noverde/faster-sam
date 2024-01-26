from http import HTTPStatus
import unittest
from unittest.mock import patch

from requests import Response

from faster_sam import web_identity_providers


class TestLambdaClient(unittest.TestCase):
    def setUp(self) -> None:
        self.patch_requests = patch("requests.get")
        self.mock_requests = self.patch_requests.start()

    def tearDown(self) -> None:
        self.patch_requests.stop()

    def test_get_token(self):
        token = "jKhV9WnL4qrMzY47wWuOJdcE6FDtSrS62g0dJenrO1o"

        mock_response = Response()
        mock_response.status_code = HTTPStatus.OK.value
        mock_response._content = token.encode()

        self.mock_requests.return_value = mock_response

        web_identity_provider = web_identity_providers.factory("gcp")
        web_identity_token = web_identity_provider.get_token()

        self.assertEqual(web_identity_token, token)

    def test_get_token_fail(self):
        mock_response = Response()
        mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value

        self.mock_requests.return_value = mock_response

        web_identity_provider = web_identity_providers.factory("gcp")
        web_identity_token = web_identity_provider.get_token()

        self.assertIsNone(web_identity_token)
