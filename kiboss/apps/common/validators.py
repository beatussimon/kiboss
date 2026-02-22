import os
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

# 5 MB max size
MAX_UPLOAD_SIZE = 5 * 1024 * 1024

def validate_file_size(value):
    if hasattr(value, 'size') and value.size > MAX_UPLOAD_SIZE:
        raise ValidationError(f"File size cannot exceed {MAX_UPLOAD_SIZE / (1024*1024)} MB.")

def validate_image_extension(value):
    ext_validator = FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])
    ext_validator(value)

def validate_document_extension(value):
    ext_validator = FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])
    ext_validator(value)

def validate_attachment_extension(value):
    ext_validator = FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'txt', 'csv', 'docx'])
    ext_validator(value)
