from django.contrib import admin
from .models import Asset, Portfolio, HistoricalPrice, Benchmark, AssetPortfolioMapping


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'asset_type', 'currency']
    list_filter = ['asset_type', 'currency']
    search_fields = ['symbol', 'name']
    ordering = ['symbol']


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_date']
    list_filter = ['created_date']
    search_fields = ['name', 'description']
    ordering = ['-created_date']


@admin.register(HistoricalPrice)
class HistoricalPriceAdmin(admin.ModelAdmin):
    list_display = ['asset', 'date']  # Simplified to avoid field name issues
    list_filter = ['date', 'asset__asset_type']
    search_fields = ['asset__symbol', 'asset__name']
    date_hierarchy = 'date'
    ordering = ['-date']

    # Show related asset info
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('asset')


@admin.register(Benchmark)
class BenchmarkAdmin(admin.ModelAdmin):
    list_display = ['name', 'symbol', 'description']
    search_fields = ['name', 'symbol', 'description']
    ordering = ['name']


@admin.register(AssetPortfolioMapping)
class AssetPortfolioMappingAdmin(admin.ModelAdmin):
    list_display = ['portfolio', 'asset', 'weight']
    list_filter = ['portfolio', 'asset__asset_type']
    search_fields = ['portfolio__name', 'asset__symbol']
    ordering = ['portfolio']

    # Show related info
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('portfolio', 'asset')


# Customize admin site headers
admin.site.site_header = "Portfolio Comparison Admin"
admin.site.site_title = "Portfolio Admin"
admin.site.index_title = "Welcome to Portfolio Management"