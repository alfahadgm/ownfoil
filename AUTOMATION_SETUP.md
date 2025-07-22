# 🤖 Ownfoil Automation Setup Guide

This guide will help you set up the complete Ownfoil automation stack for automatic game downloading, extraction, and organization.

## 📋 Prerequisites

- Docker and Docker Compose (recommended)
- OR Python 3.8+ for native installation
- At least 10GB free disk space
- Basic understanding of torrents and indexers

## 🚀 Quick Start (Docker)

1. **Clone and setup**:
   ```bash
   git clone https://github.com/a1ex4/ownfoil.git
   cd ownfoil
   python setup.py
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   nano .env
   ```

3. **Start the stack**:
   ```bash
   docker compose -f docker-compose-full.yml up -d
   ```

4. **Access services**:
   - Ownfoil: http://localhost:8465
   - qBittorrent: http://localhost:8080 (admin/adminpass)
   - Jackett: http://localhost:9117

## 🔧 Configuration

### Step 1: Configure Jackett

1. Open Jackett at http://localhost:9117
2. Click "Add Indexer"
3. Add your preferred torrent indexers
4. Note: Public indexers work but private trackers provide better results

### Step 2: Configure Ownfoil Automation

1. Login to Ownfoil at http://localhost:8465
2. Go to Settings → Automation
3. Configure services:
   - **qBittorrent URL**: `http://qbittorrent:8080`
   - **Username**: `admin`
   - **Password**: `adminpass`
   - **Jackett URL**: `http://jackett:9117`
4. Click "Test Connection" for each service
5. Save settings

### Step 3: Configure qBittorrent

1. Open qBittorrent at http://localhost:8080
2. Login with admin/adminpass
3. Go to Settings → Downloads
4. Set Default Save Path: `/downloads/complete`
5. Enable "Create subfolder for torrents"
6. Go to Settings → BitTorrent
7. Set upload limits if needed

## 🎮 Using Automation

### Searching for Games

1. Go to Ownfoil → Missing Content
2. Click "Search in Jackett" on any missing item
3. Jackett opens with pre-filled search query
4. Click on a result to download

### Automatic Processing

Ownfoil now supports multiple methods for processing completed downloads:

#### Method 1: File Watcher (Default)
When downloads complete:
1. **Unpackerr** automatically extracts archives
2. **Ownfoil** detects new files via file watcher
3. Files are organized into proper structure

#### Method 2: qBittorrent Webhook (NEW - Recommended)
Configure qBittorrent to notify Ownfoil when downloads complete:

1. In qBittorrent, go to Settings → Downloads
2. Enable "Run external program on torrent completion"
3. Enter this command:
   ```
   curl -X POST http://ownfoil:8465/api/automation/webhook/qbittorrent -F "%%N=%%N" -F "%%I=%%I" -F "%%F=%%F" -F "%%R=%%R" -F "%%L=%%L"
   ```
   
   For Windows (adjust URL as needed):
   ```
   curl -X POST http://localhost:8465/api/automation/webhook/qbittorrent -F "%%N=%%N" -F "%%I=%%I" -F "%%F=%%F" -F "%%R=%%R" -F "%%L=%%L"
   ```

4. The webhook will:
   - Extract archives if enabled
   - Identify game type (BASE/UPDATE/DLC)
   - Move files to your library path
   - Organize into proper structure:
     ```
     /games/
     ├── Pokemon Scarlet/
     │   ├── BASE/
     │   ├── UPDATES/
     │   └── DLC/
     ```

#### Method 3: Manual API Call
You can also manually trigger processing:
```bash
curl -X POST http://localhost:8465/api/automation/process-download \
  -H "Content-Type: application/json" \
  -d '{
    "path": "D:\\Downloads\\Torrents\\Completed\\nintendo-switch\\GameFolder",
    "name": "Game Name"
  }'
```

## 📁 Directory Structure

```
ownfoil/
├── config/
│   ├── ownfoil/       # Ownfoil configuration
│   ├── qbittorrent/   # qBittorrent configuration
│   ├── jackett/       # Jackett configuration
│   └── unpackerr/     # Unpackerr configuration
├── downloads/         # Download directory
│   └── complete/      # Completed downloads
└── games/            # Organized game library
```

## ⚙️ Advanced Configuration

### Processing Options

In Ownfoil Settings → Automation → Processing Options:

- **Auto Extract**: Automatically extract RAR/ZIP/7Z files
- **Auto Organize**: Organize files into GameName/TYPE structure
- **Use Hardlinks**: Save disk space (requires same filesystem)
- **Delete After Process**: Remove source files after processing
- **Target Library Index**: Which library path to use (0 = first path, 1 = second, etc.)

### Custom Categories

1. In qBittorrent, create category "nintendo-switch"
2. Set category save path to `/downloads/complete/nintendo-switch`
3. Update Ownfoil automation settings with new category

