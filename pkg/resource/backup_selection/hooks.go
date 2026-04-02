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

package backup_selection

import (
	"context"
	"fmt"

	ackcompare "github.com/aws-controllers-k8s/runtime/pkg/compare"
	ackcondition "github.com/aws-controllers-k8s/runtime/pkg/condition"
	ackerr "github.com/aws-controllers-k8s/runtime/pkg/errors"
	corev1 "k8s.io/api/core/v1"
)

// customUpdateBackupSelection handles updates for BackupSelection resources.
// There is no UpdateBackupSelection API — selections can only be created or
// deleted. Return a terminal error so users get feedback.
func (rm *resourceManager) customUpdateBackupSelection(
	ctx context.Context,
	desired *resource,
	latest *resource,
	delta *ackcompare.Delta,
) (*resource, error) {
	msg := "BackupSelection resources cannot be updated. Delete and recreate the resource to apply changes."
	ackcondition.SetTerminal(desired, corev1.ConditionTrue, &msg, nil)
	return desired, ackerr.NewTerminalError(fmt.Errorf(msg))
}
