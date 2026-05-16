import os
import mimetypes
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

# 5 MB max size
MAX_UPLOAD_SIZE = 5 * 1024 * 1024

def validate_file_size(value):
    if hasattr(value, 'size') and value.size > MAX_UPLOAD_SIZE:
        raise ValidationError(f"File size cannot exceed {MAX_UPLOAD_SIZE / (1024*1024)} MB.")

def validate_file_content_type(value, allowed_mimes):
    if hasattr(value, 'file'):
        pos = value.file.tell()
        value.file.seek(0)
        _ = value.file.read(2048)
        value.file.seek(pos)
    
    mime_type, _ = mimetypes.guess_type(value.name)
    if mime_type not in allowed_mimes:
        raise ValidationError(f"Invalid file type: {mime_type}. Allowed: {', '.join(allowed_mimes)}")

def validate_image_extension(value):
    ext_validator = FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])
    ext_validator(value)

def validate_document_extension(value):
    ext_validator = FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])
    ext_validator(value)

def validate_attachment_extension(value):
    ext_validator = FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'txt', 'csv', 'docx'])
    ext_validator(value)

def validate_image_content(value):
    validate_file_size(value)
    validate_image_extension(value)
    validate_file_content_type(value, ['image/jpeg', 'image/png', 'image/webp'])

def validate_document_content(value):
    validate_file_size(value)
    validate_document_extension(value)
    validate_file_content_type(value, ['application/pdf', 'image/jpeg', 'image/png'])
