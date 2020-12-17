import sys

import boto3

from src.helper import Helper


class LambdaCleanup:
    def __init__(self, logging, whitelist, settings, execution_log, region):
        self.logging = logging
        self.whitelist = whitelist
        self.settings = settings
        self.execution_log = execution_log
        self.region = region

        self._client_lambda = None
        self._dry_run = self.settings.get("general", {}).get("dry_run", True)

    @property
    def client_lambda(self):
        if not self._client_lambda:
            self._client_lambda = boto3.client("lambda", region_name=self.region)
        return self._client_lambda

    def run(self):
        self.functions()

    def functions(self):
        """
        Deletes Lambda Functions.
        """

        self.logging.debug("Started cleanup of Lambda Functions.")

        clean = (
            self.settings.get("services", {})
            .get("lambda", {})
            .get("function", {})
            .get("clean", False)
        )
        if clean:
            try:
                resources = self.client_lambda.list_functions().get("Functions")
            except:
                self.logging.error("Could not list all Lambda Functions.")
                self.logging.error(sys.exc_info()[1])
                return False

            ttl_days = (
                self.settings.get("services", {})
                .get("lambda", {})
                .get("function", {})
                .get("ttl", 7)
            )

            for resource in resources:
                resource_id = resource.get("FunctionName")
                resource_date = resource.get("LastModified")
                resource_action = None

                resource_arn = resource.get("FunctionArn")
                tag_list = self.client_lambda.list_tags(Resource=resource_arn)
                resource_tags = tag_list.get("Tags")

                if resource_tags:
                    tag_list = []
                    if "ExpiryDate" in resource_tags:
                        tag_list.append({"Key": "ExpiryDate", "Value": resource_tags.get("ExpiryDate")})
                    if "Creator" in resource_tags:
                        tag_list.append({"Key": "Creator", "Value": resource_tags.get("Creator")})
                    tag_list.append({"Key": "Name", "Value": resource_id})
                    Helper.parse_tags(tag_list, "lambda:function:" + resource_id)
                self.whitelist = Helper.get_whitelist()

                if resource_id not in self.whitelist.get("lambda", {}).get(
                    "function", []
                ):
                    delta = Helper.get_day_delta(resource_date)

                    if delta.days > ttl_days:
                        try:
                            if not self._dry_run:
                                self.client_lambda.delete_function(
                                    FunctionName=resource_id
                                )
                        except:
                            self.logging.error(
                                f"Could not delete Lambda Function '{resource_id}'."
                            )
                            self.logging.error(sys.exc_info()[1])
                            resource_action = "ERROR"
                        else:
                            self.logging.info(
                                f"Lambda Function '{resource_id}' was last modified {delta.days} days ago "
                                "and has been deleted."
                            )
                            resource_action = "DELETE"
                    else:
                        self.logging.debug(
                            f"Lambda Function '{resource_id}' was last modified {delta.days} days ago "
                            "(less than TTL setting) and has not been deleted."
                        )
                        resource_action = "SKIP - TTL"
                else:
                    self.logging.debug(
                        f"Lambda Function '{resource_id}' has been whitelisted and has not been deleted."
                    )
                    resource_action = "SKIP - WHITELIST"

                Helper.record_execution_log_action(
                    self.execution_log,
                    self.region,
                    "Lambda",
                    "Function",
                    resource_id,
                    resource_action,
                )

            self.logging.debug("Finished cleanup of Lambda Functions.")
            return True
        else:
            self.logging.info("Skipping cleanup of Lambda Functions.")
            return True
