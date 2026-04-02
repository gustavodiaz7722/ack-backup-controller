	// BackupPlanId is outside the input_wrapper_field_path (BackupSelection).
	// The code generator only populates wrapper fields, so we set it manually.
	if desired.ko.Spec.BackupPlanID != nil {
		input.BackupPlanId = desired.ko.Spec.BackupPlanID
	}
