import csv
from datetime import datetime, time
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q

from .models import (
    BusinessSettings,
    Inventory,
    Sale,
    Delivery,
    Expense,
    InventoryAdjustment,
    StockMovement,
)
from .forms import (
    SaleForm,
    DeliveryForm,
    ExpenseForm,
    InventoryAdjustmentForm,
    RestockingCalculatorForm,
    BusinessSettingsForm,
    OpeningStockForm,
)
from .services import (
    PricingService,
    InventoryService,
    RestockingCalculator,
    AccountingService,
)


def login_view(request):
    """
    Standard Django secure authentication view.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """
    Logs out the user and redirects to login page.
    """
    logout(request)
    messages.info(request, "You have been logged out securely.")
    return redirect('login')


@login_required
def dashboard_view(request):
    """
    Central operational dashboard showing real-time stock, today's metrics,
    weekly sales summaries, and recent activity.
    """
    settings = BusinessSettings.get_settings()
    inventory = Inventory.get_inventory()

    today = timezone.localdate()
    start_of_today = timezone.make_aware(datetime.combine(today, time.min))
    end_of_today = timezone.make_aware(datetime.combine(today, time.max))

    # Today's Financials
    today_summary = AccountingService.get_financial_summary(start_of_today, end_of_today)

    # Today's deliveries count
    today_deliveries_count = Delivery.objects.filter(delivery_date__range=(start_of_today, end_of_today)).count()

    # 7-day sales trend
    seven_days_ago = start_of_today - timezone.timedelta(days=6)
    recent_sales = Sale.objects.filter(sale_date__gte=seven_days_ago, is_cancelled=False)
    
    daily_chart_data = []
    for i in range(7):
        day = (seven_days_ago + timezone.timedelta(days=i)).date()
        day_sales = [s for s in recent_sales if timezone.localdate(s.sale_date) == day]
        day_rev = sum(s.total_amount for s in day_sales) or Decimal('0.00')
        day_eggs = sum(s.quantity for s in day_sales) or 0
        daily_chart_data.append({
            'day_name': day.strftime('%a, %d %b'),
            'revenue': float(day_rev),
            'eggs': day_eggs,
        })

    # Recent Transactions / Stock Movements
    recent_movements = StockMovement.objects.all()[:8]
    recent_sales_list = Sale.objects.all()[:5]

    # Quick restocking calculator recommendation
    calc_result = RestockingCalculator.calculate(
        current_stock_eggs=inventory.total_eggs,
        target_trays=30, # Default target of 30 full trays
        purchase_cost_per_tray=settings.default_purchase_cost_per_tray
    )

    context = {
        'business': settings,
        'inventory': inventory,
        'today': today_summary,
        'today_deliveries_count': today_deliveries_count,
        'daily_chart_data': daily_chart_data,
        'recent_movements': recent_movements,
        'recent_sales': recent_sales_list,
        'restock_calc': calc_result,
        'is_low_stock': inventory.is_low_stock(settings.low_stock_threshold),
    }
    return render(request, 'dashboard.html', context)


@login_required
def price_preview_api(request):
    """
    JSON API for live pricing preview and offer breakdown on the sales form.
    """
    try:
        qty_str = request.GET.get('quantity', '1')
        quantity = int(qty_str)
        if quantity <= 0:
            return JsonResponse({'success': False, 'error': 'Quantity must be greater than zero.'}, status=400)

        pricing = PricingService.calculate_optimal_price(quantity)
        inventory = Inventory.get_inventory()
        available = inventory.total_eggs

        return JsonResponse({
            'success': True,
            'quantity': quantity,
            'total_price': float(pricing['total_price']),
            'formatted_price': f"KSh {pricing['total_price']:,.2f}",
            'breakdown_items': [
                {
                    'name': item['bundle_name'],
                    'units': item['bundle_units'],
                    'unit_price': float(item['unit_price']),
                    'subtotal': float(item['subtotal']),
                }
                for item in pricing['breakdown_items']
            ],
            'breakdown_text': pricing['breakdown_text'],
            'available_stock': available,
            'sufficient_stock': available >= quantity,
        })
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid quantity entered.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def sales_view(request):
    """
    Record new sales with live pricing and review past sales history.
    """
    if request.method == 'POST':
        form = SaleForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            customer_name = form.cleaned_data['customer_name']
            sale_date = form.cleaned_data['sale_date']
            notes = form.cleaned_data['notes']

            try:
                sale = InventoryService.record_sale(
                    quantity=quantity,
                    customer_name=customer_name,
                    sale_date=sale_date,
                    notes=notes
                )
                messages.success(
                    request,
                    f"Sale #{sale.id} recorded successfully! Sold {quantity} eggs to {sale.customer_name} for KSh {sale.total_amount:,.2f}."
                )
                return redirect('sales')
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            messages.error(request, "Please correct the errors in the sales form.")
    else:
        form = SaleForm()

    # Sales history
    sales_qs = Sale.objects.all()
    query = request.GET.get('q', '').strip()
    if query:
        sales_qs = sales_qs.filter(
            Q(customer_name__icontains=query) | Q(notes__icontains=query) | Q(id__icontains=query)
        )

    paginator = Paginator(sales_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    inventory = Inventory.get_inventory()
    context = {
        'form': form,
        'page_obj': page_obj,
        'query': query,
        'inventory': inventory,
    }
    return render(request, 'sales.html', context)


@login_required
def cancel_sale_view(request, sale_id):
    """
    Safely cancel a sale and return eggs to inventory without deleting history.
    """
    sale = get_object_or_404(Sale, id=sale_id)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        try:
            InventoryService.cancel_sale(sale.id, reason=reason)
            messages.success(request, f"Sale #{sale.id} was successfully cancelled. {sale.quantity} eggs were restored to stock.")
        except ValidationError as e:
            messages.error(request, str(e))
        return redirect('sales')

    return render(request, 'confirm_delete.html', {
        'title': f"Cancel Sale #{sale.id}",
        'message': f"Are you sure you want to cancel Sale #{sale.id} for {sale.quantity} eggs (KSh {sale.total_amount:,.2f}) to {sale.customer_name}? The eggs will be returned to inventory.",
        'action_name': "Confirm Cancellation",
        'back_url': 'sales'
    })


@login_required
def deliveries_view(request):
    """
    Record restocking deliveries from suppliers, calculate costs, and view delivery history.
    """
    settings = BusinessSettings.get_settings()
    inventory = Inventory.get_inventory()

    if request.method == 'POST':
        if 'calc_submit' in request.POST:
            calc_form = RestockingCalculatorForm(request.POST)
            delivery_form = DeliveryForm(initial={'purchase_price_per_tray': settings.default_purchase_cost_per_tray})
            calc_result = None
            if calc_form.is_valid():
                calc_result = RestockingCalculator.calculate(
                    current_stock_eggs=inventory.total_eggs,
                    target_trays=calc_form.cleaned_data['target_trays'],
                    purchase_cost_per_tray=calc_form.cleaned_data['purchase_cost_per_tray']
                )
        else:
            calc_form = RestockingCalculatorForm(initial={
                'target_trays': 30,
                'purchase_cost_per_tray': settings.default_purchase_cost_per_tray
            })
            calc_result = None
            delivery_form = DeliveryForm(request.POST, request.FILES)
            if delivery_form.is_valid():
                try:
                    delivery = InventoryService.record_delivery(
                        supplier_name=delivery_form.cleaned_data['supplier_name'],
                        trays_received=delivery_form.cleaned_data['trays_received'],
                        purchase_price_per_tray=delivery_form.cleaned_data['purchase_price_per_tray'],
                        delivery_date=delivery_form.cleaned_data['delivery_date'],
                        notes=delivery_form.cleaned_data['notes'],
                        receipt_image=delivery_form.cleaned_data.get('receipt_image')
                    )
                    messages.success(
                        request,
                        f"Delivery #{delivery.id} recorded! Added {delivery.trays_received} trays ({delivery.eggs_received} eggs) from {delivery.supplier_name}. Total Cost: KSh {delivery.total_cost:,.2f}."
                    )
                    return redirect('deliveries')
                except ValidationError as e:
                    messages.error(request, str(e))
            else:
                messages.error(request, "Please correct the errors in the delivery form.")
    else:
        delivery_form = DeliveryForm(initial={
            'purchase_price_per_tray': settings.default_purchase_cost_per_tray
        })
        calc_form = RestockingCalculatorForm(initial={
            'target_trays': 30,
            'purchase_cost_per_tray': settings.default_purchase_cost_per_tray
        })
        calc_result = RestockingCalculator.calculate(
            current_stock_eggs=inventory.total_eggs,
            target_trays=30,
            purchase_cost_per_tray=settings.default_purchase_cost_per_tray
        )

    deliveries_qs = Delivery.objects.all()
    paginator = Paginator(deliveries_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'delivery_form': delivery_form,
        'calc_form': calc_form,
        'calc_result': calc_result,
        'page_obj': page_obj,
        'inventory': inventory,
    }
    return render(request, 'deliveries.html', context)


@login_required
def expenses_view(request):
    """
    Record and review operating expenses (Transport, Packaging, Utilities, etc.).
    """
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save()
            messages.success(request, f"Expense recorded: {expense.description} (KSh {expense.amount:,.2f}).")
            return redirect('expenses')
        else:
            messages.error(request, "Please correct errors in the expense form.")
    else:
        form = ExpenseForm()

    expenses_qs = Expense.objects.all()

    # Category and date filtering
    cat_filter = request.GET.get('category', '').strip()
    if cat_filter:
        expenses_qs = expenses_qs.filter(category=cat_filter)

    # Monthly total calculation
    today = timezone.localdate()
    month_start = timezone.make_aware(datetime(today.year, today.month, 1, 0, 0))
    month_expenses_total = sum(
        e.amount for e in Expense.objects.filter(expense_date__gte=month_start)
    ) or Decimal('0.00')

    paginator = Paginator(expenses_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'form': form,
        'page_obj': page_obj,
        'category_filter': cat_filter,
        'month_expenses_total': month_expenses_total,
        'categories': Expense.CATEGORY_CHOICES,
    }
    return render(request, 'expenses.html', context)


@login_required
def inventory_view(request):
    """
    Current egg inventory details, stock loss adjustments,
    and auditable stock movements log.
    """
    inventory = Inventory.get_inventory()
    settings = BusinessSettings.get_settings()

    if request.method == 'POST':
        adj_form = InventoryAdjustmentForm(request.POST)
        if adj_form.is_valid():
            try:
                adj = InventoryService.record_adjustment(
                    quantity=adj_form.cleaned_data['quantity'],
                    reason=adj_form.cleaned_data['reason'],
                    adjustment_type=adj_form.cleaned_data['adjustment_type'],
                    adjustment_date=adj_form.cleaned_data['adjustment_date'],
                    notes=adj_form.cleaned_data['notes'],
                )
                action_text = "recorded as loss" if adj.adjustment_type == 'loss' else "added to inventory"
                messages.success(
                    request,
                    f"Stock adjustment #{adj.id} ({adj.get_reason_display()}) successfully {action_text}: {adj.quantity} eggs."
                )
                return redirect('inventory')
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please correct the errors in the adjustment form.")
    else:
        adj_form = InventoryAdjustmentForm()

    movements_qs = StockMovement.objects.all()
    paginator = Paginator(movements_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    calc_result = RestockingCalculator.calculate(
        current_stock_eggs=inventory.total_eggs,
        target_trays=30,
        purchase_cost_per_tray=settings.default_purchase_cost_per_tray
    )

    context = {
        'inventory': inventory,
        'business': settings,
        'adj_form': adj_form,
        'page_obj': page_obj,
        'calc_result': calc_result,
        'is_low_stock': inventory.is_low_stock(settings.low_stock_threshold),
    }
    return render(request, 'inventory.html', context)


@login_required
def transactions_view(request):
    """
    Complete audit trail of all business events:
    Sales, Restocking Deliveries, Operating Expenses, Stock Losses, and Adjustments.
    """
    movements_qs = StockMovement.objects.all()

    # Filter by movement type
    type_filter = request.GET.get('type', '').strip()
    if type_filter:
        movements_qs = movements_qs.filter(movement_type=type_filter)

    # Search filter
    search_query = request.GET.get('q', '').strip()
    if search_query:
        movements_qs = movements_qs.filter(
            Q(description__icontains=search_query) |
            Q(reference_id__icontains=search_query)
        )

    # Date range filters
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    if start_date_str:
        try:
            start_dt = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            movements_qs = movements_qs.filter(created_at__gte=start_dt)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_dt = timezone.make_aware(datetime.combine(datetime.strptime(end_date_str, '%Y-%m-%d'), time.max))
            movements_qs = movements_qs.filter(created_at__lte=end_dt)
        except ValueError:
            pass

    paginator = Paginator(movements_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'type_filter': type_filter,
        'search_query': search_query,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'movement_types': StockMovement.MOVEMENT_TYPES,
    }
    return render(request, 'transactions.html', context)


@login_required
def export_transactions_csv(request):
    """
    Export transaction audit logs to a clean CSV file.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="cheremo_transactions_{timezone.localdate()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Date & Time', 'Transaction Type', 'Egg Quantity Change',
        'Running Balance', 'Unit Cost (KES)', 'Total Value (KES)',
        'Reference', 'Description'
    ])

    movements = StockMovement.objects.all()
    for m in movements:
        writer.writerow([
            m.id,
            m.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            m.get_movement_type_display(),
            m.quantity_change,
            m.balance_after,
            f"{m.unit_cost:.4f}",
            f"{m.total_value:.2f}",
            m.reference_id,
            m.description,
        ])

    return response


