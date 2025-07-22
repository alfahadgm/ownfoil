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
        # Check only critical fields, version can be None for base games and DLC
        critical_fields = ['filepath', 'title_id', 'app_id', 'type']
        has_critical_none = any(title.get(field) is None for field in critical_fields)
        if has_critical_none:
            logger.warning(f'File contains None in critical fields, it will be skipped: {title}')
            continue
        if title['type'] == APP_TYPE_UPD:
            continue
        info_from_titledb = get_game_info(title['app_id'])
        if info_from_titledb is None:
            logger.warning(f'Info not found for game: {title}')
            continue
        
        # Use extracted name as fallback if title not found in database
        if info_from_titledb.get('name') == 'Unrecognized':
            extracted_name = extract_name_from_filename(title['filename'])
            if extracted_name:
                info_from_titledb['name'] = extracted_name
                logger.info(f"Using extracted name '{extracted_name}' for {title['filename']}")
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
                
            # Ensure file_info has required fields
            if not file_info.get('filepath') or not file_info.get('filename'):
                logger.warning(f"File info missing required fields: {file_info}")
                continue
                
            # Add extension field if missing
            if 'extension' not in file_info:
                file_info['extension'] = file_info['filename'].split('.')[-1] if '.' in file_info['filename'] else 'nsp'
                
            # Get title information
            if file_info['type'] == APP_TYPE_BASE:
                title_info = get_game_info(file_info['app_id'])
            else:
                title_info = get_game_info(file_info['title_id'])
            
            # Handle cases where title_info is None
            if title_info is None:
                title_info = {'name': 'Unrecognized'}
            
            if title_info.get('name') == 'Unrecognized':
                # Try to extract name from filename as fallback
                extracted_name = extract_name_from_filename(file_info['filename'])
                if extracted_name:
                    title_info['name'] = extracted_name
                    logger.info(f"Using extracted name '{extracted_name}' for {file_info['filepath']}")
                else:
                    errors.append({
                        'file': file_info['filepath'],
                        'error': 'Title not found in database and could not extract from filename'
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


def apply_library_organization(changes, dry_run=False, remove_empty_folders=True):
    """Apply the organization changes to the library"""
    results = {
        'success': [],
        'errors': [],
        'skipped': []
    }
    
    # Track processed files to avoid moving duplicates
    processed_destinations = set()
    
    for change in changes:
        old_path = change['old_path']
        new_path = change['new_path']
        
        try:
            if not dry_run:
                # Create directory if it doesn't exist
                new_dir = os.path.dirname(new_path)
                os.makedirs(new_dir, exist_ok=True)
                
                # Check if destination already exists
                if os.path.exists(new_path) and old_path.lower() != new_path.lower():
                    # Check if files are identical by comparing size
                    old_size = os.path.getsize(old_path) if os.path.exists(old_path) else 0
                    new_size = os.path.getsize(new_path)
                    
                    if old_size == new_size:
                        # Files are likely the same, skip and mark for potential deletion
                        results['skipped'].append({
                            'file': old_path,
                            'reason': f'Identical file already exists at destination: {new_path}',
                            'can_delete': True
                        })
                    else:
                        # Files are different, don't overwrite
                        results['errors'].append({
                            'file': old_path,
                            'error': f'Destination already exists: {new_path}'
                        })
                    continue
                
                # Check if we've already processed a file going to this destination
                if new_path.lower() in processed_destinations:
                    results['errors'].append({
                        'file': old_path,
                        'error': f'Another file is already being moved to: {new_path}'
                    })
                    continue
                
                # Move the file
                shutil.move(old_path, new_path)
                processed_destinations.add(new_path.lower())
                
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
    
    # Clean up empty directories after organization (if requested)
    if not dry_run and results['success'] and remove_empty_folders:
        cleanup_empty_directories(changes)
    
    return results


def cleanup_empty_directories(changes):
    """Clean up empty directories after file organization"""
    # Collect all source directories that had files moved
    source_dirs = set()
    for change in changes:
        old_dir = os.path.dirname(change['old_path'])
        while old_dir and old_dir != '/':
            source_dirs.add(old_dir)
            old_dir = os.path.dirname(old_dir)
    
    # Sort by length (deepest first) to clean up from bottom to top
    sorted_dirs = sorted(source_dirs, key=len, reverse=True)
    
    cleaned_dirs = []
    for dir_path in sorted_dirs:
        try:
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                # Check if directory is empty
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    cleaned_dirs.append(dir_path)
                    logger.info(f'Removed empty directory: {dir_path}')
        except Exception as e:
            logger.debug(f'Could not remove directory {dir_path}: {e}')
    
    return cleaned_dirs


def find_all_duplicates(title_id=None):
    """Find all duplicate files (updates with older versions and duplicate base/DLC files)"""
    all_files = get_all_titles_from_db()
    
    # Group files by title_id and type
    files_by_title_type = {}
    for file_info in all_files:
        if title_id and file_info.get('title_id') != title_id and file_info.get('app_id') != title_id:
            continue
            
        # Use title_id for updates/DLC, app_id for base games
        if file_info['type'] == APP_TYPE_BASE:
            key = (file_info['app_id'], file_info['type'])
        else:
            key = (file_info['title_id'], file_info['type'])
            
        if key not in files_by_title_type:
            files_by_title_type[key] = []
        
        files_by_title_type[key].append(file_info)
    
    duplicates = []
    
    for (tid, ftype), files in files_by_title_type.items():
        if len(files) <= 1:
            continue
            
        # Get title info
        title_info = get_game_info(tid)
        if title_info is None:
            title_info = {'name': 'Unknown'}
        
        if ftype == APP_TYPE_BASE:
            # For BASE games, they should all be v0, so check for exact duplicates by size
            size_groups = {}
            for file in files:
                size = file.get('size', 0)
                if size not in size_groups:
                    size_groups[size] = []
                size_groups[size].append(file)
            
            # Check each size group for duplicates
            for size, same_size_files in size_groups.items():
                if len(same_size_files) > 1:
                    # Sort by filename to keep the one with the simplest/cleanest name
                    sorted_by_name = sorted(same_size_files, key=lambda x: len(x.get('filename', '')))
                    
                    # Keep the first one, mark others as duplicates
                    for file in sorted_by_name[1:]:
                        duplicates.append({
                            'id': file['id'],
                            'filepath': file['filepath'],
                            'filename': file.get('filename', ''),
                            'title_id': tid,
                            'title_name': title_info.get('name', 'Unknown'),
                            'type': 'Base',
                            'version': file.get('version', 0),
                            'size': file.get('size', 0),
                            'latest_version': file.get('version', 0),
                            'kept_file': sorted_by_name[0].get('filename', ''),
                            'reason': f"Duplicate base game (identical file, keeping: {sorted_by_name[0].get('filename', 'shortest name')})"
                        })
                        
        elif ftype == APP_TYPE_UPD:
            # For updates, keep only the newest version
            sorted_files = sorted(files, 
                                key=lambda x: int(x.get('version', 0)) if x.get('version') else 0, 
                                reverse=True)
            
            # Group by version to handle multiple files with same version
            version_groups = {}
            for file in sorted_files:
                ver = file.get('version', 0)
                if ver not in version_groups:
                    version_groups[ver] = []
                version_groups[ver].append(file)
            
            # Keep only one file per version (preferring shortest filename)
            kept_versions = {}
            for ver, ver_files in version_groups.items():
                if len(ver_files) > 1:
                    # Multiple files with same version, keep the one with shortest name
                    sorted_by_name = sorted(ver_files, key=lambda x: len(x.get('filename', '')))
                    kept_versions[ver] = sorted_by_name[0]
                    
                    # Mark others as duplicates
                    for file in sorted_by_name[1:]:
                        duplicates.append({
                            'id': file['id'],
                            'filepath': file['filepath'],
                            'filename': file.get('filename', ''),
                            'title_id': tid,
                            'title_name': title_info.get('name', 'Unknown'),
                            'type': 'Update',
                            'version': file.get('version', 0),
                            'size': file.get('size', 0),
                            'latest_version': sorted_files[0].get('version', 0),
                            'kept_file': sorted_by_name[0].get('filename', ''),
                            'reason': f"Duplicate update file v{ver} (keeping: {sorted_by_name[0].get('filename', 'shortest name')})"
                        })
                else:
                    kept_versions[ver] = ver_files[0]
            
            # Now check for older versions
            sorted_versions = sorted(kept_versions.keys(), reverse=True)
            if len(sorted_versions) > 1:
                latest_version = sorted_versions[0]
                for ver in sorted_versions[1:]:
                    file = kept_versions[ver]
                    duplicates.append({
                        'id': file['id'],
                        'filepath': file['filepath'],
                        'filename': file.get('filename', ''),
                        'title_id': tid,
                        'title_name': title_info.get('name', 'Unknown'),
                        'type': 'Update',
                        'version': file.get('version', 0),
                        'size': file.get('size', 0),
                        'latest_version': latest_version,
                        'kept_file': kept_versions[latest_version].get('filename', ''),
                        'reason': f"Older update version (keeping latest: v{latest_version})"
                    })
                    
        else:  # DLC
            # For DLC, check both version and size
            # First remove duplicates with same app_id and size
            seen_dlc = {}
            for file in files:
                dlc_key = (file.get('app_id'), file.get('size', 0))
                if dlc_key not in seen_dlc:
                    seen_dlc[dlc_key] = []
                seen_dlc[dlc_key].append(file)
            
            for (dlc_app_id, size), dlc_files in seen_dlc.items():
                if len(dlc_files) > 1:
                    # Sort by filename to keep the cleanest name
                    sorted_by_name = sorted(dlc_files, key=lambda x: len(x.get('filename', '')))
                    
                    for file in sorted_by_name[1:]:
                        duplicates.append({
                            'id': file['id'],
                            'filepath': file['filepath'],
                            'filename': file.get('filename', ''),
                            'title_id': tid,
                            'title_name': title_info.get('name', 'Unknown'),
                            'type': 'DLC',
                            'version': file.get('version', 0),
                            'size': file.get('size', 0),
                            'latest_version': file.get('version', 0),
                            'kept_file': sorted_by_name[0].get('filename', ''),
                            'reason': f"Duplicate DLC file (identical content, keeping: {sorted_by_name[0].get('filename', 'shortest name')})"
                        })
    
    return duplicates


def find_duplicate_updates(title_id=None):
    """Find update files that have newer versions available"""
    # This is now a wrapper for backward compatibility
    all_duplicates = find_all_duplicates(title_id)
    # Filter only update duplicates
    return [d for d in all_duplicates if d['type'] == 'Update']


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


def get_missing_content(library_paths=None):
    """Get all missing content (base games, updates, and DLCs)"""
    all_files = get_all_titles_from_db()
    
    # Group files by title_id
    titles_data = {}
    
    for file_info in all_files:
        # Skip if library path specified and file not in that library
        if library_paths and file_info['library'] not in library_paths:
            continue
            
        # Determine the main title_id for grouping
        if file_info['type'] == APP_TYPE_BASE:
            group_id = file_info['app_id']
        else:
            group_id = file_info['title_id']
            
        if group_id not in titles_data:
            titles_data[group_id] = {
                'title_id': group_id,
                'has_base': False,
                'has_updates': [],
                'has_dlcs': [],
                'files': []
            }
        
        titles_data[group_id]['files'].append(file_info)
        
        if file_info['type'] == APP_TYPE_BASE:
            titles_data[group_id]['has_base'] = True
        elif file_info['type'] == APP_TYPE_UPD:
            titles_data[group_id]['has_updates'].append(file_info['version'])
        elif file_info['type'] == APP_TYPE_DLC:
            titles_data[group_id]['has_dlcs'].append(file_info['app_id'])
    
    missing_content = {
        'missing_base': [],
        'missing_updates': [],
        'missing_dlc': [],
        'summary': {
            'total_missing_base': 0,
            'total_missing_updates': 0,
            'total_missing_dlc': 0,
            'total_size_needed': 0
        }
    }
    
    # Check each title for missing content
    for title_id, title_data in titles_data.items():
        title_info = get_game_info(title_id)
        if title_info is None:
            title_info = {'name': 'Unknown', 'iconUrl': '', 'bannerUrl': ''}
        
        # Check for missing base game (has DLC/updates but no base)
        if not title_data['has_base'] and (title_data['has_updates'] or title_data['has_dlcs']):
            missing_content['missing_base'].append({
                'title_id': title_id,
                'name': title_info.get('name', 'Unknown'),
                'iconUrl': title_info.get('iconUrl', ''),
                'bannerUrl': title_info.get('bannerUrl', ''),
                'has_updates': len(title_data['has_updates']) > 0,
                'has_dlcs': len(title_data['has_dlcs']) > 0,
                'owned_files': title_data['files']
            })
            missing_content['summary']['total_missing_base'] += 1
        
        # Check for missing updates
        if title_data['has_base'] or title_data['has_updates']:
            library_status = get_library_status(title_id)
            
            if not library_status.get('has_latest_version', True):
                latest_version = None
                owned_versions = title_data['has_updates']
                
                # Get all available versions
                if library_status.get('version'):
                    all_versions = library_status['version']
                    latest_version = all_versions[-1]['version'] if all_versions else None
                    
                    missing_versions = []
                    for ver in all_versions:
                        if not ver.get('owned', False) and str(ver['version']) not in [str(v) for v in owned_versions]:
                            missing_versions.append({
                                'version': ver['version'],
                                'release_date': ver.get('release_date', 'Unknown')
                            })
                    
                    if missing_versions:
                        missing_content['missing_updates'].append({
                            'title_id': title_id,
                            'name': title_info.get('name', 'Unknown'),
                            'iconUrl': title_info.get('iconUrl', ''),
                            'bannerUrl': title_info.get('bannerUrl', ''),
                            'current_version': max(owned_versions) if owned_versions else 0,
                            'latest_version': latest_version,
                            'missing_versions': missing_versions,
                            'has_base': title_data['has_base']
                        })
                        missing_content['summary']['total_missing_updates'] += len(missing_versions)
        
        # Check for missing DLC
        if title_data['has_base']:
            all_existing_dlcs = get_all_existing_dlc(title_id)
            owned_dlcs = title_data['has_dlcs']
            
            if all_existing_dlcs:
                missing_dlcs = []
                for dlc_id in all_existing_dlcs:
                    if dlc_id not in owned_dlcs:
                        dlc_info = get_game_info(dlc_id)
                        if dlc_info:
                            missing_dlcs.append({
                                'app_id': dlc_id,
                                'name': dlc_info.get('name', f'DLC {dlc_id}')
                            })
                
                if missing_dlcs:
                    missing_content['missing_dlc'].append({
                        'title_id': title_id,
                        'name': title_info.get('name', 'Unknown'),
                        'iconUrl': title_info.get('iconUrl', ''),
                        'bannerUrl': title_info.get('bannerUrl', ''),
                        'missing_dlcs': missing_dlcs,
                        'total_dlc': len(all_existing_dlcs),
                        'owned_dlc': len(owned_dlcs)
                    })
                    missing_content['summary']['total_missing_dlc'] += len(missing_dlcs)
    
    return missing_content
