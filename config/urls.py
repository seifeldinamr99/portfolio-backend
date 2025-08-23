from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def api_root(request):
    return JsonResponse({
        'message': 'Portfolio API is running',
        'status': 'healthy',
        'endpoints': {
            'health_check': '/api/health/',
            'assets': '/api/assets/',
            'portfolios': '/api/portfolios/',
            'prices': '/api/prices/',
            'benchmarks': '/api/benchmarks/',
            'portfolio_analysis': '/api/run-portfolio-analysis/',
            'admin': '/admin/'
        }
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('portfolio.urls')),
    path('', api_root, name='api_root'),  # This handles the root URL
]