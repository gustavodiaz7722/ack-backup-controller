	// UpdateBackupPlan requires BackupPlanId which is outside the
	// input_wrapper_field_path (BackupPlan). The code generator only
	// populates wrapper fields, so we set the identifier manually.
	if desired.ko.Status.ID != nil {
		input.BackupPlanId = desired.ko.Status.ID
	}
