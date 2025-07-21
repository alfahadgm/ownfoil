#!/usr/bin/env python3
"""
Ownfoil Automation Setup Script
Cross-platform setup utility for initializing the automation environment
"""

import os
import sys
import platform
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class OwnfoilSetup:
    """Setup utility for Ownfoil automation"""
    
    def __init__(self):
        self.platform = platform.system()
        self.is_docker = os.path.exists('/.dockerenv')
        self.base_dir = Path(__file__).parent
        
    def print_header(self):
        """Print setup header"""
        print("=" * 60)
        print("Ownfoil Automation Setup")
        print(f"Platform: {self.platform}")
        print(f"Python: {sys.version.split()[0]}")
        print(f"Docker: {'Yes' if self.is_docker else 'No'}")
        print("=" * 60)
        print()
        
    def check_requirements(self) -> Dict[str, bool]:
        """Check system requirements"""
        requirements = {
            'python': sys.version_info >= (3, 8),
            'docker': self._check_docker(),
            'docker_compose': self._check_docker_compose(),
            'disk_space': self._check_disk_space(),
        }
        
        return requirements
        
    def _check_docker(self) -> bool:
        """Check if Docker is installed"""
        try:
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
            
    def _check_docker_compose(self) -> bool:
        """Check if Docker Compose is installed"""
        try:
            # Try docker compose (v2)
            result = subprocess.run(['docker', 'compose', 'version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return True
                
            # Try docker-compose (v1)
            result = subprocess.run(['docker-compose', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
            
    def _check_disk_space(self, min_gb: int = 10) -> bool:
        """Check available disk space"""
        stat = os.statvfs(self.base_dir)
        available_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        return available_gb >= min_gb
        
    def create_directories(self, dirs: List[str]):
        """Create required directories"""
        print("Creating directories...")
        for dir_name in dirs:
            dir_path = self.base_dir / dir_name
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"  ✓ Created: {dir_name}")
            else:
                print(f"  • Exists: {dir_name}")
                
    def setup_config_files(self):
        """Setup configuration files"""
        print("\nSetting up configuration files...")
        
        # Copy .env.example to .env if it doesn't exist
        env_example = self.base_dir / '.env.example'
        env_file = self.base_dir / '.env'
        
        if env_example.exists() and not env_file.exists():
            shutil.copy2(env_example, env_file)
            print("  ✓ Created .env from .env.example")
            print("  ! Please edit .env with your settings")
        elif env_file.exists():
            print("  • .env already exists")
            
    def install_python_dependencies(self):
        """Install Python dependencies"""
        print("\nInstalling Python dependencies...")
        
        # Check if in virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        
        if not in_venv and not self.is_docker:
            print("  ! Warning: Not in a virtual environment")
            print("  ! Consider creating one: python -m venv venv")
            
        # Install requirements
        requirements_file = self.base_dir / 'requirements.txt'
        if requirements_file.exists():
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 
                              str(requirements_file)], check=True)
                print("  ✓ Installed base requirements")
            except subprocess.CalledProcessError as e:
                print(f"  ✗ Failed to install requirements: {e}")
                
        # Install optional automation dependencies
        optional_deps = ['rarfile', 'py7zr']
        for dep in optional_deps:
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', dep], 
                             check=True, capture_output=True)
                print(f"  ✓ Installed {dep}")
            except subprocess.CalledProcessError:
                print(f"  • Skipped {dep} (optional)")
                
    def setup_docker_stack(self):
        """Setup Docker stack"""
        print("\nSetting up Docker stack...")
        
        compose_file = self.base_dir / 'docker-compose-full.yml'
        if not compose_file.exists():
            print("  ✗ docker-compose-full.yml not found")
            return
            
        print("  • Starting services (this may take a few minutes)...")
        try:
            # Use docker compose v2 if available, otherwise v1
            compose_cmd = ['docker', 'compose', '-f', str(compose_file), 'up', '-d']
            result = subprocess.run(compose_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                # Try docker-compose v1
                compose_cmd = ['docker-compose', '-f', str(compose_file), 'up', '-d']
                subprocess.run(compose_cmd, check=True)
                
            print("  ✓ Docker services started")
            print("\nServices available at:")
            print("  • Ownfoil: http://localhost:8465")
            print("  • qBittorrent: http://localhost:8080")
            print("  • Jackett: http://localhost:9117")
            
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Failed to start services: {e}")
            
    def setup_windows_specific(self):
        """Windows-specific setup"""
        print("\nWindows-specific setup...")
        
        # Check for Visual C++ Build Tools
        print("  • Checking for Visual C++ Build Tools...")
        print("  ! If archive extraction fails, install:")
        print("    https://visualstudio.microsoft.com/visual-cpp-build-tools/")
        
        # Check for long path support
        print("\n  • Checking long path support...")
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r"SYSTEM\CurrentControlSet\Control\FileSystem")
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            if value == 1:
                print("  ✓ Long paths enabled")
            else:
                print("  ! Long paths disabled. To enable:")
                print("    Run as admin: reg add HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1")
        except:
            print("  • Could not check long path support")
            
    def print_next_steps(self):
        """Print next steps"""
        print("\n" + "=" * 60)
        print("Setup Complete! Next steps:")
        print("=" * 60)
        print("\n1. Edit .env file with your settings")
        print("\n2. Configure Ownfoil:")
        print("   - Go to http://localhost:8465/settings")
        print("   - Navigate to Automation section")
        print("   - Set qBittorrent URL: http://qbittorrent:8080")
        print("   - Set Jackett URL: http://jackett:9117")
        print("   - Use qBittorrent credentials: admin/adminpass")
        print("\n3. Configure Jackett:")
        print("   - Go to http://localhost:9117")
        print("   - Add your preferred indexers")
        print("\n4. Start downloading!")
        print("   - Use the Missing Content page to search")
        print("   - Downloads will be automatically processed")
        
    def run_interactive(self):
        """Run interactive setup"""
        self.print_header()
        
        # Check requirements
        print("Checking requirements...")
        reqs = self.check_requirements()
        for req, status in reqs.items():
            status_str = "✓" if status else "✗"
            print(f"  {status_str} {req}")
            
        if not reqs['python']:
            print("\n✗ Python 3.8+ is required")
            sys.exit(1)
            
        # Ask setup type
        print("\nSetup type:")
        print("1. Docker (recommended)")
        print("2. Native")
        
        if reqs['docker'] and reqs['docker_compose']:
            choice = input("\nSelect option [1]: ").strip() or "1"
        else:
            print("\n! Docker not found, using native setup")
            choice = "2"
            
        # Create directories
        dirs = ['games', 'downloads', 'config', 'config/ownfoil', 
                'config/qbittorrent', 'config/jackett', 'config/unpackerr']
        self.create_directories(dirs)
        
        # Setup config files
        self.setup_config_files()
        
        if choice == "1":
            # Docker setup
            self.setup_docker_stack()
        else:
            # Native setup
            self.install_python_dependencies()
            
            if self.platform == "Windows":
                self.setup_windows_specific()
                
        self.print_next_steps()
        

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Ownfoil Automation Setup')
    parser.add_argument('--non-interactive', action='store_true',
                       help='Run in non-interactive mode')
    parser.add_argument('--docker', action='store_true',
                       help='Force Docker setup')
    parser.add_argument('--native', action='store_true',
                       help='Force native setup')
    
    args = parser.parse_args()
    
    setup = OwnfoilSetup()
    
    if args.non_interactive:
        # Non-interactive mode
        setup.print_header()
        setup.create_directories(['games', 'downloads', 'config'])
        setup.setup_config_files()
        
        if args.docker:
            setup.setup_docker_stack()
        elif args.native:
            setup.install_python_dependencies()
        else:
            # Auto-detect
            reqs = setup.check_requirements()
            if reqs['docker'] and reqs['docker_compose']:
                setup.setup_docker_stack()
            else:
                setup.install_python_dependencies()
    else:
        # Interactive mode
        setup.run_interactive()
        

if __name__ == '__main__':
    main()