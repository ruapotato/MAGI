import json
import os
import time
from gi.repository import GLib, Gtk, Gdk
from pathlib import Path

# Theme definitions from settings.py
MAGI_THEMES = {
    "Plain": {
        "panel_bg": "#ffffff",
        "panel_fg": "#000000",
        "button_bg": "#f0f0f0",
        "button_hover": "#e0e0e0",
        "button_active": "#d0d0d0",
        "launcher_bg": "#2c71cc",
        "accent": "#2c71cc",
        "entry_bg": "#ffffff",
        "entry_fg": "#000000",
        "entry_border": "#cccccc",
        "entry_focus": "#2c71cc",
        "selection_bg": "#2c71cc",
        "selection_fg": "#ffffff",
        "link": "#0066cc",
        "error": "#cc0000",
        "subtitle_fg": "#666666"
    },
    "Tokyo Night": {
        "panel_bg": "#1a1b26",
        "panel_fg": "#c0caf5",
        "button_bg": "#24283b",
        "button_hover": "#414868",
        "button_active": "#565f89",
        "launcher_bg": "#bb9af7",
        "accent": "#7aa2f7",
        "entry_bg": "#1f2335",
        "entry_fg": "#c0caf5",
        "entry_border": "#414868",
        "entry_focus": "#7aa2f7",
        "selection_bg": "#7aa2f7",
        "selection_fg": "#1a1b26",
        "link": "#73daca",
        "error": "#f7768e",
        "subtitle_fg": "#a9b1d6"
    },
    "Forest": {
        "panel_bg": "#2b3328",
        "panel_fg": "#e4dfd2",
        "button_bg": "#3a4637",
        "button_hover": "#4f6146",
        "button_active": "#546c4d",
        "launcher_bg": "#a7c080",
        "accent": "#83c092",
        "entry_bg": "#323d2f",
        "entry_fg": "#e4dfd2",
        "entry_border": "#4f6146",
        "entry_focus": "#a7c080",
        "selection_bg": "#a7c080",
        "selection_fg": "#2b3328",
        "link": "#83c092",
        "error": "#e67e80",
        "subtitle_fg": "#d3c6aa"
    }
}

