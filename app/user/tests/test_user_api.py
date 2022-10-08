from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status


CREATE_USER_URL = reverse('user:create')
TOKEN_URL = reverse('user:token')
ME_URL = reverse('user:me')


def create_user(**payload):
    """Helper function to create user."""
    return get_user_model().objects.create_user(**payload)


class PublicUserApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_user_success(self):
        payload = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'name': 'Test Name',
        }
        res = self.client.post(CREATE_USER_URL, payload)

        # Pre svega mora da bude 201 status kod nakon POST zahteva
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Proveravamo da l je kreiran korisnik: ako jeste, njegova sacuvana
        # sifra (hesirana) ce biti jednaka onoj iz payload-a
        user = get_user_model().objects.get(email=payload['email'])
        self.assertTrue(user.check_password(payload['password']))

        # Jos proveravamo da li kada dohvatamo korisnika se njegova sifra
        # nalazi u odgovoru (ne bi smelo)
        self.assertNotIn('password', res.data)

    def test_user_with_email_exists(self):
        payload = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'name': 'Test Name',
        }
        create_user(**payload)
        res = self.client.post(CREATE_USER_URL, payload)

        # Treba da bude neuspesan post jer korisnik s tim mejlom vec postoji
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short(self):
        payload = {
            'email': 'test@example.com',
            'password': 'pw',
            'name': 'Test Name',
        }
        res = self.client.post(CREATE_USER_URL, payload)
        # Ovakav POST zahtev ne sme da prodje
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Provera da li korisnik postoji u bazi: ne bi trebalo da postoji
        # jer testiramo sifru prilikom REGISTRACIJE korisnika
        user_exists = get_user_model().objects.filter(
            email=payload['email'],
        ).exists()
        self.assertFalse(user_exists)

    def test_create_token_for_user(self):
        user_details = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'name': 'Test Name',
        }
        create_user(**user_details)

        payload = {
            'email': user_details['email'],
            'password': user_details['password'],
        }
        res = self.client.post(TOKEN_URL, payload)

        # Ako je token uspesno kreiran, status je 200 i 'token' mora da se
        # nalazi u odgovoru
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('token', res.data)

    def test_create_token_bad_credentials(self):
        user_details = {
            'email': 'test@example.com',
            'password': 'goodpass',
            'name': 'Test Name',
        }
        create_user(**user_details)

        payload = {
            'email': 'test@example.com',
            'password': 'badpass',
        }
        res = self.client.post(TOKEN_URL, payload)

        # Ako nije dobra sifra, status je 400 i 'token' ne sme da se nalazi
        # u odgovoru
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('token', res.data)

    def test_create_token_blank_password(self):
        user_details = {
            'email': 'test@example.com',
            'password': 'goodpass',
            'name': 'Test Name',
        }
        create_user(**user_details)

        payload = {
            'email': 'test@example.com',
            'password': '',  # samo ova linija se razlikuje od prethodne f-je
        }
        res = self.client.post(TOKEN_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('token', res.data)

    def test_retrieve_user_unauthorized(self):
        res = self.client.get(ME_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateUserApiTests(TestCase):
    def setUp(self):
        self.user = create_user(
            name='Test Name',
            email='test@example.com',
            password='testpass123',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_profile_success(self):
        res = self.client.get(ME_URL)

        # GET mora da vrati iste podatke kao autentifikovani korisnik
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {
            'name': self.user.name,
            'email': self.user.email,
        })

    def test_post_me_not_allowed(self):
        res = self.client.post(ME_URL, {})
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_user_profile(self):
        payload = {
            'name': 'Updated name',
            'password': 'newpassword123',
        }
        res = self.client.patch(ME_URL, payload)

        self.user.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self.user.name, payload['name'])
        self.assertTrue(self.user.check_password(payload['password']))
