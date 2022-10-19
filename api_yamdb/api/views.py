from api.permissions import AdminOnlyPermission, SafeMethodOnlyPermission
from api.serializers import CategorySerializer, GenreSerializer
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Avg
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken
from reviews.models import Category, Genre, Review, Title, User

from api_yamdb.settings import DEFAULT_FROM_EMAIL

from .filters import TitleFilter
from .permissions import IsAdmin, IsAuthorOrReadOnly
from .serializers import (CommentSerializer, ReviewSerializer,
                          SignupSerializer, TitleGetSerializer,
                          TitlePostSerializer, TokenSerializer,
                          UserEditSerializer, UserSerializer)


class CreateRetrieveViewSet(viewsets.GenericViewSet,
                            mixins.ListModelMixin,
                            mixins.DestroyModelMixin,
                            mixins.CreateModelMixin):
    pass


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAdmin,)
    lookup_field = "username"

    @action(
        methods=[
            "get",
            "patch",
        ],
        detail=False,
        url_path="me",
        permission_classes=[permissions.IsAuthenticated],
        serializer_class=UserEditSerializer,
    )
    def users_own_profile(self, request):
        user = request.user
        if request.method == "GET":
            serializer = self.get_serializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        if request.method == "PATCH":
            serializer = self.get_serializer(
                user,
                data=request.data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['POST'])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    user = get_object_or_404(User,
                             username=serializer.validated_data['username'])
    confirmation_code = default_token_generator.make_token(user)
    send_mail(
        'registration',
        f'Код подтверждения:{confirmation_code}',
        DEFAULT_FROM_EMAIL,
        [user.email],
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def get_token(request):
    serializer = TokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = get_object_or_404(User,
                             username=serializer.validated_data['username'])
    if default_token_generator.check_token(user,
                                           serializer
                                           .validated_data
                                           ['confirmation_code']):
        token = AccessToken.for_user(user)
        return Response({"token": str(token)}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = (IsAuthorOrReadOnly,)

    def get_queryset(self):
        id = self.kwargs.get('title_id')
        title = get_object_or_404(Title, id=id)
        return title.reviews.all()

    def perform_create(self, serializer):
        title_id = self.kwargs.get('title_id')
        title = get_object_or_404(Title, id=title_id)
        serializer.save(author=self.request.user, title=title)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = (IsAuthorOrReadOnly,)

    def get_queryset(self):
        id = self.kwargs.get('review_id')
        review = get_object_or_404(Review, id=id)
        return review.comments.all()

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_id')
        review = get_object_or_404(Review, id=review_id)
        serializer.save(author=self.request.user, review=review)


class TitleViewSet(viewsets.ModelViewSet):
    queryset = Title.objects.annotate(rating=Avg('reviews__score')).all()
    paginator_class = LimitOffsetPagination
    permission_classes = (AdminOnlyPermission,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TitleFilter

    def get_serializer_class(self):
        if self.request.method in ["POST", "PATCH"]:
            return TitlePostSerializer
        return TitleGetSerializer


class GenreViewSet(CreateRetrieveViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ("name",)
    pagination_class = LimitOffsetPagination
    permission_classes = (SafeMethodOnlyPermission,)
    lookup_field = "slug"


class CategoryViewSet(CreateRetrieveViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ("name",)
    pagination_class = LimitOffsetPagination
    permission_classes = (SafeMethodOnlyPermission,)
    lookup_field = "slug"
