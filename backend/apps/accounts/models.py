import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils.timezone import now as tz_now

from apps.core.enums import Profession
from apps.core.models import HEX_COLOR, TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(max_length=254, unique=True, db_index=True)
    full_name = models.CharField(max_length=150, blank=True, default="")

    avatar = models.ImageField(
        upload_to="avatars/%Y/%m/", max_length=500, null=True, blank=True
    )
    avatar_color = models.CharField(
        max_length=7, default="#7B68EE", validators=[HEX_COLOR]
    )

    # Kasb roli — PROFIL MA'LUMOTI, RUXSAT ROLI EMAS. Hech qanday tekshiruv
    # (has_perm / require_perm / WorkspaceRole) bu maydonni o'qimaydi; u faqat
    # UI'da ko'rsatiladi va PM odam tanlashiga yordam beradi.
    profession = models.CharField(
        max_length=20, choices=Profession.choices, blank=True, default=""
    )

    timezone = models.CharField(max_length=64, default="UTC", db_index=False)

    # Faqat o'qish uchun hisob (demo). Rolidan qat'i nazar — egasi bo'lsa ham —
    # har qanday yozish ruxsati `apps.core.access.has_perm` da rad etiladi.
    # Owner huquqlari qulflangani uchun buni matritsa orqali qilib bo'lmaydi.
    is_readonly = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=tz_now, editable=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []  # createsuperuser prompts for email + password only

    class Meta:
        db_table = "users"
        ordering = ["email"]
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci"),
        ]
        indexes = [
            models.Index(Lower("full_name"), name="idx_user_fullname_ci"),
        ]

    def __str__(self):
        return self.email

    @property
    def initials(self) -> str:
        source = (self.full_name or self.email).strip()
        parts = [p for p in source.replace("@", " ").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @property
    def display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]
