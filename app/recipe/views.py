from rest_framework import (
    viewsets,
    mixins,
    status,
)
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from core.models import (
    Recipe,
    Tag,
    Ingredient,
)
from recipe import serializers


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                'tags',
                OpenApiTypes.STR,
                description='Comma separated list of tag ids to filter',
            ),
            OpenApiParameter(
                'ingredients',
                OpenApiTypes.STR,
                description='Comma separated list of ingredient ids to filter',
            ),
        ],
    )
)
class RecipeViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.RecipeDetailSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Recipe.objects.all()

    def get_queryset(self):
        """Return recipes only for authenticated user."""
        tags = self.request.query_params.get('tags')
        ingredients = self.request.query_params.get('ingredients')
        queryset = self.queryset

        # Filtriranje spec. sintaksom za filtriranje iz queryset-a
        if tags:
            tag_ids = self._params_to_ints(tags)  # npr. [1, 2, 3]
            queryset = queryset.filter(tags__id__in=tag_ids)

        if ingredients:
            ingredient_ids = self._params_to_ints(ingredients)  # npr. [5, 8]
            queryset = queryset.filter(ingredients__id__in=ingredient_ids)

        # Recepti moraju da pripadaju autentifikovanom korisniku, da budu
        # uredjeni opadajuce, i osiguravamo da se ne vracaju duplikati (zbog
        # dvostrukog nezavisnog filtririanja, po tagovima i sastojcima)
        return queryset.filter(
            user=self.request.user,
        ).order_by('-id').distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.RecipeSerializer
        elif self.action == 'upload_image':
            return serializers.RecipeImageSerializer

        return self.serializer_class

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(methods=['POST'], detail=True, url_path='upload_image')
    def upload_image(self, request, pk=None):
        # Dohvatamo konkretan recept koji je na ovom URL-u (URL je oblika:
        # .../recipes/<recipe_id>
        recipe = self.get_object()

        # get_serializer poziva get_serializer_class i posto je akcija
        # upravo 'upload_image', vratice se RecipeImageSerializer,
        # kome potom prosledjujemo podatke iz zahteva
        serializer = self.get_serializer(recipe, data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ovde je serializer validan, cuvamo uploadovanu sliku u bazi i
        # vracamo odgovor
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _params_to_ints(self, qs: str):
        return [int(str_id) for str_id in qs.strip().split(',')]


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                'assigned_only',
                OpenApiTypes.INT,
                enum=[0, 1],
                description='Filter by items assigned to recipes',
            ),
        ],
    )
)
class BaseRecipeAttrViewSet(
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Base viewset for recipe attributes."""
    # auth, perm i get_queryset() su identicni i za Tags i za Ingredients pa
    # ima smisla da napravimo baznu klasu koja ce objedini deljeni kod
    # Takodje, ako hocemo da promenimo ponasanje atribute (npr. order_by),
    # to sada mozemo da uradimo na jednom mestu i to ce se odraziti na sve
    # atribute, cak i ako odlucimo da dodamo neke nove
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter queryset to authenticated user."""
        assigned_only = bool(
            int(self.request.query_params.get('assigned_only', 0))
        )
        queryset = self.queryset

        if assigned_only:
            queryset = queryset.filter(recipe__isnull=False)

        return queryset.filter(
            user=self.request.user,
        ).order_by('-name').distinct()


class TagViewSet(BaseRecipeAttrViewSet):
    """Manage tags in the database."""
    serializer_class = serializers.TagSerializer
    queryset = Tag.objects.all()


class IngredientViewSet(BaseRecipeAttrViewSet):
    serializer_class = serializers.IngredientSerializer
    queryset = Ingredient.objects.all()
