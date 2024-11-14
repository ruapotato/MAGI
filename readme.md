# MAGI - Machine Augmented GTK Interface

> An experimental Linux desktop environment designed for AI integration

## Overview

MAGI is a proof-of-concept desktop environment that explores how AI can be deeply integrated into the Linux desktop experience. Built on MATE/GTK technologies, it provides a foundation for experimenting with new ways of human-AI interaction in a desktop environment.

## Vision

MAGI aims to reimagine the desktop environment as an AI-augmented workspace where:

- AI assists with task management and workflow optimization
- Natural language can be used for system interaction
- Intelligent context awareness enhances productivity
- Privacy via local models
- Support for GTX 1060 or better

## Current Status: Early Prototype

This is currently a **technical demo** that implements basic desktop environment functionality as a foundation for AI features. While the core desktop interface works, full OS building is underway.

### What Works Now
- Basic desktop shell with panels and window management
- Workspace switching and window list
- Application launcher and system tray
- Session management and settings integration
- Context-aware LLM integration

### Coming Soon
- Natural language command interface
- AI-powered agents

## Technical Foundation
- **Shell**: Custom GTK3-based interface
- **Backend**: Python with MATE components
- **LLM**: Ollama

## Try It Out

While still in development, you can test the basic shell today on a Debian Bookworm base

```bash
# Clone the repository
git clone [repository-url]
cd magi

# Run the setup script
./setup.sh
```

Then select "MAGI Shell" from your display manager's session list.

## Configuration

Edit `~/.config/magi/config.json` to customize basic settings. AI configuration options coming soon.

## Development Status

- [x] Basic desktop shell
- [x] Window management
- [x] Session handling
- [x] LLM integration framework
- [x] Context awareness system
- [x] Natural language processing
- [x] AI task assistance
- [ ] OS build
- [ ] Local Agent

## Contributing

MAGI is in experimental stages and we welcome:
- Ideas for AI integration
- Thoughts on privacy-preserving AI
- Interface design suggestions
- Code contributions
- Documentation help
- Testing and feedback

## License

Copyright (C) 2024 David Hamner

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

## Contact

David Hamner  
Project Status: Experimental Demo

---
*Note: This is a research project exploring AI integration in desktop environments. Many planned features are still in conceptual stages.*
