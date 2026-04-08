// Fixed error field extraction for ValidationStatus with FailedFields as array of objects

const validationStatus = findValidation(unwrapped);
const errorFieldsMap = new Map(); // Map of field name to reason

if (validationStatus && validationStatus.FailedFields && Array.isArray(validationStatus.FailedFields)) {
    validationStatus.FailedFields.forEach(item => {
        // Handle both old format (string) and new format (object with Field and Reason)
        if (typeof item === 'string') {
            errorFieldsMap.set(item, validationStatus[item] || 'Validation failed');
        } else if (item && typeof item === 'object' && item.Field) {
            const fieldName = item.Field;
            const reason = item.Reason || 'Validation failed';

            // If field already has multiple reasons, append this one
            if (errorFieldsMap.has(fieldName)) {
                errorFieldsMap.set(fieldName, `${errorFieldsMap.get(fieldName)}; ${reason}`);
            } else {
                errorFieldsMap.set(fieldName, reason);
            }
        }
    });

    if (docIndex === 0) {
        console.log('✓ Error fields detected:', Array.from(errorFieldsMap.entries()));
    }
}
