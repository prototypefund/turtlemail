import datetime

from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


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


class User(AbstractBaseUser, PermissionsMixin):
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

    objects = UserManager()

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


class Location(models.Model):
    name = models.CharField(verbose_name=_("Name"), max_length=100)
    is_home = models.BooleanField(verbose_name=_("Home"))
    lat = models.DecimalField(
        verbose_name=_("Latitude"), max_digits=17, decimal_places=15
    )
    lon = models.DecimalField(
        verbose_name=_("Longitude"), max_digits=17, decimal_places=15
    )
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

    class Meta:
        verbose_name = _("Stay")
        verbose_name_plural = _("Stays")
