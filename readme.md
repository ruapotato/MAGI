# MAGI OS - Machine Augmented GTK Interface
> An AI-native Linux distribution with deep LLM integration

[![Website](https://img.shields.io/badge/Website-255.one-blue)](https://255.one)

## Overview
MAGI OS is an experimental Linux distribution that deeply integrates AI capabilities into the core desktop experience. Built on Debian and MATE/GTK technologies, it provides a complete operating system designed for exploring new paradigms of human-AI interaction in desktop computing.

## Key Features
- 🧠 Local LLM integration via Ollama
- 🎤 Voice interface with Whisper
- 🖥️ Custom GTK4-based shell
- 🔒 Privacy-focused (all AI runs locally)
- ⚡ NVIDIA GPU acceleration support

## System Requirements
- CPU: x86_64 processor
- RAM: 16GB minimum (32GB recommended)
- GPU: NVIDIA GTX 1060 or better
- VRAM: 8GB minimum (24GB recommended)
- Storage: 30GB minimum

## Quick Start

### Download Pre-built ISO
Visit [255.one](https://255.one/?page_id=15) to download the latest MAGI OS ISO.

### Building from Source
MAGI OS can be built on any Debian-based system:

```bash
# Clone the repository
git clone https://github.com/ruapotato/MAGI
cd MAGI

# For local installation
./setup.sh

# To build the ISO (requires root)
sudo ./build.sh
```

The build process will:
1. Set up a clean build environment
2. Download required packages and drivers
3. Configure system components
4. Create a bootable ISO

The resulting ISO will be in the `magi-os-build` directory.

## Architecture

### Core Components
- **MAGI Shell**: Custom GTK3-based desktop environment
- **Ollama**: Local LLM integration
- **Whisper**: Speech-to-text processing
- **MATE**: Base desktop components
- **NVIDIA**: GPU acceleration stack

### AI Integration
- Context-aware command interpretation
- Voice control interface
- Local LLM processing
- Task automation capabilities
- Adaptive workspace management

## Configuration

### System Settings
Edit `~/.config/magi/config.json`:
```json
{
    "panel_height": 28,
    "workspace_count": 4,
    "enable_effects": true,
    "enable_ai": true,
    "terminal": "mate-terminal",
    "launcher": "mate-panel --run-dialog",
    "background": "/usr/share/magi/backgrounds/default.png",
    "ollama_model": "mistral",
    "whisper_endpoint": "http://localhost:5000/transcribe",
    "sample_rate": 16000
}
```

## Development Status

### Implemented
- [x] Basic desktop environment
- [x] Window management
- [x] Session handling
- [x] Local LLM integration
- [x] Voice recognition
- [x] Context system
- [x] NVIDIA driver support
- [x] ISO building

### Coming Soon
- [ ] Installer
- [ ] Natural language command interface
- [ ] AI-powered agents
- [ ] Tokyo Night theme

## Contributing
MAGI OS is an experimental project and we welcome contributions:
- Feature suggestions
- Code contributions
- Documentation improvements
- Testing and bug reports
- Design ideas
- Use case examples

## Security Notes
- All AI processing runs locally
- No data leaves your system
- Models can be audited and replaced
- Standard Linux security model
- Regular security updates via Debian base

## License
Copyright (C) 2024 David Hamner

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

## Contact & Community
- Website: [255.one](https://255.one)
- Email: ke7oxh@gmail.com
- GitHub Issues: [Project Issues](https://github.com/ruapotato/MAGI/issues)

## Project Status
Current Stage: **Public Alpha Test**
- Basic functionality working
- Active development
- Seeking community feedback
- Not recommended for production use

---
*MAGI OS is a research project exploring the future of AI-integrated computing environments. While functional, it should be considered experimental software.*
