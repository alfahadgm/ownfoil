from constants import *
from db import *
from titles import *
import os
import shutil
import re

def identify_files_and_add_to_db(library_path, files):
    nb_to_identify = len(files)
    for n, filepath in enumerate(files):
        file = filepath.replace(library_path, "")
        logger.info(f'Identifying file ({n+1}/{nb_to_identify}): {file}')

        file_info = identify_file(filepath)

        if file_info is None:
            logger.error(f'Failed to identify: {file} - file will be skipped.')
            # in the future save identification error to be displayed and inspected in the UI
            continue

        logger.info(f'Identifying file ({n+1}/{nb_to_identify}): {file} OK Title ID: {file_info["title_id"]} App ID : {file_info["app_id"]} Title Type: {file_info["type"]} Version: {file_info["version"]}')
        add_to_titles_db(library_path, file_info)


def scan_library_path(app_settings, library_path):
    try:
        logger.info(f'Scanning library path {library_path} ...')
        if not os.path.isdir(library_path):
            logger.warning(f'Library path {library_path} does not exists.')
            return
        _, files = getDirsAndFiles(library_path)

        if app_settings['titles']['valid_keys']:
            current_identification = 'cnmt'
        else:
            logger.warning('Invalid or non existing keys.txt, title identification fallback to filename only.')
            current_identification = 'filename'

        all_files_with_current_identification = get_all_files_with_identification(current_identification)
        files_to_identify = [f for f in files if f not in all_files_with_current_identification]
        identify_files_and_add_to_db(library_path, files_to_identify)
    finally:
        pass


def get_library_status(title_id):
    has_base = False
    has_latest_version = False

    title_files = get_all_title_files(title_id)
    if len(list(filter(lambda x: x.get('type') == APP_TYPE_BASE, title_files))):
        has_base = True

    available_versions = get_all_existing_versions(title_id)
    if available_versions is None:
        return {
            'has_base': has_base,
            'has_latest_version': True,
            'version': []
        }
    game_latest_version = get_game_latest_version(available_versions)
    for version in available_versions:
        if len(list(filter(lambda x: x.get('type') == APP_TYPE_UPD and str(x.get('version')) == str(version['version']), title_files))):
            version['owned'] = True
            if str(version['version'])  == str(game_latest_version):
                has_latest_version = True
        else:
            version['owned'] = False

    all_existing_dlcs = get_all_existing_dlc(title_id)
    owned_dlcs = [t['app_id'] for t in title_files if t['type'] == APP_TYPE_DLC]
    has_all_dlcs = all(dlc in owned_dlcs for dlc in all_existing_dlcs)

    library_status = {
        'has_base': has_base,
        'has_latest_version': has_latest_version,
        'version': available_versions,
        'has_all_dlcs': has_all_dlcs
    }
    return library_status


def generate_library():
    logger.info(f'Generating library ...')
    titles = get_all_titles_from_db()
    games_info = []
    for title in titles:
        has_none_value = any(value is None for value in title.values())
        if has_none_value:
            logger.warning(f'File contains None value, it will be skipped: {title}')
            continue
        if title['type'] == APP_TYPE_UPD:
            continue
        info_from_titledb = get_game_info(title['app_id'])
        if info_from_titledb is None:
            logger.warning(f'Info not found for game: {title}')
            continue
        title.update(info_from_titledb)
        if title['type'] == APP_TYPE_BASE:
            library_status = get_library_status(title['app_id'])
            title.update(library_status)
            title['title_id_name'] = title['name']
        if title['type'] == APP_TYPE_DLC:
            dlc_has_latest_version = None
            all_dlc_existing_versions = get_all_dlc_existing_versions(title['app_id'])

            if all_dlc_existing_versions is not None and len(all_dlc_existing_versions):
                if title['version'] == all_dlc_existing_versions[-1]:
                    dlc_has_latest_version = True
                else:
                    dlc_has_latest_version = False

            else:
                app_id_version_from_versions_txt = get_app_id_version_from_versions_txt(title['app_id'])
                if app_id_version_from_versions_txt is not None:
                    if int(title['version']) == int(app_id_version_from_versions_txt):
                        dlc_has_latest_version = True
                    else:
                        dlc_has_latest_version = False


            if dlc_has_latest_version is not None:
                title['has_latest_version'] = dlc_has_latest_version

            titleid_info = get_game_info(title['title_id'])
            title['title_id_name'] = titleid_info['name']
        games_info.append(title)
    titles_library = sorted(games_info, key=lambda x: (
        "title_id_name" not in x, 
        x.get("title_id_name", "Unrecognized") or "Unrecognized", 
        x.get('app_id', "") or ""
    ))
    logger.info(f'Generating library done.')

    return titles_library


def sanitize_filename(filename):
    """Remove or replace characters that are invalid in filenames"""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    # Limit length to avoid filesystem issues
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def generate_organized_filename(file_info, title_info):
    """Generate a standardized filename for a game file"""
    name = sanitize_filename(title_info.get('name', 'Unknown'))
    app_id = file_info['app_id']
    file_type = file_info['type']
    version = file_info['version']
    extension = file_info['extension']
    
    if file_type == APP_TYPE_BASE:
        filename = f"{name} [{app_id}][{version}].{extension}"
    elif file_type == APP_TYPE_UPD:
        filename = f"{name} [{app_id}][v{version}].{extension}"
    elif file_type == APP_TYPE_DLC:
        dlc_name = file_info.get('name', '')
        if dlc_name and dlc_name != name:
            filename = f"{name} - {dlc_name} [{app_id}][v{version}].{extension}"
        else:
            filename = f"{name} [{app_id}][v{version}].{extension}"
    
    return filename