@login_required
def reports_view(request):
    """
    Transparent financial reports: Daily, Weekly, Monthly, and Custom Range.
    Clearly shows Revenue, COGS, Gross Profit, Operating Expenses, Stock Losses, and Net Profit.
    """
    period = request.GET.get('period', 'monthly')
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    now = timezone.now()
    today = timezone.localdate()

    if period == 'daily':
        start_date = timezone.make_aware(datetime.combine(today, time.min))
        end_date = timezone.make_aware(datetime.combine(today, time.max))
        period_label = f"Today ({today.strftime('%d %B %Y')})"
    elif period == 'weekly':
        start_date = timezone.make_aware(datetime.combine(today - timezone.timedelta(days=7), time.min))
        end_date = now
        period_label = f"Last 7 Days ({start_date.strftime('%d %b')} - {today.strftime('%d %b %Y')})"
    elif period == 'all':
        start_date = None
        end_date = None
        period_label = "All Time Business Overview"
    elif period == 'custom' and start_date_str and end_date_str:
        try:
            start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.combine(datetime.strptime(end_date_str, '%Y-%m-%d'), time.max))
            period_label = f"Custom: {start_date_str} to {end_date_str}"
        except ValueError:
            start_date = timezone.make_aware(datetime(today.year, today.month, 1, 0, 0))
            end_date = now
            period_label = f"This Month ({today.strftime('%B %Y')})"
    else: # Default: monthly
        start_date = timezone.make_aware(datetime(today.year, today.month, 1, 0, 0))
        end_date = now
        period_label = f"This Month ({today.strftime('%B %Y')})"

    summary = AccountingService.get_financial_summary(start_date, end_date)

    # Top expenses in this period
    expenses_qs = Expense.objects.all()
    if start_date:
        expenses_qs = expenses_qs.filter(expense_date__gte=start_date)
    if end_date:
        expenses_qs = expenses_qs.filter(expense_date__lte=end_date)
    
    context = {
        'period': period,
        'period_label': period_label,
        'summary': summary,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'expenses_list': expenses_qs[:10],
    }
    return render(request, 'reports.html', context)