### Multiple Library Paths

1. Add library paths in Ownfoil Settings → Library
2. Mount additional paths in docker-compose.yml:
   ```yaml
   volumes:
     - /mnt/games1:/games
     - /mnt/games2:/games2
   ```

## 🐧 Native Linux Installation

If not using Docker:

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install rarfile py7zr  # Optional for archive support
   ```

2. **Install services**:
   - qBittorrent: `sudo apt install qbittorrent-nox`
   - Jackett: Follow [official guide](https://github.com/Jackett/Jackett)

3. **Configure services** to use local URLs:
   - qBittorrent: `http://localhost:8080`
   - Jackett: `http://localhost:9117`

## 🪟 Windows Installation

See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for Windows-specific instructions.

### Windows qBittorrent Webhook Setup

For Windows users with qBittorrent:

1. **Install curl** (if not already installed):
   - Download from https://curl.se/windows/
   - Or use Windows Package Manager: `winget install curl`

2. **Configure qBittorrent webhook**:
   - Go to Settings → Downloads
   - Enable "Run external program on torrent completion"
   - Use this command (adjust paths as needed):
     ```
     C:\Windows\System32\curl.exe -X POST http://localhost:8465/api/automation/webhook/qbittorrent -F "%%N=%%N" -F "%%I=%%I" -F "%%F=%%F" -F "%%R=%%R" -F "%%L=%%L"
     ```

3. **Alternative: PowerShell webhook** (if curl is not available):
   - Create a PowerShell script `webhook.ps1`:
     ```powershell
     param($N, $I, $F, $R, $L)
     $body = @{
       "%%N" = $N
       "%%I" = $I
       "%%F" = $F
       "%%R" = $R
       "%%L" = $L
     }
     Invoke-WebRequest -Uri "http://localhost:8465/api/automation/webhook/qbittorrent" -Method POST -Body $body
     ```
   - In qBittorrent, use:
     ```
     powershell.exe -ExecutionPolicy Bypass -File "C:\path\to\webhook.ps1" -N "%%N" -I "%%I" -F "%%F" -R "%%R" -L "%%L"
     ```

## 🔍 Troubleshooting

### Connection Issues

1. **"Connection failed" errors**:
   - Ensure all containers are running: `docker ps`
   - Check container logs: `docker logs <container-name>`
   - Verify internal DNS works between containers

2. **Permission errors**:
   - Check PUID/PGID in .env match your user: `id`
   - Fix permissions: `sudo chown -R $(id -u):$(id -g) ./config ./games`

### Processing Issues

1. **Files not organizing**:
   - Check file naming follows format: `Game Name [TitleID][vVersion].nsp`
   - Verify library paths are correctly mounted
   - Check Ownfoil logs for errors

2. **Archives not extracting**:
   - Check Unpackerr logs: `docker logs unpackerr`
   - Verify archive passwords in configuration
   - Ensure enough disk space for extraction

### Performance

1. **Slow downloads**:
   - Check qBittorrent connection settings
   - Verify port forwarding if needed
   - Consider VPN for better peer connectivity

2. **High CPU usage**:
   - Limit simultaneous extractions in Unpackerr
   - Reduce qBittorrent active torrent limits
   - Consider processing schedule during off-hours

## 🛡️ Security Considerations

1. **Change default passwords** immediately
2. **Use reverse proxy** (nginx/traefik) for HTTPS
3. **Restrict access** to local network only
4. **Regular backups** of config directory
5. **Monitor disk usage** to prevent filling

## 📊 Monitoring

### View Logs
```bash
# All services
docker compose -f docker-compose-full.yml logs -f

# Specific service
docker logs -f ownfoil
```

### Service Status
```bash
docker compose -f docker-compose-full.yml ps
```

### Resource Usage
```bash
docker stats
```

## 🔄 Updating

1. **Backup configuration**:
   ```bash
   tar -czf config-backup.tar.gz ./config
   ```

2. **Update images**:
   ```bash
   docker compose -f docker-compose-full.yml pull
   docker compose -f docker-compose-full.yml up -d
   ```

3. **Or use Watchtower** (included in stack with management profile)

## 🎯 Tips & Best Practices

1. **Organize before enabling automation** - Clean your existing library first
2. **Start with dry-run** - Test with delete_after_process disabled
3. **Monitor space usage** - Game files can be large
4. **Use categories** - Separate Switch games from other downloads
5. **Regular maintenance** - Clean completed torrents periodically

## 📚 Additional Resources

- [Ownfoil Documentation](https://github.com/a1ex4/ownfoil)
- [qBittorrent Wiki](https://github.com/qbittorrent/qBittorrent/wiki)
- [Jackett GitHub](https://github.com/Jackett/Jackett)
- [Unpackerr Documentation](https://unpackerr.zip)

---

Need help? Check the [issues](https://github.com/a1ex4/ownfoil/issues) or create a new one!