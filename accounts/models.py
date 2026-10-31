from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', User.ROLE_CUSTOMER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.ROLE_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_STAFF = 'staff'
    ROLE_CUSTOMER = 'customer'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_STAFF, 'Staff'),
        (ROLE_CUSTOMER, 'Customer'),
    ]

    username = None
    email = models.EmailField('Email Address', unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CUSTOMER, db_index=True)
    company_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['email']

    def __str__(self):
        full_name = self.get_full_name()
        if full_name:
            return f"{full_name} ({self.email})"
        return self.email

    @property
    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def is_staff_user(self):
        return self.role == self.ROLE_STAFF

    @property
    def is_customer_user(self):
        return self.role == self.ROLE_CUSTOMER
