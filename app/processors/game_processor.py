import os
import re
import shutil
import platform
import logging
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from enum import Enum

# Third-party imports - these will be optional
try:
    import rarfile
    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False
    
try:
    import py7zr
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False

logger = logging.getLogger(__name__)


class GameType(Enum):
    BASE = "BASE"
    UPDATE = "UPDATES"
    DLC = "DLC"


class ArchiveHandler:
    """Cross-platform archive extraction handler"""
    
    def __init__(self, passwords: List[str] = None):
        self.passwords = passwords or ["", "switch", "nintendo"]
        
    def extract(self, archive_path: str, extract_to: str) -> Tuple[bool, str]:
        """Extract archive to specified directory"""
        archive_path = Path(archive_path)
        extract_to = Path(extract_to)
        
        if not archive_path.exists():
            return False, f"Archive not found: {archive_path}"
            
        # Create extraction directory
        extract_to.mkdir(parents=True, exist_ok=True)
        
        # Determine archive type and extract
        ext = archive_path.suffix.lower()
        
        try:
            if ext in ['.zip']:
                return self._extract_zip(archive_path, extract_to)
            elif ext in ['.rar'] and HAS_RARFILE:
                return self._extract_rar(archive_path, extract_to)
            elif ext in ['.7z'] and HAS_PY7ZR:
                return self._extract_7z(archive_path, extract_to)
            elif ext in ['.tar', '.tar.gz', '.tgz', '.tar.bz2']:
                return self._extract_tar(archive_path, extract_to)
            else:
                return False, f"Unsupported archive format: {ext}"
        except Exception as e:
            return False, f"Extraction failed: {str(e)}"
            
    def _extract_zip(self, archive_path: Path, extract_to: Path) -> Tuple[bool, str]:
        """Extract ZIP archive"""
        for password in self.passwords:
            try:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    if password:
                        zf.setpassword(password.encode())
                    zf.extractall(extract_to)
                    return True, "Successfully extracted ZIP"
            except RuntimeError as e:
                if "Bad password" in str(e):
                    continue
                raise
        return False, "Failed to extract ZIP - incorrect password"
        
    def _extract_rar(self, archive_path: Path, extract_to: Path) -> Tuple[bool, str]:
        """Extract RAR archive"""
        if not HAS_RARFILE:
            return False, "RAR support not available - install rarfile package"
            
        for password in self.passwords:
            try:
                with rarfile.RarFile(archive_path, 'r') as rf:
                    if password:
                        rf.setpassword(password)
                    rf.extractall(extract_to)
                    return True, "Successfully extracted RAR"
            except rarfile.BadRarFile:
                return False, "Invalid RAR file"
            except rarfile.PasswordRequired:
                continue
        return False, "Failed to extract RAR - incorrect password"
        
    def _extract_7z(self, archive_path: Path, extract_to: Path) -> Tuple[bool, str]:
        """Extract 7Z archive"""
        if not HAS_PY7ZR:
            return False, "7Z support not available - install py7zr package"
            
        for password in self.passwords:
            try:
                with py7zr.SevenZipFile(archive_path, 'r', password=password if password else None) as archive:
                    archive.extractall(extract_to)
                    return True, "Successfully extracted 7Z"
            except py7zr.Bad7zFile:
                return False, "Invalid 7Z file"
            except Exception as e:
                if "password" in str(e).lower():
                    continue
                raise
        return False, "Failed to extract 7Z - incorrect password"
        
    def _extract_tar(self, archive_path: Path, extract_to: Path) -> Tuple[bool, str]:
        """Extract TAR archive"""
        try:
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(extract_to)
                return True, "Successfully extracted TAR"
        except Exception as e:
            return False, f"Failed to extract TAR: {str(e)}"


