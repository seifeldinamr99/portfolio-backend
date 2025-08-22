from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views   # <-- make sure this points to the correct views.py

router = DefaultRouter()

# Register all the viewsets
router.register(r'assets', views.AssetViewSet)
router.register(r'portfolios', views.PortfolioViewSet)
router.register(r'prices', views.HistoricalPriceViewSet)
router.register(r'benchmarks', views.BenchmarkViewSet)
router.register(r'portfolio-assets', views.AssetPortfolioMappingViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('health/', views.health_check, name='health_check'),

    # Simplified backtesting endpoint (stateless, instant results)
    path('run-portfolio-analysis/', views.run_portfolio_analysis, name='run_analysis'),
]
