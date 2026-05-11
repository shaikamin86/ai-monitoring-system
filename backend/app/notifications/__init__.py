from app.notifications.dispatcher import NotificationDispatcher

_dispatcher: NotificationDispatcher | None = None


def get_dispatcher() -> NotificationDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
