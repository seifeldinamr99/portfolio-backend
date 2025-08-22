# models
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Asset(models.Model):
    ASSET_TYPES = [
        ('ETF', 'ETF'),
        ('Stock', 'Stock'),
        ('Bond', 'Bond'),
        ('Sukuk', 'Sukuk'),
        ('Index', 'Index'),
        ('Commodity', 'Commodity'),
    ]

    MARKETS = [
        ('Saudi', 'Saudi'),
        ('International', 'International'),
        ('Global', 'Global'),
    ]

    CURRENCIES = [
        ('SAR', 'Saudi Riyal'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]

    symbol = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    asset_type = models.CharField(max_length=50, choices=ASSET_TYPES)
    market = models.CharField(max_length=50, choices=MARKETS)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default='USD')
    is_shariah_compliant = models.BooleanField(default=False)
    sector = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    data_provider_config = models.JSONField(default=dict)
    inception_date = models.DateField(null=True, blank=True)
    expense_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assets'
        ordering = ['symbol']

    def __str__(self):
        return f"{self.symbol} - {self.name}"


class Portfolio(models.Model):
    PORTFOLIO_TYPES = [
        ('ETF', 'ETF'),
        ('Composite', 'Composite'),
        ('Model', 'Model'),
    ]

    REBALANCING_RULES = [
        ('none', 'None'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]

    CURRENCIES = [
        ('SAR', 'Saudi Riyal'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    portfolio_type = models.CharField(max_length=50, choices=PORTFOLIO_TYPES)
    base_currency = models.CharField(max_length=3, choices=CURRENCIES, default='USD')
    is_predefined = models.BooleanField(default=True)
    rebalancing_rule = models.CharField(max_length=20, choices=REBALANCING_RULES, default='none')
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portfolios'
        ordering = ['name']

    def __str__(self):
        return self.name


class AssetPortfolioMapping(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='asset_mappings')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='portfolio_mappings')
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))]
    )
    effective_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'asset_portfolio_mappings'
        unique_together = ['portfolio', 'asset', 'effective_date']
        ordering = ['-effective_date', '-weight']

    def __str__(self):
        return f"{self.portfolio.name} - {self.asset.symbol} ({self.weight:.2%})"


class HistoricalPrice(models.Model):
    DATA_PROVIDERS = [
        ('yfinance', 'Yahoo Finance'),
        ('manual', 'Manual Entry'),
    ]

    CURRENCIES = [
        ('SAR', 'Saudi Riyal'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='prices')
    date = models.DateField()
    open = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    high = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    low = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    close = models.DecimalField(max_digits=12, decimal_places=4)
    adjusted_close = models.DecimalField(max_digits=12, decimal_places=4)
    volume = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default='USD')
    data_provider = models.CharField(max_length=50, choices=DATA_PROVIDERS, default='yfinance')
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'historical_prices'
        unique_together = ['asset', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.asset.symbol} - {self.date} - {self.close}"


class Benchmark(models.Model):
    MARKET_FOCUS = [
        ('Saudi', 'Saudi'),
        ('GCC', 'GCC'),
        ('Global', 'Global'),
        ('Sector', 'Sector'),
    ]

    CURRENCIES = [
        ('SAR', 'Saudi Riyal'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]

    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default='USD')
    market_focus = models.CharField(max_length=50, choices=MARKET_FOCUS)
    data_provider_config = models.JSONField(default=dict)
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'benchmarks'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.symbol})"


