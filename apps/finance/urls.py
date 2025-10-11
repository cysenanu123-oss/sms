# ============================================
# FILE 3: apps/finance/urls.py (UPDATE)
# ============================================

from django.urls import path
from .admin_views import record_payment, get_pending_fees, get_finance_overview

app_name = 'finance'

urlpatterns = [
    # Admin endpoints
    path('api/v1/admin/finance/record-payment/', record_payment, name='record_payment'),
    path('api/v1/admin/finance/pending-fees/', get_pending_fees, name='pending_fees'),
    path('api/v1/admin/finance/overview/', get_finance_overview, name='overview'),
]