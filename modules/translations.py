"""
Translation module for multi-language support
"""

translations = {
    'de': {
        # Web Interface
        'app_title': 'Paperoo',
        'app_subtitle': 'Drucke deine Aufgaben sofort auf Bondrucker',
        'task_description': 'Aufgabenbeschreibung',
        'task_placeholder': 'Gib deine Aufgabe hier ein...',
        'priority_level': 'Prioritätsstufe',
        'priority_low': 'Niedrig',
        'priority_medium': 'Mittel',
        'priority_normal': 'Normal',
        'priority_high': 'Hoch',
        'priority_urgent': 'Dringend',
        'print_button': 'ToDo Drucken',
        'printing': 'Drucke...',
        'printer_config': 'Drucker-Konfiguration',
        'refresh': 'Aktualisieren',
        'enable_motivation': 'KI-Motivationsspruch aktivieren',
        'motivation_subtitle': 'Nutzt OpenAI für personalisierte Motivation',
        'language_label': 'Sprache',
        'online': 'Online',
        'offline': 'Offline',
        'network_printer': 'Netzwerkdrucker',
        'serial_ports': 'Serielle Ports',
        'usb_printers': 'USB Drucker',
        'active': 'Aktiv',
        'enter_ip': 'IP-Adresse eingeben (z.B. 192.168.1.100)',
        'no_printers': 'Keine Drucker gefunden. Bitte einen Drucker anschließen und aktualisieren.',
        'printer_saved': '✅ Drucker-Konfiguration gespeichert!',
        'print_success': '✅ ToDo erfolgreich gedruckt!',
        'print_error': '❌ Druckfehler',
        'please_enter_task': 'Bitte eine Aufgabenbeschreibung eingeben',
        'please_enter_ip': 'Bitte eine IP-Adresse für den Netzwerkdrucker eingeben',
        'failed_save_printer': 'Drucker-Konfiguration konnte nicht gespeichert werden',
        'failed_print': 'ToDo konnte nicht gedruckt werden',
        'loading_printers': 'Lade Drucker...',
        'failed_load_printers': 'Drucker konnten nicht geladen werden',
        'error_loading_printers': 'Fehler beim Laden der Drucker',
        'motivation_enabled': '✅ KI-Motivation aktiviert',
        'motivation_disabled': 'KI-Motivation deaktiviert',
        'create_new_todo': 'Neue Aufgabe erstellen',
        
        # Login/Auth
        'login_subtitle': 'Bitte anmelden, um fortzufahren',
        'username': 'Benutzername',
        'password': 'Passwort',
        'remember_me': '30 Tage angemeldet bleiben',
        'login_button': 'Anmelden',
        'logout': 'Abmelden',
        'invalid_credentials': 'Ungültiger Benutzername oder Passwort',
        'rate_limit_error': 'Zu viele fehlgeschlagene Anmeldeversuche. Bitte später erneut versuchen.',
        'rate_limit_message': 'Zu viele Versuche. Bitte warten Sie',
        'seconds': 'Sekunden',
        'login_footer': 'Sichere Anmeldung erforderlich für Drucker-Zugriff',
        'print_queued': 'ToDo wurde in die Warteschlange gespeichert',
        
        # Printer output
        'receipt_header': 'AUFGABE',
        'receipt_priority': 'Priorität',
        'receipt_date': 'Datum',
        'receipt_motivation_default': 'Pack es an!',
        
        # Priority names for receipt
        'priority_1': 'Niedrig',
        'priority_2': 'Mittel',
        'priority_3': 'Normal',
        'priority_4': 'Hoch',
        'priority_5': 'Dringend',
    },
    'en': {
        # Web Interface
        'app_title': 'Paperoo',
        'app_subtitle': 'Print your tasks instantly on receipt paper',
        'task_description': 'Task Description',
        'task_placeholder': 'Enter your task here...',
        'priority_level': 'Priority Level',
        'priority_low': 'Low',
        'priority_medium': 'Medium',
        'priority_normal': 'Normal',
        'priority_high': 'High',
        'priority_urgent': 'Urgent',
        'print_button': 'Print ToDo',
        'printing': 'Printing...',
        'printer_config': 'Printer Configuration',
        'refresh': 'Refresh',
        'enable_motivation': 'Enable AI Motivational Quote',
        'motivation_subtitle': 'Uses OpenAI to generate personalized motivation',
        'language_label': 'Language',
        'online': 'Online',
        'offline': 'Offline',
        'network_printer': 'Network Printer',
        'serial_ports': 'Serial Ports',
        'usb_printers': 'USB Printers',
        'active': 'Active',
        'enter_ip': 'Enter IP address (e.g., 192.168.1.100)',
        'no_printers': 'No printers detected. Please connect a printer and refresh.',
        'printer_saved': '✅ Printer configuration saved!',
        'print_success': '✅ ToDo printed successfully!',
        'print_error': '❌ Print error',
        'please_enter_task': 'Please enter a task description',
        'please_enter_ip': 'Please enter an IP address for the network printer',
        'failed_save_printer': 'Failed to save printer configuration',
        'failed_print': 'Failed to print ToDo',
        'loading_printers': 'Loading printers...',
        'failed_load_printers': 'Failed to load printers',
        'error_loading_printers': 'Error loading printers',
        'motivation_enabled': '✅ AI Motivation enabled',
        'motivation_disabled': 'AI Motivation disabled',
        'create_new_todo': 'Create New ToDo',
        
        # Login/Auth
        'login_subtitle': 'Please log in to continue',
        'username': 'Username',
        'password': 'Password',
        'remember_me': 'Remember me for 30 days',
        'login_button': 'Login',
        'logout': 'Logout',
        'invalid_credentials': 'Invalid username or password',
        'rate_limit_error': 'Too many failed login attempts. Please try again later.',
        'rate_limit_message': 'Too many attempts. Please wait',
        'seconds': 'seconds',
        'login_footer': 'Secure login required to access printer interface',
        'print_queued': 'ToDo saved to queue for printing',
        
        # Printer output
        'receipt_header': 'TODO',
        'receipt_priority': 'Priority',
        'receipt_date': 'Date',
        'receipt_motivation_default': 'Get it done!',
        
        # Priority names for receipt
        'priority_1': 'Low',
        'priority_2': 'Medium',
        'priority_3': 'Normal',
        'priority_4': 'High',
        'priority_5': 'Urgent',
    }
}

def get_translation(lang_code: str, key: str, default: str = None) -> str:
    """Get translation for a given key"""
    if lang_code not in translations:
        lang_code = 'de'  # Default to German
    
    return translations[lang_code].get(key, default or key)

def get_all_translations(lang_code: str) -> dict:
    """Get all translations for a language"""
    if lang_code not in translations:
        lang_code = 'de'  # Default to German
    
    return translations[lang_code]