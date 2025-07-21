# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ownfoil is a Nintendo Switch library manager and self-hosted Tinfoil shop written in Python using Flask. It manages Switch game files (NSP, NSZ, XCI, XCZ), provides a web interface for administration, and creates a Tinfoil-compatible shop interface.

## Key Architecture

- **Backend**: Flask application with SQLAlchemy database
- **Frontend**: Server-side rendered HTML templates with Jinja2
- **File Processing**: NSTools submodule for Switch file handling
- **Real-time Updates**: Watchdog for file system monitoring
- **Deployment**: Docker-first with Kubernetes/Helm support

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (runs on port 8465)
python app/app.py
```

### Docker Development
```bash
# Build Docker image
docker build -t ownfoil .

# Run with docker-compose
docker-compose up -d

# Run with docker directly
docker run -d -p 8465:8465 -v /your/game/directory:/games -v /your/config/directory:/app/config --name ownfoil ownfoil
```

### NSTools Submodule
```bash
# Initialize if not cloned with --recurse-submodules
git submodule update --init --recursive

# Build NSTools (if needed)
cd app/NSTools/build
./setup-build.sh
```

## Important Notes

- **No test suite**: The project currently has no automated tests
- **No linting configuration**: No code quality tools are configured
- **Port**: Application runs on port 8465 by default
- **User permissions**: Docker uses PUID/PGID environment variables (default 1000:1000)
- **Configuration**: Stored in `/app/config` directory
- **Game files**: Mounted to `/games` in container

## Core Application Structure

- `app/app.py`: Main Flask application entry point
- `app/auth.py`: User authentication (Flask-Login)
- `app/shop.py`: Tinfoil shop generation with encryption
- `app/library.py`: Game library scanning and management (includes duplicate detection, organization, missing content)
- `app/titles.py`: Title identification logic
- `app/file_watcher.py`: Real-time file monitoring
- `app/db.py`: SQLAlchemy database models
- `app/settings.py`: Configuration management
- `app/templates/missing.html`: Missing content page template

## Key Features to Understand

1. **Multi-user Authentication**: Admin and guest users can be created via environment variables or web UI
2. **Library Scanning**: Automatically identifies Switch games using decryption or filename patterns
3. **Shop Encryption**: Supports RSA/AES encryption for Tinfoil compatibility
4. **Real-time Updates**: Watchdog monitors directories for file changes
5. **Title Database**: Integrates with external title databases for game identification
6. **Missing Content Page**: Shows missing base games, updates, and DLCs at `/missing`
7. **Duplicate Detection**: Find and remove duplicate game files (older updates, identical files)
8. **Library Organization**: Reorganize files into structured folders (GameName/BASE, GameName/UPDATES, GameName/DLC)

## New Features Added

### Library Management
- **Organize Library**: Restructure files into organized folders (Settings → Library → Organize)
  - Creates GameName/BASE, GameName/UPDATES, GameName/DLC structure
  - Handles duplicate files gracefully
  - Cleans up empty directories after organization
  
- **Duplicate Detection**: Find and remove duplicate files (Settings → Library → Cleanup)
  - Detects older update versions
  - Finds duplicate base games and DLCs (same file size)
  - Safe deletion with dry-run option
  
- **Missing Content Page**: View all missing content at `/missing`
  - Shows games without base files (orphaned DLC/updates)
  - Lists games with available updates
  - Displays missing DLC for owned games
  - Export missing content list as text file

## Security Considerations

- Flask secret key must be properly configured for production
- User authentication supports admin/regular roles
- Shop can be public or private (requiring authentication)
- Supports encrypted shop responses for Tinfoil