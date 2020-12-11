import datetime
import dateutil.parser
import boto3
import os
from botocore.exceptions import ClientError


class Helper:
    def __init__(self):
        pass

    @staticmethod
    def convert_to_datetime(date):
        return dateutil.parser.isoparse(str(date)).replace(tzinfo=None)

    @staticmethod
    def get_day_delta(resource_date):
        from_datetime = Helper.convert_to_datetime(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        if resource_date is not None:
            to_datetime = Helper.convert_to_datetime(resource_date)
            return from_datetime - to_datetime
        else:
            return from_datetime - from_datetime

    @staticmethod
    def parse_resource_id(resource_id):
        elements = resource_id.split(":", 2)

        result = {
            "service": elements[0],
            "resource_type": elements[1],
            "resource": elements[2],
        }

        return result

    @staticmethod
    def record_execution_log_action(
        execution_log, region, service, resource, resource_id, resource_action
    ):
        execution_log.get("AWS").setdefault(region, {}).setdefault(
            service, {}
        ).setdefault(resource, []).append(
            {
                "id": resource_id,
                "action": resource_action,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    @staticmethod
    def parse_tags(tags, resource_id):
        # tags = [{'Key': 'ExpiryDate', 'Value': '2500-03-11'}, {'Key': 'Creator', 'Value': 'John'}]
        # Check if the tags both contain Creator and ExpiryDate
        if any(x["Key"] == "ExpiryDate" for x in tags):
            if any(x["Key"] == "Creator" for x in tags):
                response = {}

                for tag in tags:
                    if tag["Key"] == "ExpiryDate":
                        try:
                            response["date"] = str(
                                datetime.datetime.strptime(
                                    tag["Value"], "%Y-%m-%d"
                                ).timestamp()
                            )
                        except Exception as e:
                            print(f"Could not parse date. Error: {e}")
                    if tag["Key"] == "Creator":
                        response["creator"] = tag["Value"]

                if {"date", "creator"} <= response.keys():
                    Helper.insert_whitelist(
                        response["date"], response["creator"], resource_id
                    )

    @staticmethod
    def insert_whitelist(date, creator, resource_id):
        try:
            boto3.client("dynamodb").put_item(
                TableName=os.environ.get("WHITELISTTABLE"),
                Item={
                    "resource_id": {"S": resource_id},
                    "expiration": {"N": date},
                    "owner": {"S": creator},
                    "comment": {"S": ""},
                },
            )
            return True
        except ClientError as e:
            print(f"Error inserting record into whitelist. ({e})")
