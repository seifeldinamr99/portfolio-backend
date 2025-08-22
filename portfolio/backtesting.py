# backtesting.py
import pandas as pd
import numpy as np
import pyfolio as pf
from datetime import datetime
from django.db.models import Q
from .models import Portfolio, HistoricalPrice, Benchmark, AssetPortfolioMapping


class SimpleBacktestEngine:
    """
    Minimal backtesting engine using pyfolio for MVP
    """

    def __init__(self, portfolio_mix, benchmark_id, start_date, end_date, rebalance_frequency='never'):
        self.portfolio_mix = portfolio_mix
        self.benchmark_id = benchmark_id
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.rebalance_frequency = rebalance_frequency

    def _clean_results(self, data):
        """
        Clean NaN and infinite values from results to make them JSON serializable
        """
        if isinstance(data, dict):
            cleaned = {}
            for key, value in data.items():
                cleaned[key] = self._clean_results(value)
            return cleaned
        elif isinstance(data, list):
            return [self._clean_results(item) for item in data]
        elif isinstance(data, (np.floating, float)):
            if np.isnan(data) or np.isinf(data):
                return 0.0
            return float(data)
        elif isinstance(data, (np.integer, int)):
            return int(data)
        elif hasattr(data, 'item'):  # numpy scalars
            cleaned_value = data.item()
            if isinstance(cleaned_value, float) and (np.isnan(cleaned_value) or np.isinf(cleaned_value)):
                return 0.0
            return cleaned_value
        else:
            return data

    def run_backtest(self):
        """
        Run simple backtest using pyfolio with user-defined rebalancing
        """
        try:
            # 1. Get individual portfolio returns (before mixing)
            individual_portfolio_returns = self._get_individual_portfolio_returns()

            # Check if we have any data
            if individual_portfolio_returns.empty:
                return {
                    'error': 'No portfolio data found for the specified date range',
                    'performance_metrics': {},
                    'time_series': {'dates': [], 'portfolio_values': [], 'benchmark_values': []},
                    'portfolio_composition': self._get_portfolio_composition(),
                    'rebalancing_events': [],
                    'rebalancing_frequency': self.rebalance_frequency,
                    'calculation_date': datetime.now().isoformat()
                }

            # 2. Apply user-selected rebalancing to create combined returns
            portfolio_returns = self._apply_rebalancing_logic(individual_portfolio_returns)

            if portfolio_returns.empty:
                return {
                    'error': 'Unable to calculate portfolio returns',
                    'performance_metrics': {},
                    'time_series': {'dates': [], 'portfolio_values': [], 'benchmark_values': []},
                    'portfolio_composition': self._get_portfolio_composition(),
                    'rebalancing_events': [],
                    'rebalancing_frequency': self.rebalance_frequency,
                    'calculation_date': datetime.now().isoformat()
                }

            # 3. Get benchmark returns
            benchmark_returns = self._get_benchmark_returns()

            # 4. Use pyfolio to calculate metrics (with error handling)
            try:
                metrics = pf.timeseries.perf_stats(portfolio_returns)
                # Convert metrics to regular Python types and handle NaNs
                clean_metrics = {}
                for key, value in metrics.items():
                    if isinstance(value, (np.floating, float)):
                        if np.isnan(value) or np.isinf(value):
                            clean_metrics[key] = 0.0
                        else:
                            clean_metrics[key] = float(value)
                    else:
                        clean_metrics[key] = value
            except Exception as e:
                print(f"Error calculating pyfolio metrics: {e}")
                # Fallback to basic metrics
                clean_metrics = {
                    'Annual return': portfolio_returns.mean() * 252 if not portfolio_returns.empty else 0.0,
                    'Annual volatility': portfolio_returns.std() * np.sqrt(252) if not portfolio_returns.empty else 0.0,
                    'Sharpe ratio': 0.0,
                    'Max drawdown': 0.0,
                    'Sortino ratio': 0.0
                }

            # 5. Calculate additional comparison metrics
            comparison_metrics = self._calculate_comparison_metrics(portfolio_returns, benchmark_returns)

            # 6. Generate time series for frontend
            time_series = self._generate_time_series(portfolio_returns, benchmark_returns)

            # 7. Get rebalancing events for display
            rebalancing_events = self._get_rebalancing_events()

            # Calculate total return safely
            total_return = 0.0
            if not portfolio_returns.empty:
                total_return_calc = ((1 + portfolio_returns).prod() - 1) * 100
                if not (np.isnan(total_return_calc) or np.isinf(total_return_calc)):
                    total_return = float(total_return_calc)

            results = {
                'performance_metrics': {
                    'annual_return': round(clean_metrics.get('Annual return', 0) * 100, 2),
                    'volatility': round(clean_metrics.get('Annual volatility', 0) * 100, 2),
                    'sharpe_ratio': round(clean_metrics.get('Sharpe ratio', 0), 3),
                    'max_drawdown': round(clean_metrics.get('Max drawdown', 0) * 100, 2),
                    'sortino_ratio': round(clean_metrics.get('Sortino ratio', 0), 3),
                    'total_return': round(total_return, 2),
                    **comparison_metrics
                },
                'time_series': time_series,
                'portfolio_composition': self._get_portfolio_composition(),
                'rebalancing_events': rebalancing_events,
                'rebalancing_frequency': self.rebalance_frequency,
                'calculation_date': datetime.now().isoformat()
            }

            # Clean all results to ensure JSON serializability
            return self._clean_results(results)

        except Exception as e:
            print(f"Backtest error: {str(e)}")
            raise Exception(f"Backtest failed: {str(e)}")

    def _get_individual_portfolio_returns(self):
        """
        Get returns for each portfolio separately (before applying user's rebalancing)
        """
        portfolio_returns_dict = {}

        for portfolio_config in self.portfolio_mix:
            portfolio_id = portfolio_config['portfolio_id']

            # Get portfolio returns
            portfolio_returns = self._get_single_portfolio_returns(portfolio_id)
            portfolio_returns_dict[portfolio_id] = portfolio_returns

        # Combine into DataFrame with portfolio IDs as columns
        returns_df = pd.DataFrame(portfolio_returns_dict)
        return returns_df.fillna(0)

    def _apply_rebalancing_logic(self, individual_returns):
        """
        Apply USER-SELECTED rebalancing frequency to create combined portfolio
        """
        if individual_returns.empty:
            return pd.Series(dtype=float)

        # Get target weights from user input
        target_weights = {}
        for portfolio_config in self.portfolio_mix:
            portfolio_id = portfolio_config['portfolio_id']
            weight = float(portfolio_config['weight']) / 100.0
            target_weights[portfolio_id] = weight

        if self.rebalance_frequency == 'never':
            # Buy and hold - apply initial weights and let them drift
            weighted_returns = []
            for portfolio_id, weight in target_weights.items():
                if portfolio_id in individual_returns.columns:
                    weighted_returns.append(individual_returns[portfolio_id] * weight)

            if weighted_returns:
                combined_returns = pd.concat(weighted_returns, axis=1).sum(axis=1)
                combined_returns.name = 'portfolio_returns'
                return combined_returns
            else:
                return pd.Series(dtype=float)

        else:
            # Periodic rebalancing
            return self._calculate_rebalanced_returns(individual_returns, target_weights)

    def _calculate_rebalanced_returns(self, individual_returns, target_weights):
        """
        Calculate returns with periodic rebalancing back to target weights
        """
        # Get rebalancing dates
        rebalance_dates = self._get_rebalancing_dates(individual_returns.index)

        # Initialize portfolio value tracking
        portfolio_values = pd.Series(index=individual_returns.index, dtype=float)
        portfolio_values.iloc[0] = 100000  # Starting value

        # Track current weights
        current_weights = target_weights.copy()

        # Calculate day-by-day portfolio value
        for i in range(len(individual_returns)):
            date = individual_returns.index[i]

            if i == 0:
                continue  # Already set initial value

            # Check if rebalancing date
            if date in rebalance_dates:
                # Rebalance back to target weights
                current_weights = target_weights.copy()

            # Calculate day's return based on current weights
            day_return = 0
            for portfolio_id, weight in current_weights.items():
                if portfolio_id in individual_returns.columns:
                    day_return += individual_returns[portfolio_id].iloc[i] * weight

            # Update portfolio value
            portfolio_values.iloc[i] = portfolio_values.iloc[i - 1] * (1 + day_return)

            # Update weights based on relative performance (weight drift)
            if day_return != 0:  # Avoid division by zero
                for portfolio_id in current_weights:
                    if portfolio_id in individual_returns.columns:
                        portfolio_return = individual_returns[portfolio_id].iloc[i]
                        # Update weight based on relative performance
                        current_weights[portfolio_id] = current_weights[portfolio_id] * (1 + portfolio_return) / (
                                1 + day_return)

        # Convert portfolio values to returns
        portfolio_returns = portfolio_values.pct_change().dropna()
        portfolio_returns.name = 'portfolio_returns'

        return portfolio_returns

    def _get_rebalancing_dates(self, date_index):
        """
        Get dates when rebalancing should occur based on user's frequency choice
        """
        rebalance_dates = []

        if self.rebalance_frequency == 'never':
            return rebalance_dates

        current_date = date_index[0]
        end_date = date_index[-1]

        while current_date <= end_date:
            if current_date in date_index:
                rebalance_dates.append(current_date)

            # Move to next rebalancing date
            if self.rebalance_frequency == 'monthly':
                current_date = current_date + pd.DateOffset(months=1)
            elif self.rebalance_frequency == 'quarterly':
                current_date = current_date + pd.DateOffset(months=3)
            elif self.rebalance_frequency == 'semi_annually':
                current_date = current_date + pd.DateOffset(months=6)
            elif self.rebalance_frequency == 'annually':
                current_date = current_date + pd.DateOffset(years=1)
            else:
                break

        return rebalance_dates

    def _get_rebalancing_events(self):
        """
        Get rebalancing events for display in UI
        """
        if self.rebalance_frequency == 'never':
            return []

        # This is a simplified version - you can enhance with actual costs
        rebalance_dates = self._get_rebalancing_dates(
            pd.date_range(self.start_date, self.end_date, freq='D')
        )

        events = []
        for date in rebalance_dates[1:]:  # Skip first date (initial allocation)
            events.append({
                'date': date.strftime('%Y-%m-%d'),
                'type': f'{self.rebalance_frequency}_rebalance',
                'description': f'Rebalanced portfolio back to target weights',
                'estimated_cost': 0.1  # Placeholder - implement actual cost calculation
            })

        return events

    def _get_single_portfolio_returns(self, portfolio_id):
        """
        Get returns for a single portfolio
        """
        print(f"=== DEBUG: Getting returns for portfolio {portfolio_id} ===")

        try:
            portfolio = Portfolio.objects.get(id=portfolio_id)
            print(f"Portfolio found: {portfolio.name}")
        except Portfolio.DoesNotExist:
            print(f"ERROR: Portfolio {portfolio_id} does not exist")
            return pd.Series(dtype=float)

        # Get asset mappings
        asset_mappings = AssetPortfolioMapping.objects.filter(
            portfolio=portfolio,
            effective_date__lte=self.end_date
        ).select_related('asset')

        print(f"Asset mappings found: {asset_mappings.count()}")

        for mapping in asset_mappings:
            print(f"  - Asset: {mapping.asset.symbol} ({mapping.asset.name})")
            print(f"    Weight: {mapping.weight}")
            print(f"    Effective Date: {mapping.effective_date}")

        asset_returns = []

        for mapping in asset_mappings:
            print(f"\n--- Processing asset {mapping.asset.symbol} ---")

            # Get price data
            prices = HistoricalPrice.objects.filter(
                asset=mapping.asset,
                date__range=[self.start_date, self.end_date]
            ).values('date', 'adjusted_close').order_by('date')

            print(f"Price records found: {prices.count()}")

            if prices.count() > 0:
                print(f"Date range: {prices.first()['date']} to {prices.last()['date']}")

            if prices.exists():
                # Convert to pandas series
                price_df = pd.DataFrame(list(prices))
                price_df['date'] = pd.to_datetime(price_df['date'])
                # Convert Decimal prices to float
                price_df['adjusted_close'] = price_df['adjusted_close'].astype(float)
                price_series = price_df.set_index('date')['adjusted_close']

                # Calculate returns
                returns = price_series.pct_change().dropna()
                print(f"Returns calculated: {len(returns)} data points")

                # Weight by asset allocation - CONVERT DECIMAL TO FLOAT HERE
                weighted_returns = returns * float(mapping.weight)
                asset_returns.append(weighted_returns)
                print(f"Weighted returns added (weight: {mapping.weight})")
            else:
                print(f"No price data found for {mapping.asset.symbol}")

        print(f"\nTotal asset returns to combine: {len(asset_returns)}")

        # Combine asset returns for this portfolio
        if asset_returns:
            portfolio_returns = pd.concat(asset_returns, axis=1).sum(axis=1)
            print(f"Final portfolio returns: {len(portfolio_returns)} data points")
            return portfolio_returns.fillna(0)
        else:
            print("No asset returns found - returning empty series")
            # Return empty series if no data
            return pd.Series(dtype=float)

    def _get_benchmark_returns(self):
        """
        Get benchmark returns using Asset and HistoricalPrice tables
        """
        try:
            # Get the benchmark object
            benchmark = Benchmark.objects.get(id=self.benchmark_id)

            # Find the corresponding asset using the benchmark symbol
            from .models import Asset
            try:
                benchmark_asset = Asset.objects.get(symbol=benchmark.symbol)

                # Get historical prices for the benchmark asset
                prices = HistoricalPrice.objects.filter(
                    asset=benchmark_asset,
                    date__range=[self.start_date, self.end_date]
                ).values('date', 'adjusted_close').order_by('date')

                if prices.exists():
                    price_df = pd.DataFrame(list(prices))
                    price_df['date'] = pd.to_datetime(price_df['date'])
                    # Convert Decimal prices to float
                    price_df['adjusted_close'] = price_df['adjusted_close'].astype(float)
                    price_series = price_df.set_index('date')['adjusted_close']

                    returns = price_series.pct_change().dropna()
                    returns.name = 'benchmark_returns'

                    return returns
                else:
                    print(f"No price data found for benchmark asset {benchmark.symbol}")
                    return pd.Series(dtype=float)

            except Asset.DoesNotExist:
                print(f"Benchmark asset with symbol {benchmark.symbol} not found in Asset table")
                return pd.Series(dtype=float)

        except Benchmark.DoesNotExist:
            print(f"Benchmark with ID {self.benchmark_id} not found")
            return pd.Series(dtype=float)
        except Exception as e:
            print(f"Error getting benchmark returns: {str(e)}")
            return pd.Series(dtype=float)

    def _calculate_comparison_metrics(self, portfolio_returns, benchmark_returns):
        """
        Calculate comparison metrics between portfolio and benchmark
        """
        if benchmark_returns.empty or portfolio_returns.empty:
            return {
                'benchmark_return': 0.0,
                'excess_return': 0.0,
                'beta': 0.0,
                'alpha': 0.0
            }

        # Align returns
        aligned_data = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()

        if aligned_data.empty or len(aligned_data) < 2:
            return {
                'benchmark_return': 0.0,
                'excess_return': 0.0,
                'beta': 0.0,
                'alpha': 0.0
            }

        port_returns = aligned_data.iloc[:, 0]
        bench_returns = aligned_data.iloc[:, 1]

        # Total benchmark return
        try:
            benchmark_total_return = ((1 + bench_returns).prod() - 1) * 100
            if np.isnan(benchmark_total_return) or np.isinf(benchmark_total_return):
                benchmark_total_return = 0.0
            else:
                benchmark_total_return = float(benchmark_total_return)
        except:
            benchmark_total_return = 0.0

        # Portfolio total return
        try:
            portfolio_total_return = ((1 + port_returns).prod() - 1) * 100
            if np.isnan(portfolio_total_return) or np.isinf(portfolio_total_return):
                portfolio_total_return = 0.0
            else:
                portfolio_total_return = float(portfolio_total_return)
        except:
            portfolio_total_return = 0.0

        # Excess return
        excess_return = portfolio_total_return - benchmark_total_return

        # Beta and Alpha
        try:
            covariance = np.cov(port_returns, bench_returns)[0, 1]
            variance = np.var(bench_returns)

            if variance != 0 and not np.isnan(covariance) and not np.isnan(variance):
                beta = covariance / variance
                if np.isnan(beta) or np.isinf(beta):
                    beta = 0.0
                else:
                    beta = float(beta)
            else:
                beta = 0.0

            # Simple alpha calculation (annual)
            if not port_returns.empty and not bench_returns.empty:
                port_annual = (1 + port_returns.mean()) ** 252 - 1
                bench_annual = (1 + bench_returns.mean()) ** 252 - 1
                alpha = (port_annual - 0.03) - beta * (bench_annual - 0.03)  # 3% risk-free rate

                if np.isnan(alpha) or np.isinf(alpha):
                    alpha = 0.0
                else:
                    alpha = float(alpha)
            else:
                alpha = 0.0

        except (ZeroDivisionError, ValueError, TypeError):
            beta = 0.0
            alpha = 0.0

        return {
            'benchmark_return': round(benchmark_total_return, 2),
            'excess_return': round(excess_return, 2),
            'beta': round(beta, 3),
            'alpha': round(alpha * 100, 2)
        }

    def _generate_time_series(self, portfolio_returns, benchmark_returns):
        """
        Generate time series data for charts
        """
        if portfolio_returns.empty:
            return {
                'dates': [],
                'portfolio_values': [],
                'benchmark_values': []
            }

        # Calculate cumulative returns
        portfolio_cumulative = (1 + portfolio_returns).cumprod()

        if not benchmark_returns.empty:
            # Align with portfolio returns
            aligned_data = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
            if not aligned_data.empty:
                benchmark_cumulative = (1 + aligned_data.iloc[:, 1]).cumprod()
            else:
                benchmark_cumulative = pd.Series([1] * len(portfolio_cumulative),
                                                 index=portfolio_cumulative.index)
        else:
            benchmark_cumulative = pd.Series([1] * len(portfolio_cumulative),
                                             index=portfolio_cumulative.index)

        # Convert to value terms (starting with 100,000)
        initial_value = 100000
        portfolio_values = portfolio_cumulative * initial_value
        benchmark_values = benchmark_cumulative * initial_value

        # Clean the values to remove NaN/inf
        portfolio_values = portfolio_values.fillna(initial_value)
        benchmark_values = benchmark_values.fillna(initial_value)

        return {
            'dates': [d.strftime('%Y-%m-%d') for d in portfolio_values.index],
            'portfolio_values': [float(v) if not (np.isnan(v) or np.isinf(v)) else initial_value for v in
                                 portfolio_values.round(2).tolist()],
            'benchmark_values': [float(v) if not (np.isnan(v) or np.isinf(v)) else initial_value for v in
                                 benchmark_values.round(2).tolist()]
        }

    def _get_portfolio_composition(self):
        """
        Get portfolio composition for display
        """
        composition = []

        for portfolio_config in self.portfolio_mix:
            try:
                portfolio = Portfolio.objects.get(id=portfolio_config['portfolio_id'])
                weight = float(portfolio_config['weight'])

                composition.append({
                    'name': portfolio.name,
                    'weight': weight,
                    'category': getattr(portfolio, 'category', 'N/A'),
                    'type': getattr(portfolio, 'portfolio_type', 'N/A'),
                    'currency': getattr(portfolio, 'base_currency', 'USD')
                })
            except Portfolio.DoesNotExist:
                composition.append({
                    'name': f'Portfolio {portfolio_config["portfolio_id"]} (Not Found)',
                    'weight': float(portfolio_config['weight']),
                    'category': 'N/A',
                    'type': 'N/A',
                    'currency': 'USD'
                })

        return composition