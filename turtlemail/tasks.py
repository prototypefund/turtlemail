import datetime
from logging import debug
from django.conf import settings
from django.contrib.gis.db.models import Q
from huey import crontab
from huey.contrib.djhuey import periodic_task, lock_task
from turtlemail.models import (
    ChatMessage,
    Packet,
    Route,
    RouteStep,
    User,
    UserChatMessage,
)
from turtlemail.notification_service import NotificationService
from turtlemail.routing import recalculate_missing_routes
from turtlemail.util import ensure_database_connection


@periodic_task(crontab(minute="*/1"))
@lock_task("recalculate_missing_routes")
@ensure_database_connection
def every_minute():
    packets = Packet.objects.without_valid_route()
    debug("Found %d packets for recalculating routes", len(packets))
    recalculate_missing_routes(packets, datetime.datetime.now(datetime.UTC))


@periodic_task(crontab(minute="*/60"))
@lock_task("send_chat_notifications")
@ensure_database_connection
def send_chat_notifications():
    messages = UserChatMessage.objects.filter(status=ChatMessage.StatusChoices.NEW)
    # avoid double notification. We want to reduce db load with one update call
    notified_users = []
    for message in messages:
        if message.route_step.stay.user == message.author:
            rec_user = message.route_step.next_step.stay.user
            if (
                rec_user not in notified_users
                and rec_user.settings.wants_email_notifications_chat
            ):
                debug(f"Send chat notification email to {rec_user}.")
                NotificationService.send_email_notification_chat(rec_user)
                notified_users.append(rec_user)
        else:
            rec_user = message.route_step.stay.user
            if (
                message.route_step.stay.user not in notified_users
                and rec_user.settings.wants_email_notifications_chat
            ):
                debug(
                    f"Send chat notification email to {message.route_step.stay.user}."
                )
                NotificationService.send_email_notification_chat(
                    message.route_step.stay.user
                )
                notified_users.append(message.route_step.stay.user)
    messages.update(status=ChatMessage.StatusChoices.NOTIFIED)


@periodic_task(crontab(minute="*/15"))
@lock_task("send_requests_notifications")
@ensure_database_connection
def send_requests_notifications():
    resend_interval_filter = Q(stay__route_steps__notified_at__isnull=True) | Q(
        stay__route_steps__notified_at__lte=datetime.datetime.now()
        - datetime.timedelta(hours=settings.ROUTING_REQUEST_NOTIFICATION_INTERVAL)
    )
    users = User.objects.filter(
        resend_interval_filter,
        stay__route_steps__status=RouteStep.SUGGESTED,
        stay__route_steps__route__status=Route.CURRENT,
        settings__wants_email_notifications_requests=True,
    ).distinct()
    for user in users:
        debug(f"Send route request notification email to {user}.")
        NotificationService.send_email_notification_requests(user)
