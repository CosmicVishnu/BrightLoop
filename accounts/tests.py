from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from accounts.validators import BrightloopPasswordValidator

User = get_user_model()

class AccountsTest(TestCase):
    def setUp(self):
        self.validator = BrightloopPasswordValidator()
        self.client = Client()

    def test_password_validator_valid(self):
        # > 8 chars, 1 uppercase, 1 lowercase, 1 special
        self.validator.validate("Valid@1234")

    def test_password_validator_too_short(self):
        with self.assertRaises(ValidationError):
            self.validator.validate("Ab@12")

    def test_password_validator_no_uppercase(self):
        with self.assertRaises(ValidationError):
            self.validator.validate("lowercase@1234")

    def test_password_validator_no_lowercase(self):
        with self.assertRaises(ValidationError):
            self.validator.validate("UPPERCASE@1234")

    def test_password_validator_no_special(self):
        with self.assertRaises(ValidationError):
            self.validator.validate("NoSpecial1234")

    def test_customer_signup_and_login(self):
        res = self.client.post('/accounts/signup/', {
            'email': 'newcustomer@test.com',
            'first_name': 'Test',
            'last_name': 'Customer',
            'password': 'Secure#Password99',
            'confirm_password': 'Secure#Password99',
        })
        self.assertEqual(res.status_code, 302)
        user = User.objects.get(email='newcustomer@test.com')
        self.assertEqual(user.role, User.ROLE_CUSTOMER)

    def test_staff_creation_admin_only(self):
        admin = User.objects.create_superuser('admin_test@test.com', 'Admin#1234')
        staff = User.objects.create_user('staff_test@test.com', 'Staff#1234', role=User.ROLE_STAFF)
        customer = User.objects.create_user('cust_test@test.com', 'Cust#1234', role=User.ROLE_CUSTOMER)

        # Customer denied
        self.client.force_login(customer)
        res = self.client.get('/accounts/staff/')
        self.assertEqual(res.status_code, 403)

        # Staff denied
        self.client.force_login(staff)
        res = self.client.get('/accounts/staff/')
        self.assertEqual(res.status_code, 403)

        # Admin allowed
        self.client.force_login(admin)
        res = self.client.get('/accounts/staff/')
        self.assertEqual(res.status_code, 200)

    def test_password_reset_flow(self):
        User.objects.create_user('reset_test@brightloop.com', 'Initial#1234', role=User.ROLE_CUSTOMER)
        res = self.client.post('/accounts/password-reset/', {'email': 'reset_test@brightloop.com'})
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, '/accounts/password-reset/done/')