class ThemeManager:
    """Centralized theme management for MAGI applications"""
    _instance = None
    _config_path = os.path.expanduser("~/.config/magi/config.json")
    _config_mtime = 0
    _watchers = []
    _watch_source_id = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the theme manager"""
        self.themes = MAGI_THEMES
        self._load_config()
        self._setup_watcher()
    
    def _load_config(self):
        """Load configuration from file"""
        try:
            with open(self._config_path) as f:
                self.config = json.load(f)
                self._config_mtime = os.path.getmtime(self._config_path)
        except Exception as e:
            print(f"Theme manager config load error: {e}")
            self.config = {"magi_theme": "Plain"}
    
    def _setup_watcher(self):
        """Set up config file watching"""
        if self._watch_source_id is None:
            self._watch_source_id = GLib.timeout_add(1000, self._check_config)
    
    def _check_config(self):
        """Check for config file changes"""
        try:
            current_mtime = os.path.getmtime(self._config_path)
            if current_mtime > self._config_mtime:
                self._load_config()
                self._notify_watchers()
        except Exception as e:
            print(f"Config check error: {e}")
        return True  # Keep the timeout active
    
    def _notify_watchers(self):
        """Notify all registered watchers of theme changes"""
        theme_name = self.config.get('magi_theme', 'Plain')
        theme = self.themes.get(theme_name, self.themes['Plain'])
        
        # Create CSS provider
        css = self._generate_css(theme)
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        
        # Update all watchers
        for weak_window in self._watchers[:]:
            window = weak_window()
            if window:
                display = window.get_display()
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
            else:
                self._watchers.remove(weak_window)
    
    def _generate_css(self, theme):
        """Generate CSS from theme"""
        return f"""
        /* Override libadwaita default background colors */
        .background {{
            background-color: {theme['panel_bg']};
            color: {theme['panel_fg']};
        }}
        
        .navigationview {{
            background-color: {theme['panel_bg']};
        }}

        preferencespage > scrolledwindow > viewport > box > clamp > box,
        preferencespage > box > box,
        preferencespage box.content,
        preferencespage > scrolledwindow > viewport {{
            background-color: {theme['panel_bg']};
        }}

        preferencespage box.content {{
            background-color: {theme['panel_bg']};
        }}

        box.content {{
            background-color: {theme['panel_bg']};
        }}

        .preferences-page {{
            background-color: {theme['panel_bg']};
        }}

        row {{
            background-color: {theme['button_bg']};
            color: {theme['panel_fg']};
            border-radius: 6px;
            margin: 2px 0;
        }}

        row:hover {{
            background-color: {theme['button_hover']};
        }}

        row label {{
            color: {theme['panel_fg']};
        }}

        preferencesgroup {{
            background-color: {theme['button_bg']};
            border-radius: 12px;
            padding: 6px;
            margin: 6px;
        }}

        preferencesgroup > box > box {{
            background-color: {theme['button_bg']};
        }}

        /* Group headers */
        preferencesgroup > box > box.header {{
            color: {theme['panel_fg']};
        }}

        preferencesgroup > box > box.header label {{
            color: {theme['panel_fg']};
        }}

        preferencesgroup > box > box.header label.subtitle {{
            color: {theme['subtitle_fg']};
        }}

        actionrow {{
            background-color: {theme['entry_bg']};
            color: {theme['panel_fg']};
            border-radius: 6px;
        }}

        actionrow:hover {{
            background-color: {theme['button_hover']};
        }}

        actionrow label {{
            color: {theme['panel_fg']};
        }}
        
        actionrow .subtitle {{
            color: {theme['subtitle_fg']};
        }}

        /* Button Styling */
        button {{
            background-color: {theme['button_bg']};
            color: {theme['panel_fg']};
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid alpha(currentColor, 0.1);
            box-shadow: 0 1px 2px alpha(black, 0.1);
        }}
        
        button:hover {{
            background-color: {theme['button_hover']};
            transform: translateY(-1px);
            transition: all 200ms ease;
        }}
        
        button:active {{
            background-color: {theme['button_active']};
            transform: translateY(0px);
        }}

        /* Entry/TextField Styling */
        entry {{
            background-color: {theme['entry_bg']};
            color: {theme['entry_fg']};
            border: 1px solid {theme['entry_border']};
            border-radius: 6px;
            padding: 8px;
            caret-color: {theme['entry_fg']};
        }}
        
        entry:focus {{
            border-color: {theme['entry_focus']};
            box-shadow: 0 0 0 2px alpha({theme['entry_focus']}, 0.3);
        }}

        /* Header styling */
        headerbar {{
            background-color: {theme['button_bg']};
            color: {theme['panel_fg']};
        }}

        headerbar * {{
            color: {theme['panel_fg']};
        }}

        headerbar label,
        headerbar title {{
            color: {theme['panel_fg']};
        }}

        /* Title and text styling */
        .title {{
            color: {theme['panel_fg']};
        }}

        .subtitle {{
            color: {theme['subtitle_fg']};
        }}

        label {{
            color: {theme['panel_fg']};
        }}

        /* Navigation sidebar */
        .navigation-sidebar {{
            background-color: {theme['button_bg']};
        }}

        .navigation-sidebar label {{
            color: {theme['panel_fg']};
        }}

        .navigation-sidebar row:selected {{
            background-color: {theme['accent']};
            color: white;
        }}

        .navigation-sidebar row:hover:not(:selected) {{
            background-color: {theme['button_hover']};
        }}

        /* Spinbutton styling */
        spinbutton {{
            background-color: {theme['entry_bg']};
            color: {theme['entry_fg']};
        }}

        spinbutton text {{
            color: {theme['entry_fg']};
        }}

        spinbutton button {{
            background-color: {theme['button_bg']};
            color: {theme['panel_fg']};
        }}

        /* Combobox styling */
        combobox {{
            background-color: {theme['entry_bg']};
            color: {theme['entry_fg']};
        }}

        combobox button {{
            background-color: {theme['entry_bg']};
            color: {theme['entry_fg']};
        }}

        combobox * {{
            color: {theme['entry_fg']};
        }}

        /* Menu styling */
        menu {{
            background-color: {theme['button_bg']};
            color: {theme['panel_fg']};
        }}

        menuitem {{
            color: {theme['panel_fg']};
        }}

        menuitem:hover {{
            background-color: {theme['button_hover']};
        }}

        /* Link styling */
        link {{
            color: {theme['link']};
        }}

        link:hover {{
            text-decoration: underline;
        }}

        /* Level bar styling */
        levelbar block {{
            min-height: 10px;
        }}

        levelbar block.filled {{
            background-color: {theme['accent']};
        }}

        /* Selection styling */
        *:selected {{
            background-color: {theme['selection_bg']};
            color: {theme['selection_fg']};
        }}

        /* Scrollbar styling */
        scrollbar {{
            background-color: transparent;
        }}

        scrollbar slider {{
            background-color: alpha({theme['panel_fg']}, 0.2);
            border-radius: 999px;
            min-width: 8px;
            min-height: 8px;
        }}

        scrollbar slider:hover {{
            background-color: alpha({theme['panel_fg']}, 0.4);
        }}

        scrollbar slider:active {{
            background-color: alpha({theme['panel_fg']}, 0.6);
        }}

        /* Window styling */
        window {{
            background-color: {theme['panel_bg']};
            color: {theme['panel_fg']};
        }}

        /* Message styling for LLM Menu */
        .user-message {{
            background-color: {theme['button_bg']};
            color: {theme['panel_fg']};
            border-radius: 6px;
            padding: 8px;
        }}

        .assistant-message {{
            background-color: {theme['entry_bg']};
            color: {theme['entry_fg']};
            border-radius: 6px;
            padding: 8px;
        }}

        .code-block {{
            background-color: {theme['button_bg']};
            color: {theme['panel_fg']};
            font-family: monospace;
            padding: 8px;
            border-radius: 6px;
        }}

        /* Monitor and Clock labels for Panel */
        .monitor-label {{
            color: {theme['panel_fg']};
        }}

        .clock-label {{
            color: {theme['panel_fg']};
        }}

        /* Recording state */
        .recording {{
            color: {theme['error']};
        }}

        /* Workspace buttons */
        .active-workspace {{
            background-color: {theme['accent']};
            color: {theme['selection_fg']};
        }}

        /* Launcher button */
        .launcher-button {{
            background-color: {theme['launcher_bg']};
            color: {theme['selection_fg']};
            font-weight: bold;
        }}
        """
    
    def register_window(self, window):
        """Register a window for theme updates"""
        from weakref import ref
        self._watchers.append(ref(window))
        self._notify_watchers()  # Apply theme immediately
    
    def get_current_theme(self):
        """Get current theme name"""
        return self.config.get('magi_theme', 'Plain')
    
    def get_theme_colors(self):
        """Get current theme colors"""
        theme_name = self.get_current_theme()
        return self.themes.get(theme_name, self.themes['Plain'])
