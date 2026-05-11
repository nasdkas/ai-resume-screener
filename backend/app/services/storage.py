import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
DATA_FILE = os.path.join(DATA_DIR, 'data.json')
MATCH_RESULTS_FILE = os.path.join(DATA_DIR, 'match_results.json')

DEFAULT_DATA = {
    'resumes': [],
    'jds': [],
    'failedUploads': []
}


def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def load_data() -> Dict[str, Any]:
    ensure_data_dir()
    if not os.path.exists(DATA_FILE):
        return DEFAULT_DATA.copy()
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'jd' in data and 'jds' not in data:
            old_match_results = data.get('matchResults', [])
            if data['jd']:
                data['jds'] = [data['jd']]
            else:
                data['jds'] = []
            del data['jd']
            if 'matchResults' in data:
                del data['matchResults']
            save_data(data)
            if old_match_results and not os.path.exists(MATCH_RESULTS_FILE):
                _save_match_results(old_match_results)
        for key, default_value in DEFAULT_DATA.items():
            if key not in data:
                data[key] = default_value
        if 'jd' in data:
            del data['jd']
        if 'matchResults' in data:
            del data['matchResults']
        return data
    except (json.JSONDecodeError, IOError):
        return DEFAULT_DATA.copy()


def save_data(data: Dict[str, Any]):
    ensure_data_dir()
    clean = {k: v for k, v in data.items() if k in DEFAULT_DATA}
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(clean, f, ensure_ascii=False, indent=2, default=str)


def _load_match_results() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not os.path.exists(MATCH_RESULTS_FILE):
        return []
    try:
        with open(MATCH_RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_match_results(results: List[Dict[str, Any]]):
    ensure_data_dir()
    with open(MATCH_RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)


def save_resume(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    data = load_data()
    resume_id = str(uuid.uuid4())
    resume = {
        'id': resume_id,
        **resume_data,
        'createdAt': datetime.now().isoformat()
    }
    data['resumes'].append(resume)
    save_data(data)
    return resume


def get_all_resumes() -> List[Dict[str, Any]]:
    data = load_data()
    return data.get('resumes', [])


def get_resume_by_id(resume_id: str) -> Optional[Dict[str, Any]]:
    data = load_data()
    for resume in data.get('resumes', []):
        if resume['id'] == resume_id:
            return resume
    return None


def update_resume(resume_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = load_data()
    for resume in data.get('resumes', []):
        if resume['id'] == resume_id:
            resume.update(updates)
            save_data(data)
            return resume
    return None


def delete_resume(resume_id: str) -> bool:
    data = load_data()
    original_length = len(data.get('resumes', []))
    data['resumes'] = [r for r in data.get('resumes', []) if r['id'] != resume_id]
    save_data(data)
    results = _load_match_results()
    _save_match_results([m for m in results if m['resumeId'] != resume_id])
    return len(data['resumes']) < original_length


def save_jd(jd_data: Dict[str, Any]) -> Dict[str, Any]:
    data = load_data()
    jd_id = str(uuid.uuid4())
    jd = {
        'id': jd_id,
        **jd_data,
        'createdAt': datetime.now().isoformat()
    }
    data['jds'].append(jd)
    save_data(data)
    return jd


def get_all_jds() -> List[Dict[str, Any]]:
    data = load_data()
    return data.get('jds', [])


def get_jd_by_id(jd_id: str) -> Optional[Dict[str, Any]]:
    data = load_data()
    for jd in data.get('jds', []):
        if jd['id'] == jd_id:
            return jd
    return None


def get_jd() -> Optional[Dict[str, Any]]:
    jds = get_all_jds()
    return jds[0] if jds else None


def update_jd(jd_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = load_data()
    for jd in data.get('jds', []):
        if jd['id'] == jd_id:
            jd.update(updates)
            save_data(data)
            return jd
    return None


def delete_jd(jd_id: str) -> bool:
    data = load_data()
    original_length = len(data.get('jds', []))
    data['jds'] = [j for j in data.get('jds', []) if j['id'] != jd_id]
    for resume in data.get('resumes', []):
        if resume.get('jdId') == jd_id:
            resume['jdId'] = None
    save_data(data)
    results = _load_match_results()
    _save_match_results([m for m in results if m['jdId'] != jd_id])
    return len(data['jds']) < original_length


def save_match_result(match_result_data: Dict[str, Any]) -> Dict[str, Any]:
    results = _load_match_results()
    resume_id = match_result_data.get('resumeId')
    jd_id = match_result_data.get('jdId')
    existing_index = None
    if resume_id and jd_id:
        for i, r in enumerate(results):
            if r.get('resumeId') == resume_id and r.get('jdId') == jd_id:
                existing_index = i
                break
    match_result = {
        **match_result_data,
        'createdAt': datetime.now().isoformat()
    }
    if existing_index is not None:
        match_result['id'] = results[existing_index].get('id', str(uuid.uuid4()))
        results[existing_index] = match_result
    else:
        match_result['id'] = str(uuid.uuid4())
        results.append(match_result)
    _save_match_results(results)
    return match_result


def get_all_match_results() -> List[Dict[str, Any]]:
    return _load_match_results()


def get_match_results_by_jd_id(jd_id: str) -> List[Dict[str, Any]]:
    results = _load_match_results()
    return [r for r in results if r['jdId'] == jd_id]


def get_match_result_by_resume_and_jd(resume_id: str, jd_id: str) -> Optional[Dict[str, Any]]:
    results = _load_match_results()
    for result in results:
        if result['resumeId'] == resume_id and result['jdId'] == jd_id:
            return result
    return None


def get_match_result_by_resume_id(resume_id: str) -> Optional[Dict[str, Any]]:
    results = _load_match_results()
    for result in results:
        if result['resumeId'] == resume_id:
            return result
    return None


def delete_match_results_by_jd_id(jd_id: str):
    results = _load_match_results()
    _save_match_results([m for m in results if m['jdId'] != jd_id])


def delete_match_result(resume_id: str, jd_id: str) -> bool:
    results = _load_match_results()
    original_length = len(results)
    _save_match_results([m for m in results if not (m['resumeId'] == resume_id and m['jdId'] == jd_id)])
    return len(results) > original_length - 1 and original_length != len(_load_match_results())


def save_failed_upload(filename: str, error: str) -> Dict[str, Any]:
    data = load_data()
    record = {
        'id': str(uuid.uuid4()),
        'filename': filename,
        'error': error,
        'createdAt': datetime.now().isoformat()
    }
    if 'failedUploads' not in data:
        data['failedUploads'] = []
    data['failedUploads'].append(record)
    save_data(data)
    return record


def get_all_failed_uploads() -> List[Dict[str, Any]]:
    data = load_data()
    return data.get('failedUploads', [])


def delete_failed_upload(failed_id: str) -> bool:
    data = load_data()
    original_length = len(data.get('failedUploads', []))
    data['failedUploads'] = [f for f in data.get('failedUploads', []) if f['id'] != failed_id]
    save_data(data)
    return len(data['failedUploads']) < original_length


def delete_failed_uploads_by_filename(filename: str) -> int:
    data = load_data()
    original_length = len(data.get('failedUploads', []))
    data['failedUploads'] = [f for f in data.get('failedUploads', []) if f['filename'] != filename]
    save_data(data)
    return original_length - len(data['failedUploads'])
