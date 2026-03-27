// Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"). You may
// not use this file except in compliance with the License. A copy of the
// License is located at
//
//     http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file. This file is distributed
// on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
// express or implied. See the License for the specific language governing
// permissions and limitations under the License.

package backup_vault

import (
	"context"

	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"

	"github.com/aws-controllers-k8s/backup-controller/pkg/sync"
)

var syncTags = sync.Tags

// customUpdateBackupVault handles updates for BackupVault resources.
// There is no UpdateBackupVault API — the only mutable field is Tags,
// which is synced via TagResource/UntagResource.
func (rm *resourceManager) customUpdateBackupVault(
	ctx context.Context,
	desired *resource,
	latest *resource,
	delta *ackcompare.Delta,
) (*resource, error) {
	updatedDesired := desired.DeepCopy()
	updatedDesired.SetStatus(latest)
	if delta.DifferentAt("Spec.Tags") {
		arn := string(*latest.ko.Status.ACKResourceMetadata.ARN)
		err := syncTags(
			ctx,
			desired.ko.Spec.Tags, latest.ko.Spec.Tags,
			&arn, convertToOrderedACKTags, rm.sdkapi, rm.metrics,
		)
		if err != nil {
			return nil, err
		}
	}
	return rm.concreteResource(updatedDesired), nil
}
