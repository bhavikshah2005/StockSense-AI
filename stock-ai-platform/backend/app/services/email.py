import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PasswordResetEmail:
    recipient: str
    reset_url: str


class EmailSender:
    """Sends transactional email. Delivery integration is pending."""

    def send_password_reset(self, message: PasswordResetEmail) -> None:
        raise NotImplementedError


class PendingEmailSender(EmailSender):
    """No email provider is configured, so messages are not delivered.

    The reset URL and token are not written to logs.
    """

    def send_password_reset(self, message: PasswordResetEmail) -> None:
        del message
        logger.info("Password reset email was not sent; email delivery is pending")


class RecordingEmailSender(EmailSender):
    """Test double that keeps the latest reset messages in memory."""

    def __init__(self) -> None:
        self.messages: list[PasswordResetEmail] = []

    def send_password_reset(self, message: PasswordResetEmail) -> None:
        self.messages.append(message)


def get_email_sender() -> EmailSender:
    return PendingEmailSender()
