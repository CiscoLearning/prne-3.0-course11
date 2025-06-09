import unittest
from unittest.mock import patch, MagicMock, mock_open

from te_tests import (
    get_first_agent_id,
    find_existing_test_id,
    create_test,
    get_test_results,
    analyze_results,
    save_report,
)


class TestData:
    AGENT_DATA = {
        "agents": [{"agentId": "3", "agentName": "Singapore", "countryId": "SG"}]
    }

    TESTS_DATA = {
        "tests": [
            {
                "interval": 3600,
                "testId": "6969142",
                "testName": "Cisco.com Test",
                "createdBy": "Student (student@cisco.com)",
                "createdDate": "2025-04-10T13:42:26Z",
                "type": "http-server",
                "enabled": True,
                "url": "https://cisco.com",
            }
        ]
    }

    TEST_RESULTS = {
        "test": {
            "testId": "6969142",
            "testName": "Cisco.com Test",
            "type": "http-server",
            "url": "https://cisco.com",
        },
        "results": [
            {
                "agent": {"agentId": "3", "agentName": "Singapore", "countryId": "SG"},
                "date": "2025-04-10T15:20:39Z",
                "responseCode": 200,
                "dnsTime": 90,
                "sslTime": 8,
                "connectTime": 4,
                "waitTime": 23,
                "receiveTime": 1,
                "responseTime": 125,
                "serverIp": "23.54.57.29",
                "healthScore": 0.99988276,
            }
        ],
    }

    ENV = {
        "TE_API_TOKEN": "mock-token-123",
        "TEST_NAME": "Cisco.com Test",
        "TARGET": "https://cisco.com",
    }


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch("os.getenv")
        self.mock_getenv = self.env_patcher.start()
        self.mock_getenv.side_effect = lambda key: TestData.ENV.get(key)

        self.success_response = MagicMock()
        self.success_response.ok = True

        self.error_response = MagicMock()
        self.error_response.ok = False
        self.error_response.status_code = 500
        self.error_response.text = "API Error"

    def tearDown(self):
        self.env_patcher.stop()


class TestGetFirstAgentId(BaseTestCase):
    @patch("te_tests.api_request")
    def test_successful_agent_retrieval(self, mock_api_request):
        mock_api_request.return_value = self.success_response
        self.success_response.json.return_value = TestData.AGENT_DATA
        agent_id = get_first_agent_id()
        self.assertEqual(agent_id, 3)
        mock_api_request.assert_called_once_with("get", "agents")

    @patch("te_tests.api_request")
    def test_no_agents_found(self, mock_api_request):
        mock_api_request.return_value = self.success_response
        self.success_response.json.return_value = {"agents": []}
        agent_id = get_first_agent_id()
        self.assertIsNone(agent_id)
        mock_api_request.assert_called_once_with("get", "agents")

    @patch("te_tests.api_request")
    def test_api_error(self, mock_api_request):
        mock_api_request.side_effect = Exception("API Error")
        agent_id = get_first_agent_id()
        self.assertIsNone(agent_id)
        mock_api_request.assert_called_once_with("get", "agents")


class TestFindExistingTestId(BaseTestCase):
    @patch("te_tests.api_request")
    def test_find_existing_test(self, mock_api_request):
        mock_api_request.return_value = self.success_response
        self.success_response.json.return_value = TestData.TESTS_DATA
        test_id = find_existing_test_id("Cisco.com Test")
        self.assertEqual(test_id, 6969142)
        mock_api_request.assert_called_once_with("get", "tests/http-server")

    @patch("te_tests.api_request")
    def test_test_not_found(self, mock_api_request):
        mock_api_request.return_value = self.success_response
        self.success_response.json.return_value = {
            "tests": [{"testId": "7890123", "testName": "Different Test"}]
        }
        test_id = find_existing_test_id("Cisco.com Test")
        self.assertIsNone(test_id)
        mock_api_request.assert_called_once_with("get", "tests/http-server")

    @patch("te_tests.api_request")
    def test_api_error(self, mock_api_request):
        mock_api_request.side_effect = Exception("API Error")
        test_id = find_existing_test_id("Cisco.com Test")
        self.assertIsNone(test_id)
        mock_api_request.assert_called_once_with("get", "tests/http-server")


