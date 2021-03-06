import sys

import boto3

from src.helper import Helper


class ELBCleanup:
    def __init__(self, logging, whitelist, settings, execution_log, region):
        self.logging = logging
        self.whitelist = whitelist
        self.settings = settings
        self.execution_log = execution_log
        self.region = region

        self._client_elb = None
        self._dry_run = self.settings.get("general", {}).get("dry_run", True)

    @property
    def client_elb(self):
        if not self._client_elb:
            self._client_elb = boto3.client("elbv2", region_name=self.region)
        return self._client_elb

    def run(self):
        self.load_balancers()

    def load_balancers(self):
        """
        Deletes ELB Load Balancers.
        """

        self.logging.debug("Started cleanup of ELB Load Balancers.")

        clean = (
            self.settings.get("services", {})
            .get("elb", {})
            .get("load_balancer", {})
            .get("clean", False)
        )
        if clean:
            try:
                resources = self.client_elb.describe_load_balancers().get(
                    "LoadBalancers"
                )
            except:
                self.logging.error("Could not list all ELB Load Balancers.")
                self.logging.error(sys.exc_info()[1])
                return False

            ttl_days = (
                self.settings.get("services", {})
                .get("elb", {})
                .get("load_balancer", {})
                .get("ttl", 7)
            )

            for resource in resources:
                resource_id = resource.get("LoadBalancerName")
                resource_arn = resource.get("LoadBalancerArn")
                resource_date = resource.get("CreatedTime")
                resource_action = None

                describe_tags = self.client_elb.describe_tags(ResourceArns=[resource_arn])
                resource_tags = describe_tags.get('TagDescriptions')[0].get('Tags')

                if resource_tags:
                    Helper.parse_tags(resource_tags, "elb:load_balancer:" + resource_id, self.region)
                self.whitelist = Helper.get_whitelist()

                if resource_id not in self.whitelist.get("elb", {}).get(
                    "load_balancer", []
                ):
                    delta = Helper.get_day_delta(resource_date)

                    if delta.days > ttl_days:
                        try:
                            if not self._dry_run:
                                self.client_elb.modify_load_balancer_attributes(
                                    LoadBalancerArn=resource_arn,
                                    Attributes=[
                                        {
                                            "Key": "deletion_protection.enabled",
                                            "Value": "false",
                                        },
                                    ],
                                )
                        except:
                            self.logging.error(
                                f"Could not disable Delete Protection for ELB Load Balancer '{resource_id}'."
                            )
                            self.logging.error(sys.exc_info()[1])
                            resource_action = "ERROR"
                        else:
                            try:
                                if not self._dry_run:
                                    self.client_elb.delete_load_balancer(
                                        LoadBalancerArn=resource_arn
                                    )
                            except:
                                self.logging.error(
                                    f"Could not delete ELB Load Balancer '{resource_id}'."
                                )
                                self.logging.error(sys.exc_info()[1])
                                resource_action = "ERROR"
                            else:
                                self.logging.info(
                                    f"ELB Load Balancer '{resource_id}' was created {delta.days} days ago "
                                    "and has been deleted."
                                )
                                resource_action = "DELETE"
                    else:
                        self.logging.debug(
                            f"ELB Load Balancer '{resource_id}' was created {delta.days} days ago "
                            "(less than TTL setting) and has not been deleted."
                        )
                        resource_action = "SKIP - TTL"
                else:
                    self.logging.debug(
                        f"ELB Load Balancer '{resource_id}' has been whitelisted and has not been deleted."
                    )
                    resource_action = "SKIP - WHITELIST"

                Helper.record_execution_log_action(
                    self.execution_log,
                    self.region,
                    "ELB",
                    "Load Balancer",
                    resource_id,
                    resource_action,
                )

            self.logging.debug("Finished cleanup of ELB Load Balancers.")
            return True
        else:
            self.logging.info("Skipping cleanup of ELB Load Balancers.")
            return True
