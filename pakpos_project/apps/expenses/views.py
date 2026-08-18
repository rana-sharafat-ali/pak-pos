from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from .models import ExpenseCategory, Expense
from .forms import ExpenseCategoryForm, ExpenseForm

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
        return super().form_valid(form)
