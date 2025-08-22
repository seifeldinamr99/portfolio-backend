#serializers
from rest_framework import serializers
from .models import Asset, Portfolio, HistoricalPrice, Benchmark, AssetPortfolioMapping


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = '__all__'


class BenchmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Benchmark
        fields = '__all__'


class HistoricalPriceSerializer(serializers.ModelSerializer):
    asset_symbol = serializers.CharField(source='asset.symbol', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)

    class Meta:
        model = HistoricalPrice
        fields = '__all__'


class AssetPortfolioMappingSerializer(serializers.ModelSerializer):
    asset_symbol = serializers.CharField(source='asset.symbol', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    portfolio_name = serializers.CharField(source='portfolio.name', read_only=True)

    class Meta:
        model = AssetPortfolioMapping
        fields = '__all__'


class PortfolioSerializer(serializers.ModelSerializer):
    assets = AssetPortfolioMappingSerializer(source='assetportfoliomapping_set', many=True, read_only=True)
    total_assets = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = '__all__'

    def get_total_assets(self, obj):
        return obj.assetportfoliomapping_set.count()


# Detailed serializers for specific use cases
class AssetWithPricesSerializer(serializers.ModelSerializer):
    latest_price = serializers.SerializerMethodField()
    price_history = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = '__all__'

    def get_latest_price(self, obj):
        latest = obj.historicalprice_set.order_by('-date').first()
        if latest:
            return {
                'date': latest.date,
                'price': getattr(latest, 'price', getattr(latest, 'close_price', None)),
                'volume': getattr(latest, 'volume', None)
            }
        return None

    def get_price_history(self, obj):
        # Return last 30 days of price data
        prices = obj.historicalprice_set.order_by('-date')[:30]
        return HistoricalPriceSerializer(prices, many=True).data


class PortfolioDetailSerializer(serializers.ModelSerializer):
    assets = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = '__all__'

    def get_assets(self, obj):
        mappings = obj.assetportfoliomapping_set.select_related('asset').all()
        return AssetPortfolioMappingSerializer(mappings, many=True).data

    def get_performance_summary(self, obj):
        # Basic performance metrics
        total_assets = obj.assetportfoliomapping_set.count()
        total_weight = obj.assetportfoliomapping_set.aggregate(
            total=serializers.Sum('weight')
        ).get('total', 0) or 0

        return {
            'total_assets': total_assets,
            'total_weight': float(total_weight),
            'created_date': obj.created_date
        }