def generate_organized_path(library_path, file_info, title_info):
    """Generate organized directory structure for a game file"""
    name = sanitize_filename(title_info.get('name', 'Unknown'))
    file_type = file_info['type']
    
    # Create directory structure: library/GameName/Type/
    if file_type == APP_TYPE_BASE:
        subdir = os.path.join(name, "BASE")
    elif file_type == APP_TYPE_UPD:
        subdir = os.path.join(name, "UPDATES")
    elif file_type == APP_TYPE_DLC:
        subdir = os.path.join(name, "DLC")
    
    return os.path.join(library_path, subdir)


def preview_library_organization(library_paths=None, organize_by_name=True):
    """Preview how files would be organized without making changes"""
    all_files = get_all_titles_from_db()
    changes = []
    errors = []
    
    for file_info in all_files:
        try:
            # Skip if library path specified and file not in that library
            if library_paths and file_info['library'] not in library_paths:
                continue
                
            # Get title information
            if file_info['type'] == APP_TYPE_BASE:
                title_info = get_game_info(file_info['app_id'])
            else:
                title_info = get_game_info(file_info['title_id'])
            
            if title_info.get('name') == 'Unrecognized':
                errors.append({
                    'file': file_info['filepath'],
                    'error': 'Title not found in database'
                })
                continue
            
            old_path = file_info['filepath']
            
            if organize_by_name:
                # Generate new organized path
                new_dir = generate_organized_path(file_info['library'], file_info, title_info)
                new_filename = generate_organized_filename(file_info, title_info)
                new_path = os.path.join(new_dir, new_filename)
            else:
                # Just rename in place
                new_dir = os.path.dirname(old_path)
                new_filename = generate_organized_filename(file_info, title_info)
                new_path = os.path.join(new_dir, new_filename)
            
            if old_path != new_path:
                changes.append({
                    'id': file_info['id'],
                    'old_path': old_path,
                    'new_path': new_path,
                    'library': file_info['library'],
                    'type': file_info['type'],
                    'title_name': title_info.get('name', 'Unknown')
                })
                
        except Exception as e:
            errors.append({
                'file': file_info.get('filepath', 'Unknown'),
                'error': str(e)
            })
    
    return changes, errors


def apply_library_organization(changes, dry_run=False):
    """Apply the organization changes to the library"""
    results = {
        'success': [],
        'errors': []
    }
    
    for change in changes:
        old_path = change['old_path']
        new_path = change['new_path']
        
        try:
            if not dry_run:
                # Create directory if it doesn't exist
                new_dir = os.path.dirname(new_path)
                os.makedirs(new_dir, exist_ok=True)
                
                # Check if destination already exists
                if os.path.exists(new_path) and old_path != new_path:
                    results['errors'].append({
                        'file': old_path,
                        'error': f'Destination already exists: {new_path}'
                    })
                    continue
                
                # Move the file
                shutil.move(old_path, new_path)
                
                # Update database
                update_file_path(change['library'], old_path, new_path)
                
            results['success'].append({
                'old_path': old_path,
                'new_path': new_path
            })
            
        except Exception as e:
            results['errors'].append({
                'file': old_path,
                'error': str(e)
            })
            logger.error(f'Error organizing file {old_path}: {e}')
    
    return results


def find_duplicate_updates(title_id=None):
    """Find update files that have newer versions available"""
    all_files = get_all_titles_from_db()
    
    # Group updates by title_id
    updates_by_title = {}
    for file_info in all_files:
        if file_info['type'] != APP_TYPE_UPD:
            continue
            
        if title_id and file_info['title_id'] != title_id:
            continue
            
        tid = file_info['title_id']
        if tid not in updates_by_title:
            updates_by_title[tid] = []
        
        updates_by_title[tid].append(file_info)
    
    # Find older versions
    duplicates = []
    for tid, updates in updates_by_title.items():
        if len(updates) <= 1:
            continue
            
        # Sort by version (newest first)
        sorted_updates = sorted(updates, 
                              key=lambda x: int(x['version']) if x['version'] else 0, 
                              reverse=True)
        
        # All except the newest are duplicates
        title_info = get_game_info(tid)
        for update in sorted_updates[1:]:
            duplicates.append({
                'id': update['id'],
                'filepath': update['filepath'],
                'title_id': tid,
                'title_name': title_info.get('name', 'Unknown'),
                'version': update['version'],
                'size': update['size'],
                'latest_version': sorted_updates[0]['version']
            })
    
    return duplicates


def delete_duplicate_updates(duplicates, dry_run=False):
    """Delete duplicate update files"""
    results = {
        'deleted': [],
        'errors': []
    }
    
    for dup in duplicates:
        filepath = dup['filepath']
        
        try:
            if not dry_run:
                # Delete the file
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"Deleted duplicate update: {filepath}")
                
                # Remove from database
                delete_file_by_filepath(filepath)
            
            results['deleted'].append({
                'filepath': filepath,
                'title': dup['title_name'],
                'version': dup['version'],
                'size': dup['size']
            })
            
        except Exception as e:
            results['errors'].append({
                'file': filepath,
                'error': str(e)
            })
            logger.error(f'Error deleting file {filepath}: {e}')
    
    return results
