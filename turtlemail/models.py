import datetime
import secrets
from typing import TYPE_CHECKING, ClassVar, Self, Tuple

from django.contrib.gis.db.models import PointField
from django.db import models, transaction
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.core.validators import MinValueValidator
from django.template.defaultfilters import date
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class UserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given email and password.
        """

        if not email:
            raise ValueError(_("The email must be set."))

        user = self.model(email=self.normalize_email(email), **extra_fields)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self._create_user(email, password, **extra_fields)

    def search_for_recipient(self, username: str, searching_users_id: int):
        return self.filter(
            username__icontains=username,
        ).exclude(id__exact=searching_users_id)


class User(AbstractBaseUser, PermissionsMixin):
    if TYPE_CHECKING:
        # Automatically generated
        id: int

        # Relationships
        location_set: RelatedManager["Location"]
        stay_set: RelatedManager["Stay"]
        sent_packets: RelatedManager["Packet"]
        received_packets: RelatedManager["Packet"]

    email = models.EmailField(
        verbose_name=_("email address"),
        max_length=255,
        unique=True,
    )
    username = models.CharField(max_length=100, unique=True)
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects: ClassVar[UserManager] = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def __str__(self):
        return self.email


def default_invite_token():
    return secrets.token_urlsafe(32)


class Invite(models.Model):
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(
        max_length=255,
        unique=True,
        error_messages={"unique": _("This user has already been invited.")},
    )

    token = models.TextField(default=default_invite_token)

    class Meta:
        indexes = [models.Index(fields=["token"])]

    def __str__(self):
        return f"{self.email} (from {self.invited_by.username})"


class Location(models.Model):
    if TYPE_CHECKING:
        # Automatically generated
        id: int

        # Relationships
        stay_set: RelatedManager["Stay"]

    name = models.CharField(verbose_name=_("Name"), max_length=100)
    is_home = models.BooleanField(verbose_name=_("Home"))
    # Order: longitude, latitude (!)
    point = PointField(verbose_name=_("Location"), geography=True)
    user = models.ForeignKey(User, verbose_name=_("User"), on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")

    def __str__(self):
        return self.name


class Stay(models.Model):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    SOMETIMES = "SOMETIMES"
    ONCE = "ONCE"

    FREQUENCY_CHOICES = [
        (DAILY, "Daily"),
        (WEEKLY, "Weekly"),
        (SOMETIMES, "Sometimes"),
        (ONCE, "Once"),
    ]

    if TYPE_CHECKING:
        # Automatically generated
        id: int

        route_steps: RelatedManager["RouteStep"]

    location = models.ForeignKey(
        Location, verbose_name=_("Location"), on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, verbose_name=_("User"), on_delete=models.CASCADE)
    frequency = models.CharField(
        verbose_name=_("Frequency"), max_length=10, choices=FREQUENCY_CHOICES
    )
    start = models.DateField(
        verbose_name=_("Start"),
        validators=[MinValueValidator(limit_value=datetime.date.today)],
        null=True,
        blank=True,
    )
    end = models.DateField(
        verbose_name=_("End"),
        validators=[MinValueValidator(limit_value=datetime.date.today)],
        null=True,
        blank=True,
    )
    inactive_until = models.DateField(
        verbose_name=_("Inactive until"),
        validators=[MinValueValidator(limit_value=datetime.date.today)],
        null=True,
        blank=True,
    )
    "If set, this stay will not be included in any routes until this date has passed."

    deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Stay")
        verbose_name_plural = _("Stays")

    def __str__(self) -> str:
        time = (
            f"{self.start} - {self.end}"
            if self.start is not None and self.end is not None
            else f"{self.frequency}"
        )
        return f"Stay: {self.user.username} in {self.location.name} {time}"

    def mark_deleted(self):
        """
        Set this stay as deleted, and reject its suggested route steps.
        """
        with transaction.atomic():
            self.deleted = True
            self.save()
            self.route_steps.filter(status=RouteStep.SUGGESTED).update(
                status=RouteStep.REJECTED
            )


class PacketManager(models.Manager):
    def get_by_natural_key(self, human_id):
        return self.get(human_id=human_id)


class Packet(models.Model):
    if TYPE_CHECKING:
        # Automatically generated
        id: int

        all_routes: RelatedManager["Route"]
        routestep_set: RelatedManager["RouteStep"]
        delivery_logs: RelatedManager["DeliveryLog"]

    class Status(models.TextChoices):
        CALCULATING_ROUTE = "CALCULATING_ROUTE", _("Calculating Route")
        NO_ROUTE_FOUND = "NO_ROUTE_FOUND", _("No Route Found")
        CONFIRMING_ROUTE = "CONFIRMING_ROUTE", _("Confirming Route")
        ROUTE_OUTDATED = "ROUTE_OUTDATED", _("Route is Outdated")
        READY_TO_SHIP = "READY_TO_SHIP", _("Ready to Ship")
        DELIVERING = "DELIVERING", _("Delivering")
        DELIVERED = "DELIVERED", _("Delivered")

        def description(self):
            match self:
                case self.CALCULATING_ROUTE:
                    return _(
                        "The system is currently looking for people who can make this delivery."
                    )

                case self.NO_ROUTE_FOUND:
                    return _("The system found no way to reach the recipient.")

                case self.CONFIRMING_ROUTE:
                    return _(
                        "Waiting for everyone involved to confirm the planned journeys."
                    )

                case self.ROUTE_OUTDATED:
                    return _(
                        "Some people making this delivery don't have matching travel plans. The system will look for a new way to make this delivery."
                    )
                case self.READY_TO_SHIP:
                    return _("This delivery is ready to begin its journey.")
                case self.DELIVERING:
                    return _(
                        "This delivery is currently traveling through the turtlemail network."
                    )
                case self.DELIVERED:
                    return _("This delivery has reached its destination.")

    # Users with packets can't be deleted right now.
    # What if the packet is still being delivered?
    sender = models.ForeignKey(
        User,
        verbose_name=_("Sender"),
        on_delete=models.RESTRICT,
        related_name="sent_packets",
    )
    recipient = models.ForeignKey(
        User,
        verbose_name=_("Recipient"),
        on_delete=models.RESTRICT,
        related_name="received_packets",
    )
    created_at = models.DateTimeField(verbose_name=_("Created at"), auto_now_add=True)
    human_id = models.TextField(verbose_name=_("Code"), unique=True)

    objects = PacketManager()

    class Meta:
        indexes = [
            models.Index(fields=["human_id"]),
            models.Index(fields=["sender_id"]),
            models.Index(fields=["recipient_id"]),
        ]

        verbose_name = _("Delivery")
        verbose_name_plural = _("Deliveries")

    if TYPE_CHECKING:
        all_routes: "RelatedManager[Route]"

    def __str__(self):
        return f'Packet "{self.human_id}"'

    def natural_key(self):
        return (self.human_id,)

    def is_sender_or_recipient(self, user: User):
        return user.id in [
            self.recipient.id,
            self.sender.id,
        ]

    def current_route(self):
        return self.all_routes.filter(status=Route.CURRENT).first()

    def status(self):
        route = self.current_route()
        if route is None:
            newest_log = self.delivery_logs.first()
            if (
                newest_log is not None
                and newest_log.action == DeliveryLog.NO_ROUTE_FOUND
            ):
                return self.Status.NO_ROUTE_FOUND

            return self.Status.CALCULATING_ROUTE

        steps = route.steps.all()

        if any([step.status == RouteStep.REJECTED for step in steps]):
            return self.Status.ROUTE_OUTDATED

        if any([step.status == RouteStep.SUGGESTED for step in steps]):
            return self.Status.CONFIRMING_ROUTE

        if all([step.status == RouteStep.ACCEPTED for step in steps]):
            return self.Status.READY_TO_SHIP

        if all([step.status == RouteStep.COMPLETED for step in steps]):
            return self.Status.DELIVERED

        return self.Status.DELIVERING


class Route(models.Model):
    CURRENT = "CURRENT"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [(CURRENT, "Current"), (CANCELLED, "Cancelled")]

    if TYPE_CHECKING:
        # Automatically generated
        id: int

        steps: RelatedManager["RouteStep"]
        deliverylog_set: RelatedManager["DeliveryLog"]

    status = models.TextField(verbose_name=_("Status"), choices=STATUS_CHOICES)
    packet = models.ForeignKey(
        Packet,
        verbose_name=_("Delivery"),
        on_delete=models.CASCADE,
        related_name="all_routes",
    )

    class Meta:
        verbose_name = _("Route")
        verbose_name_plural = _("Routes")

    def __str__(self):
        return f"{self.status} Route"

    def accepted_steps(self):
        return self.steps.filter(status=RouteStep.ACCEPTED)

    def completed_steps(self):
        return self.steps.filter(status=RouteStep.COMPLETED)


class RouteStep(models.Model):
    SUGGESTED = "SUGGESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (SUGGESTED, _("Suggested")),
        (ACCEPTED, _("Accepted")),
        (REJECTED, _("Rejected")),
        (ONGOING, _("Ongoing")),
        (COMPLETED, _("Completed")),
        (CANCELLED, _("Cancelled")),
    ]

    if TYPE_CHECKING:
        # Automatically generated
        id: int

        delivery_logs: RelatedManager["DeliveryLog"]

    stay = models.ForeignKey(
        Stay,
        verbose_name=_("Stay"),
        related_name="route_steps",
        on_delete=models.RESTRICT,
    )
    start = models.DateField(
        verbose_name=_("Start"),
        validators=[MinValueValidator(limit_value=datetime.date.today)],
        null=True,
        blank=True,
    )
    end = models.DateField(
        verbose_name=_("End"),
        validators=[MinValueValidator(limit_value=datetime.date.today)],
        null=True,
        blank=True,
    )
    previous_step = models.OneToOneField(
        "self",
        verbose_name=_("Previous Step"),
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
    )
    next_step = models.OneToOneField(
        "self",
        verbose_name=_("Next Step"),
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
    )
    packet = models.ForeignKey(
        Packet, verbose_name=_("Delivery"), on_delete=models.CASCADE
    )
    status = models.TextField(verbose_name=_("Status"), choices=STATUS_CHOICES)
    route = models.ForeignKey(
        Route, verbose_name=_("Route"), on_delete=models.CASCADE, related_name="steps"
    )

    class Meta:
        verbose_name = _("Route Step")
        verbose_name_plural = _("Route Steps")

        ordering = ["start"]

    def get_overlapping_date_range(
        self, other: Self | None
    ) -> Tuple[datetime.date | None, datetime.date | None]:
        if other is None:
            return (None, None)

        if self.start is not None and other.start is not None:
            start = max(self.start, other.start)
        else:
            start = self.start if self.start is not None else other.start

        if self.end is not None and other.end is not None:
            end = min(self.end, other.end)
        else:
            end = self.end if self.end is not None else other.end

        # Check if the date ranges don't overlap. If so, return None instead
        match start, end:
            case datetime.date(), datetime.date() if start > end:
                return (None, None)

        return (start, end)

    def describe_overlapping_date_range(self, other: Self | None) -> str:
        start, end = self.get_overlapping_date_range(other)

        if start is not None and end is not None:
            return _("Between %(start_date)s and %(end_date)s") % {
                "start_date": date(start),
                "end_date": date(end),
            }
        elif start is not None:
            return _("After %(date)s") % {"date": date(start)}
        elif end is not None:
            return _("Before %(date)s" % {"date": date(end)})
        else:
            return _("At some point")

    def set_status(self, new_status: str):
        DeliveryLog.objects.create(
            route_step=self,
            packet=self.packet,
            route=self.route,
            action=DeliveryLog.ROUTE_STEP_CHANGE,
            new_step_status=new_status,
        )
        self.status = new_status


class DeliveryLog(models.Model):
    ROUTE_STEP_CHANGE = "ROUTE_STEP_CHANGE"
    SEARCHING_ROUTE = "SEARCHING_ROUTE"
    NEW_ROUTE = "NEW_ROUTE"
    NO_ROUTE_FOUND = "NO_ROUTE_FOUND"

    ACTION_CHOICES = (
        (ROUTE_STEP_CHANGE, "Travel Step Changed"),
        (SEARCHING_ROUTE, "Updating Travel Plans"),
        (NEW_ROUTE, "Travel Plans Changed"),
        (NO_ROUTE_FOUND, "Unable to find Travel Plans"),
    )

    if TYPE_CHECKING:
        # Automatically generated
        id: int

    created_at = models.DateTimeField(verbose_name=_("Datetime"), auto_now_add=True)
    route_step = models.ForeignKey(
        RouteStep,
        verbose_name=_("Route Step"),
        on_delete=models.CASCADE,
        related_name="delivery_logs",
        null=True,
    )
    packet = models.ForeignKey(
        Packet,
        verbose_name=_("Delivery"),
        on_delete=models.CASCADE,
        unique=False,
        related_name="delivery_logs",
    )
    route = models.ForeignKey(
        Route, verbose_name=_("Route"), on_delete=models.CASCADE, null=True
    )
    action = models.TextField(choices=ACTION_CHOICES, verbose_name=_("Action Choices"))
    new_step_status = models.TextField(
        choices=RouteStep.STATUS_CHOICES,
        verbose_name=_("New Route Step Status"),
        null=True,
    )

    def description(self):
        description = self.get_action_display()  # type: ignore

        if self.action == self.ROUTE_STEP_CHANGE:
            description = _(
                "Travel step changed: %(status)s"
                % {"status": self.get_new_step_status_display()}
            )

        return description

    class Meta:
        verbose_name = _("Delivery Log Entry")
        verbose_name_plural = _("Delivery Log Entries")

        ordering = ["-created_at"]
