	// BackupPlanId is outside the output_wrapper_field_path (BackupSelection).
	// The code generator only populates wrapper fields, so we set it manually.
	if resp.BackupPlanId != nil {
		ko.Spec.BackupPlanID = resp.BackupPlanId
	}
