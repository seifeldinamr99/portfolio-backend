# portfolio/views.py - Updated with backtesting integration
from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime

from .models import (
    Asset, Portfolio, HistoricalPrice, Benchmark, AssetPortfolioMapping)
from .serializers import (
    AssetSerializer, PortfolioSerializer, HistoricalPriceSerializer,
    BenchmarkSerializer, AssetPortfolioMappingSerializer,
    AssetWithPricesSerializer, PortfolioDetailSerializer
)
from .backtesting import SimpleBacktestEngine  # Import your backtesting engine


def health_check(request):
    """Simple health check endpoint"""
    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Get basic counts
        asset_count = Asset.objects.count()
        portfolio_count = Portfolio.objects.count()
        price_count = HistoricalPrice.objects.count()

        return JsonResponse({
            'status': 'healthy',
            'database': 'connected',
            'data_summary': {
                'assets': asset_count,
                'portfolios': portfolio_count,
                'price_records': price_count
            }
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)


@api_view(['POST'])
def run_portfolio_analysis(request):
    """
    Run portfolio backtest instantly and return results (no DB storage).
    """
    try:
        print("=== DEBUG: Request received ===")
        print("Request data:", request.data)

        portfolios = request.data.get('portfolios', [])
        benchmark_id = request.data.get('benchmark_id')
        rebalance_frequency = request.data.get('rebalance_frequency', 'never')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        print("=== DEBUG: Parsed data ===")
        print(f"Portfolios: {portfolios}")
        print(f"Benchmark ID: {benchmark_id}")

        # --- Validation
        if not portfolios:
            return Response({'error': 'No portfolios selected'}, status=400)
        if not benchmark_id:
            return Response({'error': 'No benchmark selected'}, status=400)
        if not start_date or not end_date:
            return Response({'error': 'Start and end dates required'}, status=400)

        print("=== DEBUG: About to check weights ===")
        total_weight = sum(float(p.get('weight', 0)) for p in portfolios)
        print(f"Total weight: {total_weight}")

        if abs(total_weight - 100.0) > 0.1:
            return Response({'error': f'Portfolio weights must sum to 100%, got {total_weight}%'}, status=400)

        print("=== DEBUG: About to check benchmark ===")
        if not Benchmark.objects.filter(id=benchmark_id).exists():
            return Response({'error': 'Invalid benchmark selected'}, status=400)

        print("=== DEBUG: About to import SimpleBacktestEngine ===")
        # --- Run backtest immediately
        engine = SimpleBacktestEngine(
            portfolio_mix=portfolios,
            benchmark_id=benchmark_id,
            start_date=start_date,
            end_date=end_date,
            rebalance_frequency=rebalance_frequency
        )

        print("=== DEBUG: About to run backtest ===")
        results = engine.run_backtest()

        return Response({
            'status': 'completed',
            'results': results
        })

    except Exception as e:
        print(f"=== ERROR: {str(e)} ===")
        import traceback
        print(traceback.format_exc())
        return Response({'error': f'Backtest failed: {str(e)}'}, status=500)



class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for assets - provides list and detail views
    """
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['asset_type', 'currency']
    search_fields = ['symbol', 'name']
    ordering_fields = ['symbol', 'name', 'asset_type']
    ordering = ['symbol']

    @action(detail=True, methods=['get'])
    def prices(self, request, pk=None):
        """Get price history for a specific asset"""
        asset = self.get_object()
        prices = asset.prices.order_by('-date')  # Using related_name from model

        # Add date filtering
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        limit = request.query_params.get('limit', 100)

        if start_date:
            prices = prices.filter(date__gte=start_date)
        if end_date:
            prices = prices.filter(date__lte=end_date)

        prices = prices[:int(limit)]

        serializer = HistoricalPriceSerializer(prices, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def with_prices(self, request):
        """Get assets with their latest price information"""
        assets = self.get_queryset()
        serializer = AssetWithPricesSerializer(assets, many=True)
        return Response(serializer.data)


class PortfolioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for portfolios - provides list and detail views
    """
    queryset = Portfolio.objects.all()
    serializer_class = PortfolioSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_date']
    ordering = ['-created_date']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PortfolioDetailSerializer
        return PortfolioSerializer

    @action(detail=True, methods=['get'])
    def assets(self, request, pk=None):
        """Get all assets in a specific portfolio"""
        portfolio = self.get_object()
        mappings = portfolio.asset_mappings.select_related('asset').all()  # Using related_name
        serializer = AssetPortfolioMappingSerializer(mappings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get performance data for a portfolio (placeholder for future implementation)"""
        portfolio = self.get_object()

        # Basic performance metrics
        assets = portfolio.asset_mappings.select_related('asset')
        total_weight = sum(float(asset.weight or 0) for asset in assets)

        performance_data = {
            'portfolio_name': portfolio.name,
            'total_assets': assets.count(),
            'total_weight': total_weight,
            'created_date': portfolio.created_date,
            'assets_breakdown': [
                {
                    'symbol': asset.asset.symbol,
                    'name': asset.asset.name,
                    'weight': float(asset.weight or 0),
                    'asset_type': asset.asset.asset_type
                }
                for asset in assets.all()
            ]
        }

        return Response(performance_data)


class HistoricalPriceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for historical price data
    """
    queryset = HistoricalPrice.objects.select_related('asset').all()
    serializer_class = HistoricalPriceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['asset', 'asset__symbol', 'asset__asset_type']
    search_fields = ['asset__symbol', 'asset__name']
    ordering_fields = ['date']
    ordering = ['-date']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Add date range filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset





class BenchmarkViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for benchmark data
    """
    queryset = Benchmark.objects.all()
    serializer_class = BenchmarkSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'symbol', 'description']
    ordering = ['name']


class AssetPortfolioMappingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for portfolio-asset mappings
    """
    queryset = AssetPortfolioMapping.objects.select_related('asset', 'portfolio').all()
    serializer_class = AssetPortfolioMappingSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['portfolio', 'asset', 'asset__asset_type']
    search_fields = ['portfolio__name', 'asset__symbol', 'asset__name']