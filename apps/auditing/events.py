# This file is the single source of truth for event types.
# The application will synchronize the Event model in the database
# with the contents of this list on startup.

EVENT_DEFINITIONS = [
    {"identifier": "NEW_DEVICE", "name": "Создано новое устройство"},
    {"identifier": "DATA_RECEIVED", "name": "Получены новые данные с датчика"},
    {"identifier": "CONFIG_FETCHED", "name": "Запрошена конфигурация датчика"},
    {"identifier": "ADMIN_LOGIN", "name": "Выполнен вход в панель администратора"},
    {"identifier": "DASHBOARD_VIEWED", "name": "Просмотрена панель мониторинга"},
    {"identifier": "DOS_DETECTED", "name": "Обнаружена DoS-атака"},
]
