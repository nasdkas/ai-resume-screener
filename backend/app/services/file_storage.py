import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

RESUME_STORAGE_DIR = os.getenv('RESUME_STORAGE_DIR', '')

if not RESUME_STORAGE_DIR:
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
    RESUME_STORAGE_DIR = os.path.join(DATA_DIR, 'resumes')


def ensure_storage_dir():
    if not os.path.exists(RESUME_STORAGE_DIR):
        os.makedirs(RESUME_STORAGE_DIR)


def get_file_extension(filename: str) -> str:
    if '.' in filename:
        return filename.rsplit('.', 1)[-1].lower()
    return ''


def save_resume_file(resume_id: str, file_bytes: bytes, original_filename: str) -> Tuple[str, str]:
    ensure_storage_dir()
    
    extension = get_file_extension(original_filename)
    if extension:
        stored_filename = f"{resume_id}.{extension}"
    else:
        stored_filename = resume_id
    
    file_path = os.path.join(RESUME_STORAGE_DIR, stored_filename)
    
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    
    return stored_filename, original_filename


def get_resume_file_path(resume_id: str) -> Optional[str]:
    ensure_storage_dir()
    
    for ext in ['pdf', 'docx', 'doc', 'txt']:
        file_path = os.path.join(RESUME_STORAGE_DIR, f"{resume_id}.{ext}")
        if os.path.exists(file_path):
            return file_path
    
    return None


def get_resume_file_info(resume_id: str) -> Optional[Tuple[str, str]]:
    file_path = get_resume_file_path(resume_id)
    if not file_path:
        return None
    
    extension = get_file_extension(file_path)
    
    mime_types = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'doc': 'application/msword',
        'txt': 'text/plain'
    }
    
    mime_type = mime_types.get(extension, 'application/octet-stream')
    
    return file_path, mime_type


def delete_resume_file(resume_id: str) -> bool:
    file_path = get_resume_file_path(resume_id)
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False
