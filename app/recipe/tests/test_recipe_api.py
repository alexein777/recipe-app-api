from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Recipe,
    Tag,
    Ingredient,
)
from recipe.serializers import (
    RecipeSerializer,
    RecipeDetailSerializer,
)


RECIPES_URL = reverse('recipe:recipe-list')


def detail_url(recipe_id):
    """Get recipe detail URL for a given recipe id."""
    return reverse('recipe:recipe-detail', args=(recipe_id,))


def create_recipe(user, **params):
    """Create default recipe for a given user as an owner."""
    defaults = {
        'title': 'Sample recipe title',
        'time_minutes': 22,
        'price': Decimal('5.25'),
        'description': 'Sample description',
        'link': 'https://www.example.com/recipe.pdf',
    }
    defaults.update(params)

    # Kreiramo recept u (test) bazi za datog korisnika
    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe


def create_user(**params):
    return get_user_model().objects.create_user(**params)


class PublicRecipeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(RECIPES_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email='test@example.com',
            password='testpass123',
            name='Test Name',
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        # Kreiramo dva recepta za autentifikovanog korisnika
        create_recipe(user=self.user)
        create_recipe(user=self.user, title='Recipe 2')

        # Ocekujemo da ih server vrati u odgovoru
        res = self.client.get(RECIPES_URL)

        # Povlacimo recepte direktno iz (test) baze: u njoj moraju biti
        # tacno ta dva recepta. Pritom, moramo da ih serijalizujemo da bismo
        # ih poredili sa odgovorom servera koji je u vidu JSON-a
        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        other_user = create_user(
            email='otheruser@example.com',
            password='testpass899',
            name='Test other user name',
        )
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)
        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        recipe = create_recipe(user=self.user)
        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        payload = {
            'title': 'Sample recipe title',
            'time_minutes': 30,
            'price': Decimal('5.99'),
        }
        res = self.client.post(RECIPES_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)

        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        original_link = 'https://www.example.com/recipe.pdf'
        recipe = create_recipe(
            user=self.user,
            title='Sample title',
            link=original_link,
        )

        payload = {'title': 'New title'}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_update(self):
        recipe = create_recipe(
            user=self.user,
            title='Sample title',
            link='https://www.example.com/recipe.pdf',
            description='Sample description',
        )

        payload = {
            'title': 'New title',
            'link': 'https://www.example.com/new-recipe.pdf',
            'description': 'New description',
            'time_minutes': 30,
            'price': Decimal('6.99'),
        }
        url = detail_url(recipe.id)
        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)

        self.assertEqual(recipe.user, self.user)

    def test_update_user_returns_error(self):
        new_user = create_user(
            email='user2@example.com',
            password='testpass123',
            name='Other user',
        )
        recipe = create_recipe(user=self.user)

        payload = {'user': new_user.id}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_delete_other_users_recipe_error(self):
        new_user = create_user(
            email='otheruser@example.com',
            password='testpass123',
            name='Other user',
        )
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    # Napomena. Hocemo da korisnik moze da doda tagove odmah prilikom
    # kreiranja recepta, i zato ovde (u receptima) dodajemo testove
    def test_create_recipe_with_new_tags(self):
        """Test creating a recipe with new tags."""
        payload = {
            'title': 'Thai Prawn Curry',
            'time_minutes': 30,
            'price': Decimal('2.50'),
            'tags': [
                {'name': 'Thai'},
                {'name': 'Dinner'},
            ]
        }
        # Posto paylaod sadrzi ugnjezdene json objekte, prosledjujemo
        # argument format='json' da osiguramo ovo ponasanje
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)  # postoji tacno jedan recept

        recipe = recipes[0]  # nece biti index errora jer smo proverili count()
        self.assertEqual(recipe.tags.count(), 2)  # taj recept ima samo 2 taga
        for tag in payload['tags']:
            # Proveravamo da li tagovi iz payload-a stvarno postoje
            tag_exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user,
            ).exists()
            self.assertTrue(tag_exists)

    def test_create_recipe_with_existing_tags(self):
        """Test creating a recipe with existing tag."""
        tag_indian = Tag.objects.create(user=self.user, name='Indian')

        payload = {
            'title': 'Pongal',
            'time_minutes': 60,
            'price': Decimal('4.50'),
            'tags': [
                {'name': 'Indian'},  # necemo da kreiramo novi obj u bazi
                {'name': 'Breakfast'},
            ]
        }
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)

        # Hocemo da ovaj konkretni tag koji smo vec napravili u bazi da bude
        # iskoriscen a ne da bude napravljen novi
        self.assertIn(tag_indian, recipe.tags.all())
        for tag in payload['tags']:
            tag_exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user,
            ).exists()
            self.assertTrue(tag_exists)

    def test_create_tag_on_update(self):
        """Test creating a tag when updating a recipe."""
        recipe = create_recipe(user=self.user)

        payload = {'tags': [{'name': 'Lunch'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user=self.user, name='Lunch')
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """Test assignin an existing tag when updating a recipe."""
        tag_breakfast = Tag.objects.create(user=self.user, name='Breakfast')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        # Hocemo da promenimo tag recepta iz Breakfast u Lunch
        tag_lunch = Tag.objects.create(user=self.user, name='Lunch')
        payload = {'tags': [{'name': 'Lunch'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Ocekujemo da se tag promenio, tj. dase sada lunch tag nalazi u
        # receptu, a breakfast tag vise ne
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):
        """Test clearing recipes tags."""
        tag = Tag.objects.create(user=self.user, name='Desert')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {'tags': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    def test_create_recipe_with_new_ingredients(self):
        """Test creating a recipe with new ingredients."""
        payload = {
            'title': 'Cauliflower Tacos',
            'time_minutes': 60,
            'price': Decimal('4.30'),
            'ingredients': [
                {'name': 'Cauliflower'},
                {'name': 'Salt'},
            ],
        }
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload['ingredients']:
            ingredient_exists = recipe.ingredients.filter(
                name=ingredient['name'],
                user=self.user,
            ).exists()
            self.assertTrue(ingredient_exists)

    def test_create_recipe_with_existing_ingredients(self):
        """Test creating a recipe with existing ingredients."""
        ingredient = Ingredient.objects.create(
            user=self.user,
            name='Lemon',
        )

        payload = {
            'title': 'Vietnamese Soup',
            'time_minutes': 25,
            'price': Decimal('2.55'),
            'ingredients': [
                {'name': 'Lemon'},
                {'name': 'Fish Sauce'},
            ],
        }
        res = self.client.post(RECIPES_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)

        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)

        # Glavni deo koda: kreirani sastojak koji je vec u bazi treba da
        # bude dodeljen receptu, a ne da se kreira novi sastojak u bazi
        self.assertIn(ingredient, recipe.ingredients.all())

        for ingredient in payload['ingredients']:
            ingredient_exists = recipe.ingredients.filter(
                name=ingredient['name'],
                user=self.user,
            ).exists()
            self.assertTrue(ingredient_exists)

    def test_create_ingredient_on_update(self):
        """Test creating an ingredient when updating a recipe."""
        recipe = create_recipe(user=self.user)

        # Azuriramo recept tako sto mu dodajemo jedan sastojak
        payload = {'ingredients': [{'name': 'Limes'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Taj dodati sastojak mora da se nadje u tom receptu (
        # recipe.ingredients.all() prakticno refreshuje bazu tako da ce ga
        # stvarno pokupiti)
        new_ingredient = Ingredient.objects.get(user=self.user, name='Limes')
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """Test assigning an existing ingredient when updating a recipe."""
        ingredient1 = Ingredient.objects.create(
            user=self.user,
            name='Pepper',
        )
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient1)

        ingredient2 = Ingredient.objects.create(
            user=self.user,
            name='Chili',
        )
        payload = {'ingredients': [{'name': 'Chili'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(ingredient2, recipe.ingredients.all())
        self.assertNotIn(ingredient1, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        """Test clearing recipe's ingredients."""
        ingredient = Ingredient.objects.create(
            user=self.user,
            name='Garlic',
        )
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {'ingredients': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)
