import os
import json
import time
import sys
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"thousandeyes_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("ThousandEyes")

TE_API_TOKEN = os.getenv("TE_API_TOKEN")
TEST_NAME = os.getenv("TEST_NAME")
TARGET = os.getenv("TARGET")

if not all([TE_API_TOKEN, TEST_NAME, TARGET]):
    logger.error("Missing required environment variables. Please check your .env file.")
    sys.exit(1)

BASE_URL = "https://api.thousandeyes.com/v7"
HEADERS = {
    "Authorization": f"Bearer {TE_API_TOKEN}",
    "Content-Type": "application/json",
}

session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)


def api_request(method: str, endpoint: str, json_data=None, params=None):
    url = f"{BASE_URL}/{endpoint}"

    try:
        response = None
        for attempt in range(retry_strategy.total + 1):
            try:
                if method.lower() == "get":
                    response = session.get(
                        url, headers=HEADERS, params=params, timeout=30
                    )
                elif method.lower() == "post":
                    response = session.post(
                        url, headers=HEADERS, json=json_data, timeout=30
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        f"Rate limit exceeded. Waiting for {retry_after} seconds."
                    )
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                if attempt < retry_strategy.total:
                    sleep_time = retry_strategy.backoff_factor * (2**attempt)
                    logger.warning(
                        f"Request failed (Attempt {attempt + 1}/{retry_strategy.total + 1}): {e}. Retrying in {sleep_time:.2f} seconds."
                    )
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Max retries reached for {method} {url}. Giving up.")
                    raise Exception(f"Request failed after multiple retries: {str(e)}")

        raise Exception(f"Request failed after multiple retries: {method} {url}")

    except Exception as e:
        logger.error(f"API request failed: {str(e)}")
        raise Exception(f"API request failed: {str(e)}")


def get_first_agent_id() -> Optional[int]:
    logger.info("Attempting to fetch the first agent ID.")
    try:
        response = api_request("get", "agents")
        agents = response.json().get("agents", [])

        if agents:
            agent = agents[0]
            logger.info(
                f"Successfully fetched agent: {agent['agentName']} (ID: {agent['agentId']})"
            )
            return int(agent["agentId"])
        else:
            logger.warning("No agents found in your account.")

    except Exception as e:
        logger.error(f"Failed to fetch agents: {str(e)}")
        return None


def find_existing_test_id(test_name: str) -> Optional[int]:
    logger.info(f"Attempting to find existing test with name: '{test_name}'")
    try:
        response = api_request("get", "tests/http-server")

        for test in response.json().get("tests", []):
            if test.get("testName") == test_name:
                test_id = int(test["testId"])
                logger.info(f"Found existing test '{test_name}' with ID: {test_id}")
                return test_id

        logger.info(f"No existing test named '{test_name}' found.")
        return None

    except Exception as e:
        logger.error(f"Failed to retrieve tests: {str(e)}")
        return None


def create_test(
    test_name: str, target: str, agent_id: int, interval: int = 3600
) -> Optional[int]:
    logger.info(f"Attempting to create a new test: '{test_name}'")
    payload = {
        "testName": test_name,
        "type": "agent-to-server",
        "url": target,
        "interval": interval,
        "protocol": "ICMP",
        "enabled": True,
        "agents": [{"agentId": agent_id}],
    }

    try:
        response = api_request("post", "tests/http-server", json_data=payload)
        test_id = response.json().get("testId")
        if test_id:
            logger.info(f"Created test '{test_name}' (ID: {test_id})")
            return int(test_id)
        logger.error("Test creation succeeded but no test ID returned")
        return None

    except Exception as e:
        logger.error(f"Error creating test: {str(e)}")
        return None


def get_test_results(test_id: int) -> Optional[Dict[str, Any]]:
    logger.info(f"Attempting to fetch test results for test ID: {test_id}")
    try:
        response = api_request("get", f"test-results/{test_id}/http-server")
        logger.info(f"Fetched test results for test ID {test_id}")
        return response.json()

    except Exception as e:
        if "Resource not found" in str(e):
            logger.warning(f"No test results found for test ID {test_id}")
        else:
            logger.error(f"Failed to retrieve test results: {str(e)}")
        return None


def analyze_results(results: Dict[str, Any]) -> None:
    logger.info("Analyzing test results.")
    entries = results.get("results", [])
    if not entries:
        logger.warning("No HTTP Server test results available for analysis.")
        return

    try:
        result = entries[0]
        output = f"""
========== HTTP SERVER TEST RESULTS ==========
 Test Name     : {TEST_NAME}
 Agent         : {result['agent']['agentName']} (ID: {result['agent']['agentId']})
 Test Date     : {result['date']}
 Target URL    : {TARGET}
----------------------------------------------
 Response Code : {result.get('responseCode')}
 Response Time : {result.get('responseTime')} ms
 Redirect Time : {result.get('redirectTime')} ms
 DNS Time      : {result.get('dnsTime')} ms
 SSL Time      : {result.get('sslTime')} ms
 Connect Time  : {result.get('connectTime')} ms
 Wait Time     : {result.get('waitTime')} ms
 Receive Time  : {result.get('receiveTime')} ms
 Total Time    : {result.get('totalTime')} ms
 Throughput    : {result.get('throughput')} bytes/sec
 Wire Size     : {result.get('wireSize')} bytes
 Server IP     : {result.get('serverIp')}
 SSL Cipher    : {result.get('sslCipher')}
 SSL Version   : {result.get('sslVersion')}
 Health Score  : {result.get('healthScore', 0):.4f}
==============================================
"""
        print(output)
        logger.info(output)
    except KeyError as e:
        logger.error(f"Missing expected key in test results: {e}")
    except IndexError:
        logger.error("Test results list is empty.")


def save_report(test_name: str, results: Dict[str, Any]) -> None:
    filename = f"{test_name}_report.json"
    try:
        with open(filename, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Report saved to: {filename}")
    except IOError as e:
        logger.error(f"Failed to save report: {str(e)}")
    except TypeError as e:
        logger.error(f"Error serializing results to JSON: {e}")


def main():
    logger.info("Starting ThousandEyes test automation...")

    agent_id = get_first_agent_id()
    if agent_id is None:
        logger.error("No valid agent available. Exiting.")
        sys.exit(1)

    test_id = find_existing_test_id(TEST_NAME)
    is_new = False

    if test_id is None:
        logger.info(
            f"No existing test named '{TEST_NAME}' found. Creating a new test..."
        )
        test_id = create_test(TEST_NAME, TARGET, agent_id)
        is_new = True

    if test_id is None:
        logger.error("Test creation failed. Exiting.")
        sys.exit(1)

    if is_new:
        logger.info(
            "Waiting 90 seconds for the first test result to become available..."
        )
        time.sleep(90)

    results = get_test_results(test_id)
    if results:
        analyze_results(results)
        save_report(TEST_NAME, results)
    else:
        logger.error("No results returned. Exiting.")
        sys.exit(1)


if __name__ == "__main__":
    main()
