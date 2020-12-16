import datetime
import dateutil.parser
import boto3
import os
from botocore.exceptions import ClientError
from dynamodb_json import json_util as dynamodb_json

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
        if any(tag_list.get("Key") in "ExpiryDate" for tag_list in tags):
            if any(tag_list.get("Key") in "Creator" for tag_list in tags):
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
                            print(f"Could not parse date on resource: {resource_id}. Error: {e}")
                    if tag["Key"] == "Creator":
                        response["creator"] = tag["Value"]
                    if tag["Key"] == "Name":
                        response["name"] = tag["Value"]

                if {"date", "creator"} <= response.keys():
                    Helper.insert_whitelist(response, resource_id)

    @staticmethod
    def insert_whitelist(parsed_tags, resource_id):
        try:
            comment = ""

            if "name" in parsed_tags:
                comment = f"Name: {parsed_tags['name']}"

            boto3.client("dynamodb").put_item(
                TableName=os.environ.get("WHITELISTTABLE"),
                Item={
                    "resource_id": {"S": resource_id},
                    "expiration": {"N": parsed_tags["date"]},
                    "owner": {"S": parsed_tags["creator"]},
                    "comment": {"S": comment},
                },
            )
            return True
        except ClientError as e:
            print(f"Error inserting record into whitelist. ({e})")

    @staticmethod
    def get_whitelist():
        whitelist = {}
        try:
            for record in boto3.client("dynamodb").scan(
                TableName=os.environ.get("WHITELISTTABLE")
            )["Items"]:
                record_json = dynamodb_json.loads(record, True)
                parsed_resource_id = Helper.parse_resource_id(
                    record_json.get("resource_id")
                )

                whitelist.setdefault(parsed_resource_id.get("service"), {}).setdefault(
                    parsed_resource_id.get("resource_type"), set()
                ).add(parsed_resource_id.get("resource"))
        except Exception as e:
            print(f"Could not read DynamoDB table: {os.environ.get('WHITELISTTABLE')}")
            print(f"Error: {e}")
        return whitelist
