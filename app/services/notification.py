from sqlalchemy.orm import Session
from app.models.notification import Notification

class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        type: str = "info",
        link: str = None
    ) -> Notification:
        """
        Internal utility for creating notifications.
        """
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def notify_user(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        type: str = "info",
        link: str = None
    ):
        """
        Standardized notification trigger.
        """
        return NotificationService.create_notification(db, user_id, title, message, type, link)
