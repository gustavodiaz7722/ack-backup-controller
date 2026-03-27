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
"""Stores the values used by each of the integration tests for replacing the
Backup-specific test variables.
"""

from acktest.aws.identity import get_region, get_account_id
from e2e.bootstrap_resources import get_bootstrap_resources

def get_replacement_values():
    """Get replacement values from bootstrap resources."""
    try:
        resources = get_bootstrap_resources()
        region = get_region()
        account_id = get_account_id()
        kms_key_arn = f"arn:aws:kms:{region}:{account_id}:key/{resources.KmsKey.id}"
        return {
            "KMS_KEY_ARN": kms_key_arn,
        }
    except:
        return {
            "KMS_KEY_ARN": "",
        }

REPLACEMENT_VALUES = get_replacement_values()
