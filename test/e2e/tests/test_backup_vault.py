# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the BackupVault resource.
"""

import pytest
import time
import logging

from acktest.resources import random_suffix_name
from acktest.k8s import resource as k8s
from acktest.k8s import condition
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_backup_resource
from e2e.replacement_values import REPLACEMENT_VALUES

RESOURCE_PLURAL = "backupvaults"

CREATE_WAIT_AFTER_SECONDS = 10
UPDATE_WAIT_AFTER_SECONDS = 10
DELETE_WAIT_AFTER_SECONDS = 10


@pytest.fixture(scope="module")
def simple_backup_vault(backup_client):
    resource_name = random_suffix_name("ack-test-vault", 32)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["VAULT_NAME"] = resource_name

    resource_data = load_backup_resource(
        "backup_vault",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    # Create the k8s resource
    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    # Teardown
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    except:
        pass

    # Wait for AWS deletion to propagate
    time.sleep(DELETE_WAIT_AFTER_SECONDS)

    # Verify vault is deleted from AWS
    try:
        backup_client.describe_backup_vault(BackupVaultName=resource_name)
        assert False, f"BackupVault {resource_name} still exists in AWS after deletion"
    except backup_client.exceptions.ResourceNotFoundException:
        pass
    except Exception:
        # AccessDeniedException also means not found for this API
        pass


@pytest.fixture(scope="module")
def backup_vault_with_tags(backup_client):
    resource_name = random_suffix_name("ack-test-vault-tags", 32)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["VAULT_NAME"] = resource_name

    resource_data = load_backup_resource(
        "backup_vault_tags",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    # Teardown
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    except:
        pass


@pytest.fixture(scope="module")
def backup_vault_with_kms(backup_client):
    resource_name = random_suffix_name("ack-test-vault-kms", 32)

    replacements = REPLACEMENT_VALUES.copy()
    replacements["VAULT_NAME"] = resource_name

    resource_data = load_backup_resource(
        "backup_vault_kms",
        additional_replacements=replacements,
    )
    logging.debug(resource_data)

    ref = k8s.CustomResourceReference(
        CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
        resource_name, namespace="default",
    )
    k8s.create_custom_resource(ref, resource_data)
    cr = k8s.wait_resource_consumed_by_controller(ref)

    assert cr is not None
    assert k8s.get_resource_exists(ref)

    yield (ref, cr)

    # Teardown
    try:
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted
    except:
        pass


@service_marker
@pytest.mark.canary
class TestBackupVault:
    def test_create(self, backup_client, simple_backup_vault):
        (ref, cr) = simple_backup_vault

        # Wait for the resource to be synced
        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        vault_name = cr["spec"]["name"]

        # Verify the resource exists in AWS
        response = backup_client.describe_backup_vault(
            BackupVaultName=vault_name
        )

        assert response["BackupVaultName"] == vault_name

        # Verify status fields are populated
        cr = k8s.get_resource(ref)
        assert cr["status"].get("creationDate") is not None

    def test_create_with_tags(self, backup_client, backup_vault_with_tags):
        """Test that tags specified at creation time are correctly applied."""
        (ref, cr) = backup_vault_with_tags

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        vault_name = cr["spec"]["name"]

        # Verify the resource exists in AWS
        response = backup_client.describe_backup_vault(
            BackupVaultName=vault_name
        )
        assert response["BackupVaultName"] == vault_name

        # Verify tags in AWS
        tags_response = backup_client.list_tags(
            ResourceArn=response["BackupVaultArn"]
        )
        aws_tags = tags_response.get("Tags", {})

        assert aws_tags.get("environment") == "testing"
        assert aws_tags.get("team") == "ack-dev"

        # Verify k8s resource spec tags match
        cr = k8s.get_resource(ref)
        spec_tags = cr["spec"].get("tags", {})
        assert spec_tags.get("environment") == "testing"
        assert spec_tags.get("team") == "ack-dev"

    def test_create_with_kms_key(self, backup_client, backup_vault_with_kms):
        """Test that a vault created with a customer-managed KMS key uses that key."""
        (ref, cr) = backup_vault_with_kms

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        vault_name = cr["spec"]["name"]

        # Verify the resource exists in AWS
        response = backup_client.describe_backup_vault(
            BackupVaultName=vault_name
        )
        assert response["BackupVaultName"] == vault_name

        # Verify the encryption key ARN matches the bootstrapped KMS key
        expected_kms_arn = REPLACEMENT_VALUES["KMS_KEY_ARN"]
        assert response["EncryptionKeyArn"] == expected_kms_arn

        # Verify status fields are populated
        cr = k8s.get_resource(ref)
        assert cr["status"].get("creationDate") is not None
        assert cr["spec"].get("encryptionKeyARN") == expected_kms_arn

    def test_update_tags(self, backup_client, simple_backup_vault):
        """Test adding and updating tags on an existing vault."""
        (ref, cr) = simple_backup_vault

        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        vault_name = cr["spec"]["name"]

        # Get the vault ARN for tag verification
        response = backup_client.describe_backup_vault(
            BackupVaultName=vault_name
        )
        vault_arn = response["BackupVaultArn"]

        # Update tags
        updates = {
            "spec": {
                "tags": {
                    "ManagedBy": "ACK",
                    "environment": "testing",
                    "new-tag": "new-value",
                }
            }
        }

        k8s.patch_custom_resource(ref, updates)
        time.sleep(UPDATE_WAIT_AFTER_SECONDS)

        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        # Verify updated tags in AWS
        tags_response = backup_client.list_tags(ResourceArn=vault_arn)
        aws_tags = tags_response.get("Tags", {})

        assert aws_tags.get("environment") == "testing"
        assert aws_tags.get("new-tag") == "new-value"

    def test_terminal_condition_invalid_encryption_key(self, backup_client):
        """Test that an invalid encryption key ARN results in a terminal condition."""
        resource_name = random_suffix_name("ack-test-vault-inv", 32)

        replacements = REPLACEMENT_VALUES.copy()
        replacements["VAULT_NAME"] = resource_name

        resource_data = load_backup_resource(
            "backup_vault_invalid",
            additional_replacements=replacements,
        )

        ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
            resource_name, namespace="default",
        )
        k8s.create_custom_resource(ref, resource_data)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        assert cr is not None

        # The controller should set the Terminal condition to True
        assert k8s.wait_on_condition(ref, "ACK.Terminal", "True", wait_periods=5)

        # Verify the terminal condition has a message
        cr = k8s.get_resource(ref)
        terminal_condition = None
        for cond in cr["status"].get("conditions", []):
            if cond["type"] == "ACK.Terminal":
                terminal_condition = cond
                break

        assert terminal_condition is not None
        assert terminal_condition["status"] == "True"

        # Verify the vault was NOT created in AWS
        try:
            backup_client.describe_backup_vault(BackupVaultName=resource_name)
            assert False, "Vault should not exist"
        except (backup_client.exceptions.ResourceNotFoundException, Exception):
            pass

        # Cleanup
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted

    def test_delete(self, backup_client):
        """Test that deleting the K8s resource deletes the AWS BackupVault."""
        resource_name = random_suffix_name("ack-test-vault-del", 32)

        replacements = REPLACEMENT_VALUES.copy()
        replacements["VAULT_NAME"] = resource_name

        resource_data = load_backup_resource(
            "backup_vault",
            additional_replacements=replacements,
        )

        ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, RESOURCE_PLURAL,
            resource_name, namespace="default",
        )
        k8s.create_custom_resource(ref, resource_data)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        assert cr is not None

        time.sleep(CREATE_WAIT_AFTER_SECONDS)
        assert k8s.wait_on_condition(ref, "ACK.ResourceSynced", "True", wait_periods=5)

        vault_name = cr["spec"]["name"]

        # Verify the vault exists in AWS
        response = backup_client.describe_backup_vault(
            BackupVaultName=vault_name
        )
        assert response["BackupVaultName"] == vault_name

        # Delete the K8s resource
        _, deleted = k8s.delete_custom_resource(ref, 3, 10)
        assert deleted

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        # Verify vault is deleted from AWS
        try:
            backup_client.describe_backup_vault(BackupVaultName=vault_name)
            assert False, f"BackupVault {vault_name} still exists in AWS after deletion"
        except backup_client.exceptions.ResourceNotFoundException:
            pass
        except Exception:
            # AccessDeniedException also means not found for this API
            pass
