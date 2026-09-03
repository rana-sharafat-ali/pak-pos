from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import threading
from pakpos_project.apps.core.services import get_current_system_settings
from .models import ExpenseCategory, Expense
from .forms import ExpenseCategoryForm, ExpenseForm

def send_expense_alert_async(expense_id):
    try:
        expense = Expense.objects.get(id=expense_id)
        settings = get_current_system_settings()
        
        # Collect owner emails
        emails = []
        for key in ['owner_email_1', 'owner_email_2', 'owner_email_3']:
            email = settings.get(key)
            if email:
                emails.append(email)
                
        if not emails:
            return # No emails configured
            
        app_name = settings.get('app_name', 'PakPOS')
        subject = f"[{app_name}] New Expense Logged: PKR {expense.amount}"
        
        context = {
            'expense': expense,
            'app_name': app_name,
            'currency': settings.get('app_currency', 'PKR')
        }
        
        html_content = render_to_string('emails/expense_alert.html', context)
        text_content = strip_tags(html_content)
        
        from pakpos_project.apps.core.models import EmailQueue
        
        email_job = EmailQueue(
            subject=subject,
            text_content=text_content,
            html_content=html_content
        )
        email_job.set_emails(emails)
        email_job.save()
        
    except Exception as e:
        print(f"Error queueing expense email: {e}")

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.role == 'admin'

# --- CATEGORY VIEWS (Admin Only) ---
class ExpenseCategoryListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = ExpenseCategory
    template_name = 'expenses/category_list.html'
    context_object_name = 'categories'
    ordering = ['name']

class ExpenseCategoryCreateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, CreateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expenses/category_form.html'
    success_url = reverse_lazy('expenses:category_list')
    success_message = "Expense category created successfully!"

class ExpenseCategoryUpdateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expenses/category_form.html'
    success_url = reverse_lazy('expenses:category_list')
    success_message = "Expense category updated successfully!"

# --- EXPENSE VIEWS (All Users) ---
class ExpenseListView(LoginRequiredMixin, ListView):
    model = Expense
    template_name = 'expenses/expense_list.html'
    context_object_name = 'expenses'
    ordering = ['-date']

    def get_queryset(self):
        qs = super().get_queryset()
        # Admin sees all, cashiers see their own (or all depending on policy, let's say all for transparency or only their own)
        if self.request.user.is_superuser or self.request.user.role == 'admin':
            return qs
        return qs.filter(logged_by=self.request.user)

class ExpenseCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expenses/expense_form.html'
    success_url = reverse_lazy('expenses:expense_list')
    success_message = "Expense logged successfully!"

    def form_valid(self, form):
        form.instance.logged_by = self.request.user
        
        from pakpos_project.apps.sales.models import CashDrawerShift
        active_shift = CashDrawerShift.objects.filter(
            cashier=self.request.user,
            status=CashDrawerShift.Status.OPEN
        ).first()
        form.instance.shift = active_shift
        
        response = super().form_valid(form)
        
        # Call directly since it only saves to DB (very fast), no need for dangerous threads
        send_expense_alert_async(form.instance.id)
        
        return response