class SwitchGameProcessor:
    """Process Nintendo Switch game files with cross-platform support"""
    
    # Regex patterns for game identification
    TITLE_ID_PATTERN = re.compile(r'\[([0-9A-Fa-f]{16})\]')
    VERSION_PATTERN = re.compile(r'\[v(\d+)\]')
    GAME_EXTENSIONS = {'.nsp', '.nsz', '.xci', '.xcz'}
    
    def __init__(self, config: Dict[str, any]):
        self.config = config
        self.archive_handler = ArchiveHandler(
            passwords=config.get('extract_passwords', [])
        )
        self.platform_info = self._get_platform_info()
        
    def _get_platform_info(self) -> Dict[str, any]:
        """Get platform-specific information"""
        return {
            'system': platform.system(),
            'is_windows': platform.system() == 'Windows',
            'is_linux': platform.system() == 'Linux',
            'is_docker': os.path.exists('/.dockerenv'),
            'supports_hardlinks': platform.system() != 'Windows' or self._check_windows_hardlink_support()
        }
        
    def _check_windows_hardlink_support(self) -> bool:
        """Check if Windows supports hardlinks (requires admin or developer mode)"""
        if platform.system() != 'Windows':
            return False
            
        # Try to create a test hardlink
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = os.path.join(tmpdir, 'test.txt')
                link_file = os.path.join(tmpdir, 'link.txt')
                
                with open(test_file, 'w') as f:
                    f.write('test')
                    
                os.link(test_file, link_file)
                os.unlink(link_file)
                return True
        except:
            return False
            
    def process_directory(self, source_dir: str, target_dir: str, 
                         auto_extract: bool = True, 
                         auto_organize: bool = True,
                         use_hardlinks: bool = True) -> Dict[str, any]:
        """Process all game files in a directory"""
        source_path = Path(source_dir)
        target_path = Path(target_dir)
        
        results = {
            'processed': [],
            'errors': [],
            'archives_extracted': 0,
            'files_organized': 0
        }
        
        if not source_path.exists():
            results['errors'].append(f"Source directory not found: {source_dir}")
            return results
            
        # Step 1: Extract archives if enabled
        if auto_extract:
            archives = self._find_archives(source_path)
            for archive in archives:
                success, message = self._extract_archive(archive, source_path)
                if success:
                    results['archives_extracted'] += 1
                    logger.info(f"Extracted: {archive.name}")
                else:
                    results['errors'].append(f"{archive.name}: {message}")
                    
        # Step 2: Find and organize game files
        if auto_organize:
            game_files = self._find_game_files(source_path)
            for game_file in game_files:
                success, message = self._organize_game_file(
                    game_file, target_path, use_hardlinks
                )
                if success:
                    results['files_organized'] += 1
                    results['processed'].append({
                        'file': str(game_file),
                        'message': message
                    })
                else:
                    results['errors'].append(f"{game_file.name}: {message}")
                    
        return results
        
    def _find_archives(self, directory: Path) -> List[Path]:
        """Find all supported archive files in directory"""
        archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.tar.gz', '.tgz', '.tar.bz2'}
        archives = []
        
        for ext in archive_extensions:
            archives.extend(directory.glob(f'**/*{ext}'))
            
        return archives
        
    def _find_game_files(self, directory: Path) -> List[Path]:
        """Find all Switch game files in directory"""
        game_files = []
        
        for ext in self.GAME_EXTENSIONS:
            game_files.extend(directory.glob(f'**/*{ext}'))
            
        return game_files
        
    def _extract_archive(self, archive: Path, extract_base: Path) -> Tuple[bool, str]:
        """Extract archive to a subdirectory"""
        extract_dir = extract_base / f"{archive.stem}_extracted"
        return self.archive_handler.extract(str(archive), str(extract_dir))
        
    def _identify_game_type(self, filename: str, title_id: str) -> GameType:
        """Identify if file is BASE, UPDATE, or DLC"""
        if not title_id:
            return GameType.BASE
            
        # Check title ID suffix
        suffix = title_id[-3:]
        
        if suffix == '000':
            return GameType.BASE
        elif suffix == '800':
            return GameType.UPDATE
        else:
            return GameType.DLC
            
    def _extract_game_info(self, file_path: Path) -> Dict[str, any]:
        """Extract game information from filename"""
        filename = file_path.name
        
        # Extract title ID
        title_id_match = self.TITLE_ID_PATTERN.search(filename)
        title_id = title_id_match.group(1) if title_id_match else None
        
        # Extract version
        version_match = self.VERSION_PATTERN.search(filename)
        version = version_match.group(1) if version_match else "0"
        
        # Extract game name (everything before the first bracket)
        game_name = filename.split('[')[0].strip()
        
        # Clean up game name
        game_name = re.sub(r'[^\w\s\-\(\)]', '', game_name)
        game_name = game_name.strip()
        
        # Determine game type
        game_type = self._identify_game_type(filename, title_id)
        
        return {
            'name': game_name,
            'title_id': title_id,
            'version': version,
            'type': game_type,
            'filename': filename
        }
        
    def _organize_game_file(self, file_path: Path, target_base: Path, 
                           use_hardlinks: bool) -> Tuple[bool, str]:
        """Organize a game file into the proper directory structure"""
        try:
            # Extract game information
            game_info = self._extract_game_info(file_path)
            
            if not game_info['name']:
                return False, "Could not determine game name"
                
            # Create target directory structure
            game_dir = target_base / game_info['name']
            type_dir = game_dir / game_info['type'].value
            type_dir.mkdir(parents=True, exist_ok=True)
            
            # Target file path
            target_file = type_dir / file_path.name
            
            # Skip if already in correct location
            if file_path == target_file:
                return True, "Already in correct location"
                
            # Skip if target exists
            if target_file.exists():
                # Check if it's the same file
                if file_path.stat().st_size == target_file.stat().st_size:
                    return True, "Identical file already exists at target"
                else:
                    return False, "Different file with same name exists at target"
                    
            # Move or link the file
            if use_hardlinks and self._can_hardlink(file_path, target_file):
                try:
                    os.link(str(file_path), str(target_file))
                    message = f"Hardlinked to {type_dir.relative_to(target_base)}"
                except Exception as e:
                    # Fallback to copy
                    shutil.copy2(str(file_path), str(target_file))
                    message = f"Copied to {type_dir.relative_to(target_base)} (hardlink failed)"
            else:
                # Copy the file
                shutil.copy2(str(file_path), str(target_file))
                message = f"Copied to {type_dir.relative_to(target_base)}"
                
            return True, message
            
        except Exception as e:
            return False, f"Organization failed: {str(e)}"
            
    def _can_hardlink(self, source: Path, target: Path) -> bool:
        """Check if hardlink is possible between source and target"""
        if not self.platform_info['supports_hardlinks']:
            return False
            
        # Check if on same filesystem (required for hardlinks)
        try:
            source_stat = source.stat()
            target_parent_stat = target.parent.stat()
            return source_stat.st_dev == target_parent_stat.st_dev
        except:
            return False
            
    def clean_empty_directories(self, base_dir: str) -> int:
        """Remove empty directories recursively"""
        removed_count = 0
        base_path = Path(base_dir)
        
        # Walk bottom-up to remove empty dirs
        for dirpath, dirnames, filenames in os.walk(base_dir, topdown=False):
            if not dirnames and not filenames:
                try:
                    os.rmdir(dirpath)
                    removed_count += 1
                    logger.info(f"Removed empty directory: {dirpath}")
                except:
                    pass
                    
        return removed_count