class TestCreateTest(BaseTestCase):
    @patch("te_tests.api_request")
    def test_successful_test_creation(self, mock_api_request):
        mock_api_request.return_value = self.success_response
        self.success_response.status_code = 201
        self.success_response.json.return_value = {"testId": "6969142"}
        test_id = create_test("Cisco.com Test", "https://cisco.com", 3)
        self.assertEqual(test_id, 6969142)
        expected_payload = {
            "testName": "Cisco.com Test",
            "type": "agent-to-server",
            "url": "https://cisco.com",
            "interval": 3600,
            "protocol": "ICMP",
            "enabled": True,
            "agents": [{"agentId": 3}],
        }
        mock_api_request.assert_called_once_with(
            "post", "tests/http-server", json_data=expected_payload
        )

    @patch("te_tests.api_request")
    def test_api_error(self, mock_api_request):
        mock_api_request.side_effect = Exception("API Error")
        test_id = create_test("Cisco.com Test", "https://cisco.com", 3)
        self.assertIsNone(test_id)
        expected_payload = {
            "testName": "Cisco.com Test",
            "type": "agent-to-server",
            "url": "https://cisco.com",
            "interval": 3600,
            "protocol": "ICMP",
            "enabled": True,
            "agents": [{"agentId": 3}],
        }
        mock_api_request.assert_called_once_with(
            "post", "tests/http-server", json_data=expected_payload
        )


class TestGetTestResults(BaseTestCase):
    @patch("te_tests.api_request")
    def test_successful_results_retrieval(self, mock_api_request):
        mock_api_request.return_value = self.success_response
        self.success_response.json.return_value = TestData.TEST_RESULTS
        results = get_test_results(6969142)
        self.assertEqual(results, TestData.TEST_RESULTS)
        mock_api_request.assert_called_once_with(
            "get", "test-results/6969142/http-server"
        )

    @patch("te_tests.api_request")
    def test_api_error(self, mock_api_request):
        mock_api_request.side_effect = Exception("API Error")
        results = get_test_results(9999999)
        self.assertIsNone(results)
        mock_api_request.assert_called_once_with(
            "get", "test-results/9999999/http-server"
        )


class TestAnalyzeResults(BaseTestCase):
    @patch("te_tests.logger")
    def test_analyze_valid_results(self, mock_logger):
        analyze_results(TestData.TEST_RESULTS)
        output = mock_logger.info.call_args[0][0]
        expected_elements = [
            "HTTP SERVER TEST RESULTS",
            "Singapore",
            "Response Code : 200",
            "Response Time : 125 ms",
            "DNS Time      : 90 ms",
            "Server IP     : 23.54.57.29",
        ]
        for element in expected_elements:
            self.assertIn(element, output)
        self.assertRegex(output, r"Health Score\s+:\s+0\.9999")

    @patch("te_tests.logger")
    def test_analyze_empty_results(self, mock_logger):
        analyze_results({"results": []})
        mock_logger.warning.assert_called_once_with(
            "No HTTP Server test results available for analysis."
        )


class TestSaveReport(BaseTestCase):
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    @patch("te_tests.logger")
    def test_save_report(self, mock_logger, mock_json_dump, mock_file_open):
        save_report("Cisco.com Test", TestData.TEST_RESULTS)
        mock_file_open.assert_called_once_with("Cisco.com Test_report.json", "w")
        mock_json_dump.assert_called_once()
        args, kwargs = mock_json_dump.call_args
        self.assertEqual(args[0], TestData.TEST_RESULTS)
        self.assertEqual(kwargs["indent"], 2)
        mock_logger.info.assert_called_once_with(
            "Report saved to: Cisco.com Test_report.json"
        )


if __name__ == "__main__":
    unittest.main()
