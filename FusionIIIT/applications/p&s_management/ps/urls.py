from django.urls import include, path
from rest_framework.routers import DefaultRouter

from ps import views
from ps.stock_views import StockCheckView

router = DefaultRouter()
router.register(r"indents", views.IndentViewSet, basename="indent")
router.register(r"me", views.MeViewSet, basename="me")

urlpatterns = [
    path("", include(router.urls)),
    path("stock/check/<int:item_id>/", StockCheckView.as_view(), name="stock_check"),
]

