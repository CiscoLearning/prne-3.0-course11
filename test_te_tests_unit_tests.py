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
    @patch("requests.get")
    def test_successful_agent_retrieval(self, mock_get):
        self.success_response.json.return_value = TestData.AGENT_DATA
        mock_get.return_value = self.success_response
        agent_id = get_first_agent_id()
        self.assertEqual(agent_id, 3)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_no_agents_found(self, mock_get):
        self.success_response.json.return_value = {"agents": []}
        mock_get.return_value = self.success_response
        agent_id = get_first_agent_id()
        self.assertIsNone(agent_id)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_api_error(self, mock_get):
        mock_get.return_value = self.error_response
        agent_id = get_first_agent_id()
        self.assertIsNone(agent_id)
        mock_get.assert_called_once()


class TestFindExistingTestId(BaseTestCase):
    @patch("requests.get")
    def test_find_existing_test(self, mock_get):
        self.success_response.json.return_value = TestData.TESTS_DATA
        mock_get.return_value = self.success_response
        test_id = find_existing_test_id("Cisco.com Test")
        self.assertEqual(test_id, 6969142)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_test_not_found(self, mock_get):
        self.success_response.json.return_value = {
            "tests": [{"testId": "7890123", "testName": "Different Test"}]
        }
        mock_get.return_value = self.success_response
        test_id = find_existing_test_id("Cisco.com Test")
        self.assertIsNone(test_id)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_api_error(self, mock_get):
        mock_get.return_value = self.error_response
        test_id = find_existing_test_id("Cisco.com Test")
        self.assertIsNone(test_id)
        mock_get.assert_called_once()


class TestCreateTest(BaseTestCase):
    @patch("requests.post")
    def test_successful_test_creation(self, mock_post):
        self.success_response.status_code = 201
        self.success_response.json.return_value = {"testId": "6969142"}
        mock_post.return_value = self.success_response
        test_id = create_test("Cisco.com Test", "https://cisco.com", 3)
        self.assertEqual(test_id, 6969142)
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_api_error(self, mock_post):
        self.error_response.status_code = 400
        mock_post.return_value = self.error_response
        test_id = create_test("Cisco.com Test", "https://cisco.com", 3)
        self.assertIsNone(test_id)
        mock_post.assert_called_once()


class TestGetTestResults(BaseTestCase):
    @patch("requests.get")
    def test_successful_results_retrieval(self, mock_get):
        self.success_response.json.return_value = TestData.TEST_RESULTS
        mock_get.return_value = self.success_response
        results = get_test_results(6969142)
        self.assertEqual(results, TestData.TEST_RESULTS)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_api_error(self, mock_get):
        self.error_response.status_code = 404
        mock_get.return_value = self.error_response
        results = get_test_results(9999999)
        self.assertIsNone(results)
        mock_get.assert_called_once()


class TestAnalyzeResults(BaseTestCase):
    @patch("sys.stdout", new_callable=MagicMock)
    def test_analyze_valid_results(self, mock_stdout):
        analyze_results(TestData.TEST_RESULTS)
        output = "".join([call[0][0] for call in mock_stdout.write.call_args_list])
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

    @patch("sys.stdout", new_callable=MagicMock)
    def test_analyze_empty_results(self, mock_stdout):
        analyze_results({"results": []})
        output = "".join([call[0][0] for call in mock_stdout.write.call_args_list])
        self.assertIn("No HTTP Server test results available.", output)


class TestSaveReport(BaseTestCase):
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_save_report(self, mock_json_dump, mock_file_open):
        save_report("Cisco.com Test", TestData.TEST_RESULTS)
        mock_file_open.assert_called_once_with("Cisco.com Test_report.json", "w")
        mock_json_dump.assert_called_once()
        args, kwargs = mock_json_dump.call_args
        self.assertEqual(args[0], TestData.TEST_RESULTS)
        self.assertEqual(kwargs["indent"], 2)


if __name__ == "__main__":
    unittest.main()
