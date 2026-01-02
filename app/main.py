from nicegui import ui
import os

@ui.page('/')
def main_page():
    # Header Bereich
    with ui.header().classes(replace='row items-center') as header:
        ui.label('FixundFertig').classes('text-2xl font-bold text-white')
        ui.label('Financial OS').classes('text-sm text-gray-200 ml-2')

    # Main Content
    with ui.column().classes('w-full items-center justify-center q-pa-md'):
        
        ui.label('System Status: Online').classes('text-xl font-bold text-green-500 q-mb-md')
        
        with ui.card().classes('w-full max-w-lg'):
            ui.label('Aktuelle Übersicht').classes('text-lg font-bold q-mb-sm')
            ui.separator()
            # Platzhalter für Daten
            ui.label('Warte auf Daten von n8n...').classes('text-gray-500 italic q-mt-md')

        with ui.row().classes('q-mt-xl'):
            ui.button('Rechnungen scannen', on_click=lambda: ui.notify('Trigger an n8n gesendet!')).props('icon=document_scanner color=primary')
            ui.button('Bankdaten abrufen', on_click=lambda: ui.notify('API Call gestartet...')).props('icon=account_balance color=secondary')

# Start der App
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='FixundFertig', port=8080, favicon='🚀', reload=True)
