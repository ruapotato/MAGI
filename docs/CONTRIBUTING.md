# Contributors

## Project Lead
- **David Hamner** (ruapotato) - Project creator and maintainer
  - Core system architecture
  - Initial implementation
  - GTK shell development
  - AI integration

## Contributors
- **Avinash Rout** (Avinash24R)
  - Code organization and modularization
  - Documentation improvements
  - Project structure refinement
  
## Testers
- **Firebird**

## Contributing
We welcome contributions from the community! Here are some ways you can help:

### Development Areas
- User Interface Improvements
- Documentation
- Bug Fixes
- New Features
- Testing
- AI Model Integration
- Themes and Visual Design

### Getting Started
1. Install Dependencies:
```bash
sudo apt install xclip wmctrl xdotool x11-utils
```

2. Setup Development Environment:
```bash
# Clone repository
git clone https://github.com/ruapotato/MAGI
cd MAGI

# Install MAGI
./bin/setup.sh
```

3. Common Development Tasks:
- Restart Panel: `killall magi_shell.py && ./bin/start_shell.sh`
- Test Voice: `./bin/start_whisper_server.sh`
- Run Model Manager: `./bin/start_model_manager.sh`

### Code Organization
- `src/magi_shell/` - Core shell components
- `src/utils/` - Standalone utilities and servers
- `bin/` - Scripts and executables
- `setup/` - Installation and build scripts
- `docs/` - Documentation

### Priority Areas
1. Application Launcher Development
2. User Documentation
3. Hardware Support
4. Live USB Installer
5. Desktop Assistant Improvements
6. System Update Mechanism
7. Model Manager Refinements
8. Theme Development
9. Text-to-Speech Alternatives
10. Integration Testing

Join us in building the future of AI-integrated desktop computing!

## Recognition
All contributors will be added to this file. For major contributions, we provide:
- Credit in release notes
- Mention in documentation
- Recognition on project website

## Contact
For questions about contributing, please:
- Open an issue on GitHub
- Email: ke7oxh@gmail.com
- Visit: [255.one](https://255.one)
