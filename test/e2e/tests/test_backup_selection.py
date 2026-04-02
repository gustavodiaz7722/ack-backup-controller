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

"""Integration tests for the AWS Backup BackupSelection resource.
"""

import pytest
import time
import logging

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s
from acktest.k8s import condition
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_backup_resource
from e2e.bootstrap_resources import get_bootstrap_resources
from e2e.replacement_values import REPLACEMENT_VALUES

BACKUP_VAULT_PLURAL = "backupvaults"
BACKUP_PLAN_PLURAL = "backupplans"
BACKUP_SELECTION_PLURAL = "backupselections"

CREATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10

# The IAM role ARN must have permissions for AWS Backup.
# This should be set in the test environment or replacement_values.py.



@service_marker
@pytest.mark.canary
class TestBackupSelection:
    def get_backup_selection(self, backup_client, plan_id: str, selection_id: str) -> dict:
        try:
            resp = backup_client.get_backup_selection(
                BackupPlanId=plan_id,
                SelectionId=selection_id,
            )
            return resp
        except backup_client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logging.debug(e)
            return None

    def selection_exists(self, backup_client, plan_id: str, selection_id: str) -> bool:
        return self.get_backup_selection(backup_client, plan_id, selection_id) is not None

    def create_vault_and_plan(self, backup_client):
        """Helper to create a BackupVault and BackupPlan for selection tests."""
        vault_name = random_suffix_name("ack-test-vault", 24)
        plan_name = random_suffix_name("ack-test-plan", 24)

        # Create BackupVault
        vault_replacements = REPLACEMENT_VALUES.copy()
        vault_replacements["VAULT_NAME"] = vault_name
        vault_data = load_backup_resource("backup_vault", additional_replacements=vault_replacements)

        vault_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_VAULT_PLURAL,
            vault_name, namespace="default",
        )
        k8s.create_custom_resource(vault_ref, vault_data)
        k8s.wait_resource_consumed_by_controller(vault_ref)
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(vault_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Create BackupPlan
        plan_replacements = REPLACEMENT_VALUES.copy()
        plan_replacements["PLAN_NAME"] = plan_name
        plan_replacements["VAULT_NAME"] = vault_name
        plan_data = load_backup_resource("backup_plan", additional_replacements=plan_replacements)

        plan_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_PLAN_PLURAL,
            plan_name, namespace="default",
        )
        k8s.create_custom_resource(plan_ref, plan_data)
        k8s.wait_resource_consumed_by_controller(plan_ref)
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(plan_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        plan_cr = k8s.get_resource(plan_ref)
        plan_id = plan_cr['status']['id']

        return vault_name, vault_ref, plan_name, plan_ref, plan_id

    def test_create_delete(self, backup_client):
        """Test basic create and delete operations for BackupSelection."""
        vault_name, vault_ref, plan_name, plan_ref, plan_id = self.create_vault_and_plan(backup_client)

        selection_name = random_suffix_name("ack-test-sel", 24)
        resources = get_bootstrap_resources()
        iam_role_arn = resources.BackupRole.arn

        sel_replacements = REPLACEMENT_VALUES.copy()
        sel_replacements["SELECTION_NAME"] = selection_name
        sel_replacements["PLAN_ID"] = plan_id
        sel_replacements["IAM_ROLE_ARN"] = iam_role_arn

        sel_data = load_backup_resource("backup_selection", additional_replacements=sel_replacements)
        logging.debug(sel_data)

        sel_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_SELECTION_PLURAL,
            selection_name, namespace="default",
        )
        k8s.create_custom_resource(sel_ref, sel_data)
        sel_cr = k8s.wait_resource_consumed_by_controller(sel_ref)

        assert sel_cr is not None
        assert k8s.get_resource_exists(sel_ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(sel_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Verify selection ID was assigned
        sel_cr = k8s.get_resource(sel_ref)
        assert 'status' in sel_cr
        assert 'id' in sel_cr['status']
        selection_id = sel_cr['status']['id']

        # Verify in AWS
        assert self.selection_exists(backup_client, plan_id, selection_id)

        sel = self.get_backup_selection(backup_client, plan_id, selection_id)
        assert sel is not None
        assert sel["BackupSelection"]["SelectionName"] == selection_name
        assert sel["BackupSelection"]["IamRoleArn"] == iam_role_arn

        # Delete selection first, then plan, then vault (reverse order)
        _, deleted = k8s.delete_custom_resource(sel_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)
        assert not self.selection_exists(backup_client, plan_id, selection_id)

        _, deleted = k8s.delete_custom_resource(plan_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        _, deleted = k8s.delete_custom_resource(vault_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)

    def test_selection_with_plan_ref(self, backup_client):
        """Test creating a BackupSelection using backupPlanRef instead of backupPlanID."""
        vault_name, vault_ref, plan_name, plan_ref, plan_id = self.create_vault_and_plan(backup_client)

        selection_name = random_suffix_name("ack-test-sel", 24)
        resources = get_bootstrap_resources()
        iam_role_arn = resources.BackupRole.arn

        sel_replacements = REPLACEMENT_VALUES.copy()
        sel_replacements["SELECTION_NAME"] = selection_name
        sel_replacements["PLAN_NAME"] = plan_name
        sel_replacements["IAM_ROLE_ARN"] = iam_role_arn

        sel_data = load_backup_resource("backup_selection_with_ref", additional_replacements=sel_replacements)
        logging.debug(sel_data)

        sel_ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, BACKUP_SELECTION_PLURAL,
            selection_name, namespace="default",
        )
        k8s.create_custom_resource(sel_ref, sel_data)
        k8s.wait_resource_consumed_by_controller(sel_ref)

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(sel_ref, condition.CONDITION_TYPE_RESOURCE_SYNCED, "True", wait_periods=5)

        # Verify the plan ID was resolved from the reference
        sel_cr = k8s.get_resource(sel_ref)
        selection_id = sel_cr['status']['id']

        sel = self.get_backup_selection(backup_client, plan_id, selection_id)
        assert sel is not None
        assert sel["BackupSelection"]["SelectionName"] == selection_name

        # Cleanup in reverse order
        _, deleted = k8s.delete_custom_resource(sel_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        _, deleted = k8s.delete_custom_resource(plan_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        _, deleted = k8s.delete_custom_resource(vault_ref)
        assert deleted
        time.sleep(DELETE_WAIT_AFTER_SECONDS)
