import os
import json
import time
import sys
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import requests
from dotenv import load_dotenv

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

BASE_URL = "https://api.thousandeyes.com/v7"
HEADERS = {
    "Authorization": f"Bearer {TE_API_TOKEN}",
    "Content-Type": "application/json",
}


def get_first_agent_id() -> Optional[int]:
    logger.info("Attempting to fetch the first agent ID.")
    url = f"{BASE_URL}/agents"
    response = requests.get(url, headers=HEADERS)

    if response.ok:
        agents = response.json().get("agents", [])
        if agents:
            agent = agents[0]
            logger.info(
                f"Successfully fetched agent: {agent['agentName']} (ID: {agent['agentId']})"
            )
            return int(agent["agentId"])
        else:
            logger.warning("No agents found in your account.")
    else:
        logger.error(
            f"Failed to fetch agents: {response.status_code} - {response.text}"
        )
    return None


def find_existing_test_id(test_name: str) -> Optional[int]:
    logger.info(f"Attempting to find existing test with name: '{test_name}'")
    url = f"{BASE_URL}/tests/http-server"
    response = requests.get(url, headers=HEADERS)

    if response.ok:
        for test in response.json().get("tests", []):
            if test.get("testName") == test_name:
                logger.info(f"Found existing test ID: {test['testId']}")
                return int(test["testId"])
        logger.info(f"No existing test named '{test_name}' found.")
    else:
        logger.error(
            f"Failed to retrieve tests: {response.status_code} - {response.text}"
        )
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

    url = f"{BASE_URL}/tests/http-server"
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code == 201:
        test_id = response.json().get("testId")
        logger.info(f"Successfully created test '{test_name}' (ID: {test_id})")
        return int(test_id)
    else:
        logger.error(f"Error creating test: {response.status_code} - {response.text}")
        return None


def get_test_results(test_id: int) -> Optional[Dict[str, Any]]:
    logger.info(f"Attempting to fetch test results for test ID: {test_id}")
    url = f"{BASE_URL}/test-results/{test_id}/http-server"
    response = requests.get(url, headers=HEADERS)

    if response.ok:
        logger.info(f"Successfully fetched test results for test ID {test_id}")
        return response.json()
    else:
        logger.error(
            f"Failed to retrieve test results: {response.status_code} - {response.text}"
        )
        return None


def analyze_results(results: Dict[str, Any]) -> None:
    logger.info("Analyzing test results.")
    entries = results.get("results", [])
    if not entries:
        logger.warning("No HTTP Server test results available for analysis.")
        return

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
    logger.info(output)


def save_report(test_name: str, results: Dict[str, Any]) -> None:
    filename = f"{test_name}_report.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Report saved to: {filename}")


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
