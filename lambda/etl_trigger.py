"""
AWS Lambda function to trigger ETL via App Runner API endpoint.

Deploy this to Lambda and schedule with EventBridge for periodic ETL runs.
"""

import json
import os
import urllib.request
from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Trigger ETL via API endpoint.

    Environment Variables:
        API_URL: The App Runner service URL (e.g., https://xxx.awsapprunner.com)
        ETL_TIMEOUT: Request timeout in seconds (default: 300)

    EventBridge Rule Example:
        Schedule: cron(0/5 * * * ? *)  # Every 5 minutes
    """
    api_url = os.environ.get("API_URL")
    if not api_url:
        return {"statusCode": 500, "body": json.dumps({"error": "API_URL environment variable not set"})}

    timeout = int(os.environ.get("ETL_TIMEOUT", "300"))

    # Trigger ETL for all sources
    endpoint = f"{api_url.rstrip('/')}/etl/run-all"

    request = urllib.request.Request(endpoint, method="POST", headers={"Content-Type": "application/json", "User-Agent": "KasparroETLTrigger/1.0"})

    try:
        print(f"Triggering ETL at: {endpoint}")

        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))

            print(f"ETL completed successfully: {json.dumps(result, indent=2)}")

            return {"statusCode": 200, "body": json.dumps({"success": True, "etl_result": result})}

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        print(f"ETL request failed with HTTP {e.code}: {error_body}")

        return {"statusCode": e.code, "body": json.dumps({"success": False, "error": f"HTTP {e.code}: {error_body}"})}

    except urllib.error.URLError as e:
        print(f"ETL request failed: {str(e)}")

        return {"statusCode": 500, "body": json.dumps({"success": False, "error": f"Connection error: {str(e)}"})}

    except Exception as e:
        print(f"Unexpected error: {str(e)}")

        return {"statusCode": 500, "body": json.dumps({"success": False, "error": str(e)})}


# For local testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        os.environ["API_URL"] = sys.argv[1]

    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))