@login_required
def settings_view(request):
    """
    Settings page for Japhet to configure retail prices, default restock costs,
    low stock warnings, branding, and initialize one-time opening stock.
    """
    settings = BusinessSettings.get_settings()
    inventory = Inventory.get_inventory()

    if request.method == 'POST':
        if 'update_settings' in request.POST:
            settings_form = BusinessSettingsForm(request.POST, request.FILES, instance=settings)
            opening_form = OpeningStockForm()
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, "Depot settings and retail egg prices updated successfully!")
                return redirect('settings')
            else:
                messages.error(request, "Please check the settings form errors.")
        elif 'init_stock' in request.POST:
            opening_form = OpeningStockForm(request.POST)
            settings_form = BusinessSettingsForm(instance=settings)
            if opening_form.is_valid():
                trays = opening_form.cleaned_data['initial_trays']
                cost = opening_form.cleaned_data['cost_per_tray']
                try:
                    InventoryService.initialize_opening_stock(
                        initial_trays=trays,
                        cost_per_tray=cost
                    )
                    messages.success(
                        request,
                        f"Opening stock successfully initialized: {trays} trays ({trays * 30} eggs) at KSh {cost:,.2f}/tray!"
                    )
                    return redirect('settings')
                except ValidationError as e:
                    messages.error(request, str(e))
            else:
                messages.error(request, "Invalid opening stock values.")
    else:
        settings_form = BusinessSettingsForm(instance=settings)
        opening_form = OpeningStockForm()

    context = {
        'settings_form': settings_form,
        'opening_form': opening_form,
        'settings': settings,
        'inventory': inventory,
    }
    return render(request, 'settings.html', context)
