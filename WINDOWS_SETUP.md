# 🪟 Ownfoil Windows Setup Guide

This guide provides Windows-specific instructions for setting up Ownfoil with automation features.

## 📋 Prerequisites

### Required Software

1. **Python 3.8+**
   - Download from [python.org](https://www.python.org/downloads/)
   - ✅ Check "Add Python to PATH" during installation

2. **Git** (optional but recommended)
   - Download from [git-scm.com](https://git-scm.com/download/win)

3. **Visual C++ Build Tools** (for some Python packages)
   - Download from [Microsoft](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   - Install "Desktop development with C++" workload

### Choose Installation Method

- **Option A**: Docker Desktop (Recommended) - [Download](https://www.docker.com/products/docker-desktop/)
- **Option B**: Native Windows Installation

## 🐳 Option A: Docker Installation (Recommended)

### Step 1: Install Docker Desktop

1. Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Start Docker Desktop
3. Ensure WSL 2 backend is enabled (Settings → General)

### Step 2: Setup Ownfoil

1. **Clone repository** (or download ZIP):
   ```powershell
   git clone https://github.com/a1ex4/ownfoil.git
   cd ownfoil
   ```

2. **Run setup**:
   ```powershell
   python setup.py
   ```

3. **Configure environment**:
   ```powershell
   copy .env.example .env
   notepad .env
   ```

4. **Start services**:
   ```powershell
   docker compose -f docker-compose-full.yml up -d
   ```

### Step 3: Access Services

- Ownfoil: http://localhost:8465
- qBittorrent: http://localhost:8080
- Jackett: http://localhost:9117

Continue with [Configuration](#configuration) section below.

## 💻 Option B: Native Windows Installation

### Step 1: Install Python Dependencies

1. **Create virtual environment**:
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```

2. **Install requirements**:
   ```powershell
   pip install -r requirements.txt
   pip install rarfile py7zr  # For archive support
   ```

### Step 2: Install Services

#### qBittorrent
1. Download from [qbittorrent.org](https://www.qbittorrent.org/download.php)
2. Install and run qBittorrent
3. Enable Web UI:
   - Tools → Options → Web UI
   - Check "Web User Interface (Remote control)"
   - Set port: 8080
   - Set username/password

#### Jackett
1. Download from [GitHub Releases](https://github.com/Jackett/Jackett/releases)
2. Extract to `C:\Tools\Jackett`
3. Run `JackettTray.exe`
4. Jackett opens at http://localhost:9117

### Step 3: Configure Paths

1. **Create directories**:
   ```powershell
   mkdir games
   mkdir downloads
   mkdir config
   ```

2. **Update Ownfoil settings**:
   - Set library path to full Windows path: `C:\ownfoil\games`
   - Configure automation URLs as `http://localhost:PORT`

### Step 4: Run Ownfoil

```powershell
python app\app.py
```

Access at http://localhost:8465

## ⚙️ Windows-Specific Configuration

### Enable Long Path Support

Nintendo Switch game files often have long names. Enable long path support:

1. **Run as Administrator**:
   ```powershell
   reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1
   ```

2. **Or use Group Policy**:
   - Run `gpedit.msc`
   - Navigate to: Computer Configuration → Administrative Templates → System → Filesystem
   - Enable "Enable Win32 long paths"

### Archive Extraction Tools

For native Windows, install extraction tools:

1. **7-Zip**: [Download](https://www.7-zip.org/)
2. **WinRAR**: [Download](https://www.rarlab.com/) (trial)

Add to PATH for command-line access.

### File Permissions

Windows handles permissions differently:

1. **Run as Administrator** if permission errors occur
2. **Disable read-only** on game directories:
   ```powershell
   attrib -R "C:\ownfoil\games\*" /S
   ```

## 🔧 Configuration

### Ownfoil Automation Settings

1. Go to Settings → Automation
2. Configure services:
   - **qBittorrent URL**: 
     - Docker: `http://qbittorrent:8080`
     - Native: `http://localhost:8080`
   - **Jackett URL**:
     - Docker: `http://jackett:9117`
     - Native: `http://localhost:9117`

### Processing Options

- **Auto Extract**: ✅ Enabled
- **Auto Organize**: ✅ Enabled
- **Use Hardlinks**: ❌ Disabled (Windows limitations)
- **Delete After Process**: ❌ Disabled (test first)

## 🛠️ Troubleshooting

### Common Issues

1. **"Python not found"**:
   - Reinstall Python with "Add to PATH" checked
   - Or manually add: `C:\Python3X\` and `C:\Python3X\Scripts\` to PATH

2. **"Docker daemon not running"**:
   - Start Docker Desktop
   - Wait for "Docker Desktop is running" in system tray

3. **Permission denied errors**:
   - Run PowerShell as Administrator
   - Check Windows Defender exclusions

4. **Archive extraction fails**:
   - Install Visual C++ Redistributables
   - Use Docker version instead

### Windows Defender

Add exclusions to prevent false positives:

1. Windows Security → Virus & threat protection
2. Manage settings → Add exclusions
3. Add folders:
   - `C:\ownfoil\games`
   - `C:\ownfoil\downloads`

### Firewall

Allow ports through Windows Firewall:

```powershell
netsh advfirewall firewall add rule name="Ownfoil" dir=in action=allow protocol=TCP localport=8465
netsh advfirewall firewall add rule name="qBittorrent" dir=in action=allow protocol=TCP localport=8080
netsh advfirewall firewall add rule name="Jackett" dir=in action=allow protocol=TCP localport=9117
```

## 🚀 Running as Windows Service

### For Native Installation

1. **Install NSSM**:
   ```powershell
   choco install nssm
   ```

2. **Create services**:
   ```powershell
   nssm install Ownfoil "C:\Python39\python.exe" "C:\ownfoil\app\app.py"
   nssm install Jackett "C:\Tools\Jackett\JackettConsole.exe"
   ```

3. **Start services**:
   ```powershell
   nssm start Ownfoil
   nssm start Jackett
   ```

### For Docker

Docker Desktop runs as a service automatically.

## 📊 Performance Tips

1. **Antivirus Exclusions**: Add game directories to exclusions
2. **Disk Choice**: Use SSD for downloads, HDD for long-term storage
3. **RAM Usage**: Close unnecessary applications during extraction
4. **Network**: Use wired connection for better torrent performance

## 🔄 Updating

### Docker Version
```powershell
docker compose -f docker-compose-full.yml pull
docker compose -f docker-compose-full.yml up -d
```

### Native Version
```powershell
git pull
pip install -r requirements.txt --upgrade
```

## 🎮 Tips for Windows Users

1. **Use Docker** when possible - fewer compatibility issues
2. **Short paths** - Install in `C:\ownfoil` not deep directories
3. **Regular backups** - Use Windows Backup or robocopy
4. **Monitor resources** - Task Manager → Performance tab
5. **Schedule scans** - Use Task Scheduler for overnight processing

## 📚 Additional Windows Resources

- [Docker Desktop Documentation](https://docs.docker.com/desktop/windows/)
- [Python on Windows FAQ](https://docs.python.org/3/faq/windows.html)
- [qBittorrent Windows Guide](https://github.com/qbittorrent/qBittorrent/wiki/Windows-compilation)

## 🆘 Getting Help

1. Check Windows Event Viewer for system errors
2. Run `docker logs <container>` for Docker issues
3. Enable debug logging in Ownfoil settings
4. Create issue with Windows version and error details

---

**Note**: Windows support is best-effort. For production use, consider Docker or Linux.