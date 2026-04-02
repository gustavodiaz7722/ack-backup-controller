	// BackupPlanId is outside the input_wrapper_field_path (BackupSelection).
	// Set from status where it was stored after creation.
	if r.ko.Status.BackupPlanID != nil {
		input.BackupPlanId = r.ko.Status.BackupPlanID
	}
	// SelectionId was renamed to ID in the CRD. Code-gen doesn't map it
	// back to the delete input automatically.
	if r.ko.Status.ID != nil {
		input.SelectionId = r.ko.Status.ID
	}
