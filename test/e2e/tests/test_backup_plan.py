# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
# 	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the AWS Backup BackupPlan resource.
"""

import pytest
import time
import logging

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s
from acktest.k8s import condition
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_backup_resource
from e2e.replacement_values import REPLACEMENT_VALUES

BACKUP_VAULT_PLURAL = "backupvaults"
BACKUP_PLAN_PLURAL = "backupplans"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10


@service_marker
@pytest.mark.canary
class TestBackupPlan:
    def get_backup_plan(self, backup_client, plan_id: str) -> dict:
        """Get a backup plan by ID."""
        try:
            resp = backup_client.get_backup_plan(
                BackupPlanId=plan_id
            )
            return resp
        except backup_client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logging.debug(e)
            return None

    def get_backup_vault(self, backup_client, vault_name: str) -> dict:
        """Get a backup vault by name."""
        try:
            resp = backup_client.describe_backup_vault(
                BackupVaultName=vault_name
            )
            return resp
        except backup_client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logging.debug(e)
            return None

    def plan_exists(self, backup_client, plan_id: str) -> bool:
        """Check if a backup plan exists."""
        return self.get_backup_plan(backup_client, plan_id) is not None

    def vault_exists(self, backup_client, vault_name: str) -> bool:
        """Check if a backup vault exists."""
        return self.get_backup_vault(backup_client, vault_name) is not None

    def test_create_delete(self, backup_client):
        """Test basic create and delete operations for BackupPlan.
        
        This test creates a BackupVault first (required for the plan's rule),
        then creates a BackupPlan that references it.
        """
        vault_name = random_suffix_name("ack-test-vault", 24)
        plan_name = random_suffix_name("ack-test-plan", 24)

        # First, create a BackupVault for the plan to use
        vault_replacements = REPLACEMENT_VALUES.copy()
        vault_replacements["VAULT_NAME"] = vault_name

        vault_data = load_backup_resource(
            "backup_vault",
            additional_replacements=vault_replacements,
        )
        logging.debug(vault_data)

        vault_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_VAULT_PLURAL,
            vault_name, namespace="default",
        )
        k8s.create_custom_resource(vault_ref, vault_data)
        vault_cr = k8s.wait_resource_consumed_by_controller(vault_ref)

        assert vault_cr is not None
        assert k8s.get_resource_exists(vault_ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(vault_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)
        assert self.vault_exists(backup_client, vault_name)

        # Now create the BackupPlan
        plan_replacements = REPLACEMENT_VALUES.copy()
        plan_replacements["PLAN_NAME"] = plan_name
        plan_replacements["VAULT_NAME"] = vault_name

        plan_data = load_backup_resource(
            "backup_plan",
            additional_replacements=plan_replacements,
        )
        logging.debug(plan_data)

        plan_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_PLAN_PLURAL,
            plan_name, namespace="default",
        )
        k8s.create_custom_resource(plan_ref, plan_data)
        plan_cr = k8s.wait_resource_consumed_by_controller(plan_ref)

        assert plan_cr is not None
        assert k8s.get_resource_exists(plan_ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(plan_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Get the plan ID from status
        plan_cr = k8s.get_resource(plan_ref)
        assert 'status' in plan_cr
        assert 'id' in plan_cr['status']
        plan_id = plan_cr['status']['id']

        # Check plan exists in AWS
        assert self.plan_exists(backup_client, plan_id)

        plan = self.get_backup_plan(backup_client, plan_id)
        assert plan is not None
        assert plan["BackupPlan"]["BackupPlanName"] == plan_name

        # Verify the rule references the correct vault
        rules = plan["BackupPlan"]["Rules"]
        assert len(rules) > 0
        assert rules[0]["TargetBackupVaultName"] == vault_name

        # Delete the BackupPlan first
        _, deleted = k8s.delete_custom_resource(plan_ref)
        assert deleted

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check plan deleted from AWS
        assert not self.plan_exists(backup_client, plan_id)

        # Delete the BackupVault
        _, deleted = k8s.delete_custom_resource(vault_ref)
        assert deleted

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Check vault deleted from AWS
        assert not self.vault_exists(backup_client, vault_name)

    def test_update_plan(self, backup_client):
        """Test updating a BackupPlan's rules."""
        vault_name = random_suffix_name("ack-test-vault", 24)
        plan_name = random_suffix_name("ack-test-plan", 24)

        # First, create a BackupVault
        vault_replacements = REPLACEMENT_VALUES.copy()
        vault_replacements["VAULT_NAME"] = vault_name

        vault_data = load_backup_resource(
            "backup_vault",
            additional_replacements=vault_replacements,
        )

        vault_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_VAULT_PLURAL,
            vault_name, namespace="default",
        )
        k8s.create_custom_resource(vault_ref, vault_data)
        k8s.wait_resource_consumed_by_controller(vault_ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(vault_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Create the BackupPlan
        plan_replacements = REPLACEMENT_VALUES.copy()
        plan_replacements["PLAN_NAME"] = plan_name
        plan_replacements["VAULT_NAME"] = vault_name

        plan_data = load_backup_resource(
            "backup_plan",
            additional_replacements=plan_replacements,
        )

        plan_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_PLAN_PLURAL,
            plan_name, namespace="default",
        )
        k8s.create_custom_resource(plan_ref, plan_data)
        k8s.wait_resource_consumed_by_controller(plan_ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(plan_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Get the plan and update the schedule
        plan_cr = k8s.get_resource(plan_ref)
        plan_id = plan_cr['status']['id']

        # Update the schedule expression
        plan_cr['spec']['rules'][0]['scheduleExpression'] = "cron(0 6 * * ? *)"  # 6 AM daily

        k8s.patch_custom_resource(plan_ref, plan_cr)
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(plan_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Verify update in AWS
        plan = self.get_backup_plan(backup_client, plan_id)
        assert plan is not None
        # Note: The plan ID stays the same but version changes on update
        assert plan["BackupPlan"]["Rules"][0]["ScheduleExpression"] == "cron(0 6 * * ? *)"

        # Cleanup
        _, deleted = k8s.delete_custom_resource(plan_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        _, deleted = k8s.delete_custom_resource(vault_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)

    def test_plan_with_vault_ref(self, backup_client):
        """Test creating a BackupPlan using targetBackupVaultRef instead of targetBackupVaultName."""
        vault_name = random_suffix_name("ack-test-vault", 24)
        plan_name = random_suffix_name("ack-test-plan", 24)

        # First, create a BackupVault
        vault_replacements = REPLACEMENT_VALUES.copy()
        vault_replacements["VAULT_NAME"] = vault_name

        vault_data = load_backup_resource(
            "backup_vault",
            additional_replacements=vault_replacements,
        )

        vault_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_VAULT_PLURAL,
            vault_name, namespace="default",
        )
        k8s.create_custom_resource(vault_ref, vault_data)
        k8s.wait_resource_consumed_by_controller(vault_ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(vault_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Create the BackupPlan using vault reference
        plan_replacements = REPLACEMENT_VALUES.copy()
        plan_replacements["PLAN_NAME"] = plan_name
        plan_replacements["VAULT_NAME"] = vault_name

        plan_data = load_backup_resource(
            "backup_plan_with_ref",
            additional_replacements=plan_replacements,
        )

        plan_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_PLAN_PLURAL,
            plan_name, namespace="default",
        )
        k8s.create_custom_resource(plan_ref, plan_data)
        k8s.wait_resource_consumed_by_controller(plan_ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(plan_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Get the plan ID from status
        plan_cr = k8s.get_resource(plan_ref)
        plan_id = plan_cr['status']['id']

        # Check plan exists in AWS and references the correct vault
        plan = self.get_backup_plan(backup_client, plan_id)
        assert plan is not None
        assert plan["BackupPlan"]["Rules"][0]["TargetBackupVaultName"] == vault_name

        # Cleanup
        _, deleted = k8s.delete_custom_resource(plan_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        _, deleted = k8s.delete_custom_resource(vault_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)
